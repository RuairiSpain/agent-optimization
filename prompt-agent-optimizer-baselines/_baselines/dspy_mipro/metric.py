"""
metric.py — scoring for the DSPy MIPROv2 baseline, single-sourced against the same contract the
Foundry track is graded on.

Two distinct scores are computed, because MIPROv2 and the Foundry track need the signal at
different granularities:

1. RESPONSE-LEVEL metric (`build_response_metric`) — a per-(input, output) scalar in [0, 1] that
   MIPROv2 optimizes against during search. Built from the SAME `agent_tests` entries in
   `expected/expectations.json` that gate promotion in the Foundry track (must_contain /
   must_not_contain / tool_call.policy / regression_blocks), plus a universal `must_not_appear`
   invention/safety guard applied to every response regardless of whether it matches a named test.
   Falls back to the guard alone when a row has no matching agent_test (see README for the measured
   overlap per agent — it is a documented minority of rows, not all of them).

2. INSTRUCTION-LEVEL report (`instruction_level_report`) — imports `eval_match`/`validate` directly
   from ../../_tools/validate_candidate.py (not reimplemented) and runs them against the FINAL
   optimized instructions text MIPROv2 produces, exactly as the Foundry track's
   validate_candidate.py CLI does for an exported Foundry candidate. This is what makes the two
   tracks' must_have / should_remove / must_not_appear pass rates directly comparable in one table.

Neither function calls an LLM by default — both are pure regex/string checks, which keeps the
MIPROv2 search loop's optimization signal free and fast by default.

An OPTIONAL judge-LM layer (`score_rubrics_for_response`, and `judge=`/`cross_judge=` params on
`build_response_metric` / `instruction_level_report`) resolves the `semantic` instruction_rules and
scores the `rubrics` questions, via ../../_tools/llm_judge.py — the SAME shared judge module the
Foundry-side `validate_candidate.py --judge-backend` flag uses, so both tracks judge semantic
content identically. Cost control, deliberate: `run_mipro_baseline.py` wires the judge into the
FINAL holdout evaluation and the instruction-level report by default, NOT into the metric MIPROv2
calls during its search loop (which would multiply judge calls by trials × trainset/valset size ×
repeats_per_item) — pass --judge-during-search to opt into the far more expensive fully-judged
search signal.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Callable

from mock_tools import get_call_log, reset_call_log

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "_tools"
if str(_TOOLS_DIR) not in sys.path:
    # validate_candidate.py does `from llm_judge import ...` (a sibling module in _tools/); since
    # spec_from_file_location loads it by path rather than as a package member, _tools/ has to be
    # on sys.path explicitly for that import to resolve.
    sys.path.insert(0, str(_TOOLS_DIR))


def _import_validate_candidate():
    spec = importlib.util.spec_from_file_location("validate_candidate", _TOOLS_DIR / "validate_candidate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_vc = _import_validate_candidate()
eval_match = _vc.eval_match
validate_instructions = _vc.validate

from llm_judge import JudgeAgreementTracker, judge_rubric_item  # noqa: E402 (needs _TOOLS_DIR on sys.path first)

SEVERITY_WEIGHT = {"critical": 0.4, "high": 0.25, "medium": 0.15, "low": 0.05}


def _find_matching_test(query: str, expectations: dict) -> dict | None:
    for t in expectations.get("agent_tests", []):
        if t["input"] == query:
            return t
    return None


def _response_must_not_appear_penalty(response_text: str, expectations: dict) -> float:
    """Universal invention/safety guard: check every regex-backed must_not_appear rule against the
    RESPONSE text (not just the instructions). This is the per-example analogue of the Foundry
    track's must_not_appear axis, and is what actually stops MIPROv2 from being rewarded for a
    candidate that produces a response containing a baked-in fabricated policy value, a dosage
    figure, an invented VAT number, etc., even though that check nominally lives in
    instruction_rules."""
    penalty = 0.0
    for item in expectations.get("instruction_rules", {}).get("must_not_appear", []):
        m = item.get("match", {})
        if m.get("type") != "absent":
            continue  # semantic must_not_appear rules need a judge; skip in the free-scoring path
        hits = [p for p in m["patterns"] if re.search(p, response_text, re.IGNORECASE)]
        if hits:
            penalty += SEVERITY_WEIGHT.get(item.get("severity", "medium"), 0.15)
    return penalty


def score_response(query: str, response_text: str, tool_calls: list[str], expectations: dict) -> float:
    """Pure-Python, no-API scoring of one (query, response, observed tool calls) triple. Returns a
    float in [0, 1]. This is what build_response_metric wraps for MIPROv2."""
    score = 1.0
    score -= _response_must_not_appear_penalty(response_text, expectations)

    test = _find_matching_test(query, expectations)
    if test is not None:
        expect = test.get("expect", {})
        for s in expect.get("must_contain", []):
            if s not in response_text:
                score -= 0.15
        hard_violation = False
        for s in expect.get("must_not_contain", []):
            if s in response_text:
                score -= 0.3
                hard_violation = True
        tc = expect.get("tool_call")
        if tc:
            policy = tc.get("policy")
            wanted = set(tc.get("tools", []))
            called = set(tool_calls)
            if policy == "required":
                overlap = called & wanted
                if not overlap:
                    score -= 0.3
                    hard_violation = True
                elif overlap != wanted:
                    score -= 0.1 * len(wanted - overlap)
            elif policy == "forbidden":
                if called & wanted:
                    score -= 0.4
                    hard_violation = True
            # "optional": no penalty either way — response is graded on the other fields only.
        if test.get("regression_blocks") and hard_violation:
            score = min(score, 0.15)  # hard floor: mirrors Foundry's regression_blocks gate

    return max(0.0, min(1.0, score))


def score_rubrics_for_response(response_text: str, expectations: dict, judge, repeats: int = 1,
                                temperature: float = 0.0, cross_judge=None,
                                agreement_tracker: "JudgeAgreementTracker | None" = None) -> tuple[float, list[dict]]:
    """Judge-LM scoring of every `rubrics` question in expectations.json against one response.
    Returns (weighted_score_in_0_1, per_rubric_detail). Costs one (or `repeats`) judge call per
    rubric per response — see the module docstring's cost-control note before wiring this into a
    MIPROv2 search loop rather than just the final holdout evaluation."""
    rubrics = expectations.get("rubrics", [])
    if not rubrics or judge is None:
        return (1.0 if not rubrics else 0.0), []

    total_weight = sum(r["weight"] for r in rubrics)
    weighted_sum = 0.0
    details = []
    for r in rubrics:
        verdict = judge_rubric_item(r["question"], r["scale"], response_text, judge,
                                     repeats=repeats, temperature=temperature)
        if r["scale"] == "binary":
            unit_score = verdict.score if verdict.score is not None else 0.0
            passed = bool(verdict.passed) and unit_score >= r.get("pass_threshold", 1)
        else:  # likert_1_5
            raw = verdict.score if verdict.score is not None else 1.0
            unit_score = (raw - 1) / 4  # normalize 1-5 -> 0-1
            passed = raw >= r.get("pass_threshold", 3)
        weighted_sum += r["weight"] * unit_score
        detail = {"id": r["id"], "dimension": r["dimension"], "raw_score": verdict.score,
                   "unit_score": round(unit_score, 4), "passed": passed, "repeats": verdict.repeats}
        if cross_judge is not None:
            cross_verdict = judge_rubric_item(r["question"], r["scale"], response_text, cross_judge,
                                               repeats=repeats, temperature=temperature)
            detail["cross_judge_raw_score"] = cross_verdict.score
            if agreement_tracker is not None:
                if r["scale"] == "binary":
                    agreement_tracker.add_binary(bool(verdict.passed), bool(cross_verdict.passed))
                else:
                    agreement_tracker.add_likert(verdict.score or 0.0, cross_verdict.score or 0.0)
        details.append(detail)
    return (weighted_sum / total_weight if total_weight else 1.0), details


def build_response_metric(agent_spec, judge=None, judge_weight: float = 0.4, repeats: int = 1,
                           temperature: float = 0.0) -> Callable[..., float]:
    """Returns a dspy-compatible metric(example, pred, trace=None) -> float, closed over one
    agent's expectations contract. `trace` is accepted and ignored (some DSPy call sites pass it
    positionally).

    judge=None (default): pure deterministic scoring (score_response only) — zero API cost, safe
    to use as MIPROv2's search-loop metric. Pass a JudgeBackend to additionally blend in
    judge-scored `rubrics` at weight `judge_weight` (deterministic score gets 1-judge_weight) — do
    this for the FINAL holdout evaluation, or for the search loop only if cost is acceptable (see
    module docstring)."""
    expectations = agent_spec.expectations

    def metric(example: Any, pred: Any, trace: Any = None) -> float:
        query = getattr(example, "query", None) or example.get("query", "")
        response_text = getattr(pred, "response", None) or str(pred)
        tool_calls = get_call_log()
        deterministic = score_response(query, response_text, tool_calls, expectations)
        if judge is None:
            return deterministic
        rubric_score, _ = score_rubrics_for_response(response_text, expectations, judge,
                                                       repeats=repeats, temperature=temperature)
        return (1 - judge_weight) * deterministic + judge_weight * rubric_score

    return metric


def instruction_level_report(instructions_text: str, expectations: dict, judge=None, cross_judge=None,
                              repeats: int = 1, temperature: float = 0.0) -> dict:
    """Thin, single-sourced wrapper around _tools/validate_candidate.py's own `validate()`, run
    against MIPROv2's final optimized instructions. Produces the exact same report shape
    (sections / critical_failures / unjudged / blocked / primary_cross_judge_agreement) that the
    Foundry track's `validate_candidate.py --judge-backend` CLI produces for an exported Foundry
    candidate, so the two can sit in one comparison table without a second, possibly-drifted
    implementation of the contract logic. judge=None preserves the original UNJUDGED-queue
    behavior exactly."""
    return validate_instructions(expectations, instructions_text, judge=judge, cross_judge=cross_judge,
                                  repeats=repeats, temperature=temperature)


def wrap_predict_with_call_log(program_call: Callable[[str], str]) -> Callable[[str], tuple[str, list[str]]]:
    """Convenience: resets the mock-tool call log, invokes the program, and returns
    (response_text, tool_calls_made). Use this inside a program's forward() when NOT going through
    build_response_metric directly (e.g. during holdout evaluation, which needs the call log
    per-row for reporting, not just for scoring)."""

    def run(query: str) -> tuple[str, list[str]]:
        reset_call_log()
        response_text = program_call(query)
        return response_text, list(get_call_log())

    return run
