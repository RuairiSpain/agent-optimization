#!/usr/bin/env python3
"""
llm_judge.py — shared LLM-judge layer for resolving `semantic` match-type rules and scoring
`rubrics` questions from expected/expectations.json. Single-sourced so BOTH tracks judge
semantic/rubric content identically:
  - _tools/validate_candidate.py (Foundry track — judges an exported candidate's INSTRUCTIONS text)
  - _baselines/dspy_mipro/metric.py (DSPy track — judges instructions AND per-row response text)

Design constraints, deliberate:
  - Zero hard new dependency on _tools/. `litellm` is only imported lazily, inside LiteLLMJudge,
    so validate_candidate.py's existing regex-only path (its entire behavior before this file
    existed) keeps working with no third-party dependency for anyone who never passes --judge.
  - Respects each agent's judge_config (expected/expectations.json):
      * primary_judge_model — pinned to a vendor family disjoint from every supported Foundry
        optimization_model AND from whatever --task-lm/--prompt-lm the DSPy baseline is using, to
        avoid self-preference bias (Zheng et al. 2023; "Judging LLM-as-a-judge"; Panickssery et
        al. 2024, "LLM Evaluators Recognize and Favor Their Own Generations").
      * cross_judge_model — deliberately SAME-family as one optimization/task-model condition, run
        in parallel to MEASURE the self-preference gap via JudgeAgreementTracker, never to silently
        override the primary judge's verdict.
      * repeats_per_item — each judged item is asked this many times and majority-voted (binary) or
        averaged (Likert), so a single flaky call never decides a promotion-gating verdict alone.
      * inference_temperature — passed through to the judge call; repeats are only meaningful at a
        nonzero temperature (a temperature-0 judge asked the same question N times will just agree
        with itself N times, which is not evidence of anything — see judge_config.note in each
        agent's contract).
  - Cohen's kappa and Pearson r are CORPUS-LEVEL statistics over many paired ratings, not
    single-item statistics — computing one from a single judged item is meaningless (kappa's
    chance-correction term needs marginal frequencies across a set). JudgeAgreementTracker
    accumulates pairs across a whole run and computes the statistic once, over everything judged so
    far, not per item.

Two backends:
  - LiteLLMJudge — real judge calls via litellm.completion(). Model string resolved the same way
    dspy.LM resolves one (env-var API keys, e.g. OPENAI_API_KEY / ANTHROPIC_API_KEY).
  - StubJudge — zero-cost, zero-network, deterministic heuristic judge for --dry-run /
    offline smoke testing ONLY. Uses a simple lexical-overlap heuristic, not real judgment — same
    caveat as _baselines/dspy_mipro/stub_lm.py: proves the plumbing, says nothing about judge
    quality. NEVER use StubJudge output as evidence in a report.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol


# --- Backends --------------------------------------------------------------------------------

class JudgeBackend(Protocol):
    model_name: str

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        """Return the judge model's raw text completion for one prompt."""
        ...


class LiteLLMJudge:
    """Real judge backend. Requires `litellm` (a dspy dependency; install separately if using
    _tools/ standalone: `pip install litellm`) and the relevant provider API key in the
    environment."""

    def __init__(self, model: str):
        self.model_name = model

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        try:
            import litellm
        except ImportError as e:
            raise ImportError(
                "LiteLLMJudge requires the 'litellm' package ('pip install litellm') and a "
                "provider API key in the environment (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY). "
                "Use --judge-backend stub for a zero-cost offline smoke test instead."
            ) from e
        resp = litellm.completion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""


class StubJudge:
    """Deterministic, zero-cost, zero-network stand-in for a real judge. Has NO understanding of
    the statement or the text: it returns YES for a semantic statement if a rough majority of the
    statement's distinctive (non-stopword) terms also appear in the candidate text, and NO
    otherwise; for a Likert score it returns a fixed value derived from the same lexical-overlap
    heuristic. This is exactly as unintelligent as it sounds — it exists ONLY to smoke-test the
    judge-layer plumbing (prompt construction, repeat/majority-vote logic, agreement tracking,
    manifest wiring) with zero API cost, the same role StubLM plays for the optimizer itself."""

    model_name = "stub-judge (offline smoke test — NOT a real judge, no quality claim)"

    _STOPWORDS = {
        "the", "a", "an", "is", "are", "does", "do", "and", "or", "of", "to", "in", "on", "for",
        "that", "this", "with", "as", "be", "not", "no", "it", "its", "their", "than", "must",
        "should", "state", "states", "instruction", "instructions", "response",
    }

    def _terms(self, text: str) -> set[str]:
        words = re.findall(r"[a-z0-9']+", text.lower())
        return {w for w in words if w not in self._STOPWORDS and len(w) > 2}

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        # Prompts built by this module always embed STATEMENT/QUESTION and TEXT sections —
        # parse them back out rather than re-deriving overlap logic per call site.
        stmt_match = re.search(r"(?:STATEMENT|QUESTION):\s*(.+?)\n", prompt)
        text_match = re.search(r"TEXT:\s*(.+)", prompt, re.DOTALL)
        statement = stmt_match.group(1) if stmt_match else ""
        text = text_match.group(1) if text_match else prompt
        stmt_terms = self._terms(statement)
        text_terms = self._terms(text)
        overlap = len(stmt_terms & text_terms) / max(1, len(stmt_terms))
        if "1-5" in prompt or "Likert" in prompt or "integer" in prompt:
            score = 1 + round(overlap * 4)
            return str(min(5, max(1, score)))
        return "YES" if overlap >= 0.4 else "NO"


# --- Prompt construction + single-item judging -----------------------------------------------

_SEMANTIC_PROMPT = """You are grading whether a piece of TEXT satisfies a STATEMENT about it.
Answer with exactly one word: YES or NO. No explanation.

STATEMENT: {statement}

TEXT:
{text}
"""

_RUBRIC_BINARY_PROMPT = """You are grading a response against a QUESTION. Answer with exactly one
word: YES or NO. No explanation.

QUESTION: {question}

TEXT:
{text}
"""

_RUBRIC_LIKERT_PROMPT = """You are grading a response against a QUESTION on a 1-5 Likert scale,
where 1 = strongly disagree / poor and 5 = strongly agree / excellent. Answer with exactly one
integer from 1 to 5. No explanation.

QUESTION: {question}

TEXT:
{text}
"""


def _majority_bool(votes: list[str]) -> tuple[bool, list[str]]:
    normalized = [v.strip().upper() for v in votes]
    yes = sum(1 for v in normalized if v.startswith("Y"))
    no = len(normalized) - yes
    return (yes >= no), normalized


def _mean_likert(votes: list[str]) -> tuple[float | None, list[str]]:
    parsed = []
    for v in votes:
        m = re.search(r"[1-5]", v)
        if m:
            parsed.append(int(m.group()))
    if not parsed:
        return None, votes
    return statistics.mean(parsed), votes


@dataclass
class JudgeVerdict:
    kind: str  # "binary" | "likert"
    passed: bool | None = None       # for binary
    score: float | None = None       # for likert (1-5), or for binary as 0.0/1.0
    repeats: int = 0
    raw_votes: list[str] = field(default_factory=list)
    judge_model: str = ""


def judge_semantic_rule(statement: str, candidate_text: str, backend: JudgeBackend,
                         repeats: int = 1, temperature: float = 0.0) -> JudgeVerdict:
    prompt = _SEMANTIC_PROMPT.format(statement=statement, text=candidate_text)
    votes = [backend.complete(prompt, temperature=temperature) for _ in range(max(1, repeats))]
    passed, normalized = _majority_bool(votes)
    return JudgeVerdict(kind="binary", passed=passed, score=1.0 if passed else 0.0,
                         repeats=len(votes), raw_votes=normalized, judge_model=backend.model_name)


def judge_rubric_item(question: str, scale: str, text: str, backend: JudgeBackend,
                       repeats: int = 1, temperature: float = 0.0) -> JudgeVerdict:
    if scale == "binary":
        prompt = _RUBRIC_BINARY_PROMPT.format(question=question, text=text)
        votes = [backend.complete(prompt, temperature=temperature) for _ in range(max(1, repeats))]
        passed, normalized = _majority_bool(votes)
        return JudgeVerdict(kind="binary", passed=passed, score=1.0 if passed else 0.0,
                             repeats=len(votes), raw_votes=normalized, judge_model=backend.model_name)
    elif scale == "likert_1_5":
        prompt = _RUBRIC_LIKERT_PROMPT.format(question=question, text=text)
        votes = [backend.complete(prompt, temperature=temperature) for _ in range(max(1, repeats))]
        mean_score, normalized = _mean_likert(votes)
        return JudgeVerdict(kind="likert", score=mean_score, repeats=len(votes),
                             raw_votes=normalized, judge_model=backend.model_name)
    raise ValueError(f"Unknown rubric scale: {scale!r}")


# --- Corpus-level agreement -------------------------------------------------------------------

class JudgeAgreementTracker:
    """Accumulates (primary, cross) verdict pairs across MANY judged items within a run and
    computes agreement ONCE over everything collected so far. Cohen's kappa needs marginal
    frequencies across a set of ratings to correct for chance agreement — a per-item kappa is not
    a meaningful quantity, so this class deliberately has no per-item agreement method."""

    def __init__(self):
        self._binary_pairs: list[tuple[bool, bool]] = []
        self._likert_pairs: list[tuple[float, float]] = []

    def add_binary(self, primary: bool, cross: bool) -> None:
        self._binary_pairs.append((primary, cross))

    def add_likert(self, primary: float, cross: float) -> None:
        self._likert_pairs.append((primary, cross))

    def cohens_kappa(self) -> float | None:
        pairs = self._binary_pairs
        n = len(pairs)
        if n == 0:
            return None
        observed_agree = sum(1 for a, b in pairs if a == b) / n
        p_primary_true = sum(1 for a, _ in pairs if a) / n
        p_cross_true = sum(1 for _, b in pairs if b) / n
        expected_agree = (p_primary_true * p_cross_true) + ((1 - p_primary_true) * (1 - p_cross_true))
        if expected_agree >= 1.0:
            return 1.0 if observed_agree >= 1.0 else 0.0
        return (observed_agree - expected_agree) / (1 - expected_agree)

    def pearson_r(self) -> float | None:
        pairs = self._likert_pairs
        n = len(pairs)
        if n < 2:
            return None
        xs = [a for a, _ in pairs]
        ys = [b for _, b in pairs]
        xbar, ybar = statistics.mean(xs), statistics.mean(ys)
        num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
        denom_x = sum((x - xbar) ** 2 for x in xs)
        denom_y = sum((y - ybar) ** 2 for y in ys)
        denom = (denom_x * denom_y) ** 0.5
        if denom == 0:
            return None
        return num / denom

    def summary(self) -> dict:
        return {
            "n_binary_pairs": len(self._binary_pairs),
            "n_likert_pairs": len(self._likert_pairs),
            "cohens_kappa_binary": self._round_or_none(self.cohens_kappa()),
            "pearson_r_likert": self._round_or_none(self.pearson_r()),
            "interpretation": (
                "kappa/r require enough paired items to be meaningful — treat n<10 as indicative "
                "only, not a reportable inter-rater reliability figure."
            ),
        }

    @staticmethod
    def _round_or_none(v):
        return round(v, 4) if v is not None else None


def build_judge_backend(model: str, kind: str = "litellm") -> JudgeBackend:
    """Factory used by both CLI entry points (validate_candidate.py --judge-backend,
    run_mipro_baseline.py --judge-backend) so the stub-vs-real switch is spelled identically in
    both places."""
    if kind == "stub":
        return StubJudge()
    if kind == "litellm":
        return LiteLLMJudge(model)
    raise ValueError(f"Unknown judge backend kind: {kind!r}")


if __name__ == "__main__":
    # Tiny self-check: hand-computable kappa/pearson_r cases, run with `python llm_judge.py`.
    tracker = JudgeAgreementTracker()
    # Perfect agreement -> kappa == 1.0
    for _ in range(10):
        tracker.add_binary(True, True)
    assert tracker.cohens_kappa() == 1.0, tracker.cohens_kappa()

    # Chance-level-ish agreement -> kappa near 0
    tracker2 = JudgeAgreementTracker()
    pattern = [(True, True), (True, False), (False, True), (False, False)] * 5
    for a, b in pattern:
        tracker2.add_binary(a, b)
    k = tracker2.cohens_kappa()
    assert k is not None and abs(k) < 0.15, k

    # Perfect positive correlation -> pearson_r == 1.0
    tracker3 = JudgeAgreementTracker()
    for x in [1, 2, 3, 4, 5]:
        tracker3.add_likert(x, x)
    assert abs(tracker3.pearson_r() - 1.0) < 1e-9, tracker3.pearson_r()

    # Perfect negative correlation -> pearson_r == -1.0
    tracker4 = JudgeAgreementTracker()
    for x in [1, 2, 3, 4, 5]:
        tracker4.add_likert(x, 6 - x)
    assert abs(tracker4.pearson_r() - (-1.0)) < 1e-9, tracker4.pearson_r()

    print("llm_judge.py self-check OK: kappa(perfect)=1.0, kappa(near-chance)~0, "
          f"({k:.3f}), pearson_r(perfect+)=1.0, pearson_r(perfect-)=-1.0")
