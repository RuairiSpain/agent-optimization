#!/usr/bin/env python3
"""
human_calibration.py — judge-vs-human calibration for the shared LLM-judge layer (llm_judge.py).

Reviewer finding (external journal review of paper-v3; see docs/paper/publication-plan.md item #4):
Section 5.5 measures judge-vs-cross-judge agreement (a self-preference-bias check) but never
judge-vs-HUMAN agreement, so there is no calibration of the judge layer against human judgment at
all. This script closes that gap using the SAME statistical machinery already built for
judge-vs-cross-judge agreement (`llm_judge.JudgeAgreementTracker` — it was written generic over
"two raters," not specifically "two judges," so nothing there needed to change).

Two modes, run in sequence for a real calibration round:

1. `--sample`: build a STRATIFIED SHORTLIST of judge-eligible items (semantic instruction_rules /
   should_edit accept_if criteria / rubrics) across all ten agents, oversampling agent
   05-clinical-triage-safety (the safety-critical agent) and should_edit / semantic must_have items
   per docs/publication-plan.md's protocol. Writes a JSONL scaffold with `text_rated` and
   `human_value` left blank for a human rater to fill in against a specific run's real candidate
   instructions/responses — this script does not and cannot invent that text.

2. `--score`: given a filled-in human-ratings JSONL (see the module docstring for HumanRating's
   shape, printed by --sample), re-runs the SAME judge_semantic_rule/judge_rubric_item functions
   every other judged score in this pack uses, against the EXACT text_rated a human rater read, and
   feeds (judge verdict, human value) into a JudgeAgreementTracker exactly as Section 5.5's
   judge-vs-cross-judge check does. If more than one human_rater_id appears on the same item, also
   reports human-vs-human agreement (all rater pairs) as a secondary check on the human labels
   themselves before trusting them as a judge-calibration reference.

Human-rating JSONL line shape (one line per (item, rater) pair):
    {
      "agent_id": "05-clinical-triage-safety",
      "item_kind": "semantic_rule" | "should_edit_accept_if" | "rubric",
      "item_id": "MH-03" | "SE-01" | "R-01",           # traces back to expectations.json
      "statement": "..."                                # semantic_rule / should_edit_accept_if only
      "question": "...", "scale": "binary"|"likert_1_5", # rubric only
      "text_rated": "the EXACT candidate instructions or response text this item was judged against",
      "human_rater_id": "rater_a",
      "human_value": true | false | 1-5,                 # bool for binary, 1-5 int for likert_1_5
      "notes": ""                                        # optional
    }

Usage:
    # Step 1: generate the shortlist (no human data yet, no judge calls, no cost).
    python human_calibration.py --sample --n 80 --out human_ratings_TEMPLATE.jsonl

    # ... a human rater fills in text_rated + human_value for each line ...

    # Step 2: score the filled-in file (needs a judge backend; --judge-backend stub costs nothing
    # and proves the pipeline works, but its "agreement" is meaningless — see StubJudge's own
    # docstring in llm_judge.py. Use --judge-backend litellm for a real calibration number.)
    python human_calibration.py --score --ratings human_ratings_FILLED.jsonl --judge-backend litellm \\
        --judge-model anthropic/claude-sonnet-5
"""
from __future__ import annotations

import argparse
import json
import random
from itertools import combinations
from pathlib import Path

from llm_judge import JudgeAgreementTracker, build_judge_backend, judge_rubric_item, judge_semantic_rule

PACK_ROOT = Path(__file__).resolve().parent.parent
AGENT_IDS = sorted(p.name for p in PACK_ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit())


def _judge_eligible_items(agent_id: str) -> list[dict]:
    """Every item in this agent's expectations.json that a human could meaningfully calibrate the
    judge against: semantic instruction_rules (any section), should_edit accept_if criteria typed
    semantic, and all rubrics. Deterministic regex/string rules are excluded — there's no judge
    verdict to calibrate there."""
    expectations = json.loads((PACK_ROOT / agent_id / "expected" / "expectations.json").read_text())
    items = []
    ir = expectations.get("instruction_rules", {})
    for section, entries in ir.items():
        for it in entries:
            if section == "should_edit":
                accept_if = it.get("accept_if", {})
                if accept_if.get("type") == "semantic":
                    items.append({"agent_id": agent_id, "item_kind": "should_edit_accept_if",
                                  "item_id": it["id"], "statement": accept_if["statement"],
                                  "severity": it.get("severity", "medium")})
            else:
                m = it.get("match", {})
                if m.get("type") == "semantic":
                    items.append({"agent_id": agent_id, "item_kind": "semantic_rule",
                                  "item_id": it["id"], "statement": m["statement"],
                                  "severity": it.get("severity", "medium"), "section": section})
    for r in expectations.get("rubrics", []):
        items.append({"agent_id": agent_id, "item_kind": "rubric", "item_id": r["id"],
                       "question": r["question"], "scale": r["scale"], "weight": r.get("weight")})
    return items


def build_sample(n: int, seed: int, safety_agent: str = "05-clinical-triage-safety") -> list[dict]:
    """Stratified sample per docs/paper/publication-plan.md item #4's protocol: oversample the
    safety-critical agent and should_edit/semantic-must_have items, but still cover every agent so
    the calibration number isn't dominated by one agent's judge-prompt phrasing. Approach: pool all
    eligible items, assign each a stratum weight, then sample without replacement proportional to
    weight (simple, auditable — not a claim of a formally optimal design)."""
    rng = random.Random(seed)
    pool = []
    for agent_id in AGENT_IDS:
        for item in _judge_eligible_items(agent_id):
            weight = 1.0
            if agent_id == safety_agent:
                weight *= 3.0  # oversample the safety-critical agent
            if item["item_kind"] in ("should_edit_accept_if",) or (
                item["item_kind"] == "semantic_rule" and item.get("section") == "must_have"
            ):
                weight *= 2.0  # oversample should_edit / semantic must_have, per the protocol
            pool.append((weight, item))

    if n >= len(pool):
        return [item for _, item in pool]

    # Weighted sample without replacement (simple reservoir-free approach: fine at this pool size).
    chosen: list[dict] = []
    remaining = pool[:]
    for _ in range(n):
        total = sum(w for w, _ in remaining)
        r = rng.uniform(0, total)
        upto = 0.0
        for i, (w, item) in enumerate(remaining):
            upto += w
            if upto >= r:
                chosen.append(item)
                remaining.pop(i)
                break
    return chosen


def write_sample_template(items: list[dict], out_path: Path) -> None:
    lines = []
    for item in items:
        line = {
            "agent_id": item["agent_id"],
            "item_kind": item["item_kind"],
            "item_id": item["item_id"],
        }
        if "statement" in item:
            line["statement"] = item["statement"]
        if "question" in item:
            line["question"] = item["question"]
            line["scale"] = item["scale"]
        line["text_rated"] = None  # TODO(human rater / run operator): the exact candidate text this
                                    # item was judged against for a specific run -- this script
                                    # cannot fill this in, it depends on which run you're calibrating
        line["human_rater_id"] = None  # TODO: fill in per rater
        line["human_value"] = None     # TODO: true/false for binary and should_edit/semantic_rule,
                                        # 1-5 for likert_1_5 rubrics
        line["notes"] = ""
        lines.append(line)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def score_ratings(ratings_path: Path, judge, cross_judge=None, repeats: int = 1,
                   temperature: float = 0.0) -> dict:
    lines = [json.loads(l) for l in ratings_path.read_text().splitlines() if l.strip()]
    incomplete = [l for l in lines if l.get("text_rated") is None or l.get("human_value") is None]
    if incomplete:
        raise SystemExit(
            f"{len(incomplete)} of {len(lines)} rows still have text_rated/human_value unset -- "
            "fill in the template from --sample before running --score. First incomplete row: "
            f"{incomplete[0].get('agent_id')}/{incomplete[0].get('item_id')}"
        )

    judge_vs_human = JudgeAgreementTracker()
    per_agent: dict[str, JudgeAgreementTracker] = {}
    human_by_item: dict[tuple, list[tuple[str, object]]] = {}  # (agent_id, item_id) -> [(rater_id, value)]

    for row in lines:
        key = (row["agent_id"], row["item_id"])
        human_by_item.setdefault(key, []).append((row["human_rater_id"], row["human_value"]))
        agent_tracker = per_agent.setdefault(row["agent_id"], JudgeAgreementTracker())

        if row["item_kind"] in ("semantic_rule", "should_edit_accept_if"):
            verdict = judge_semantic_rule(row["statement"], row["text_rated"], judge,
                                           repeats=repeats, temperature=temperature)
            human_bool = bool(row["human_value"])
            judge_vs_human.add_binary(bool(verdict.passed), human_bool)
            agent_tracker.add_binary(bool(verdict.passed), human_bool)
        elif row["item_kind"] == "rubric":
            verdict = judge_rubric_item(row["question"], row["scale"], row["text_rated"], judge,
                                         repeats=repeats, temperature=temperature)
            if row["scale"] == "binary":
                human_bool = bool(row["human_value"])
                judge_vs_human.add_binary(bool(verdict.passed), human_bool)
                agent_tracker.add_binary(bool(verdict.passed), human_bool)
            else:
                human_val = float(row["human_value"])
                judge_vs_human.add_likert(verdict.score or 0.0, human_val)
                agent_tracker.add_likert(verdict.score or 0.0, human_val)
        else:
            raise ValueError(f"Unknown item_kind: {row['item_kind']!r}")

    # Human-vs-human agreement (secondary check on the labels themselves), for every item rated by
    # more than one distinct rater.
    human_vs_human = JudgeAgreementTracker()
    for (agent_id, item_id), ratings in human_by_item.items():
        raters = {rid: val for rid, val in ratings}
        if len(raters) < 2:
            continue
        kind = next(l["item_kind"] for l in lines if l["agent_id"] == agent_id and l["item_id"] == item_id)
        for (rid_a, val_a), (rid_b, val_b) in combinations(raters.items(), 2):
            if kind == "rubric":
                scale = next(l["scale"] for l in lines if l["agent_id"] == agent_id and l["item_id"] == item_id)
                if scale == "binary":
                    human_vs_human.add_binary(bool(val_a), bool(val_b))
                else:
                    human_vs_human.add_likert(float(val_a), float(val_b))
            else:
                human_vs_human.add_binary(bool(val_a), bool(val_b))

    return {
        "n_rows": len(lines),
        "n_distinct_items": len(human_by_item),
        "judge_vs_human": judge_vs_human.summary(),
        "judge_vs_human_by_agent": {aid: t.summary() for aid, t in per_agent.items()},
        "human_vs_human": human_vs_human.summary() if human_vs_human.summary()["n_binary_pairs"]
                          or human_vs_human.summary()["n_likert_pairs"] else
                          {"note": "fewer than 2 distinct human_rater_id values rated the same item "
                                   "-- cannot compute human-vs-human agreement; at least 2 raters "
                                   "double-rating a subset of items is needed for this figure"},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true", help="generate a stratified shortlist template")
    mode.add_argument("--score", action="store_true", help="score a filled-in human-ratings file")
    ap.add_argument("--n", type=int, default=80, help="--sample: target sample size (protocol default: 60-100)")
    ap.add_argument("--seed", type=int, default=0, help="--sample: sampling seed, for reproducibility")
    ap.add_argument("--out", default="human_ratings_TEMPLATE.jsonl", help="--sample: output path")
    ap.add_argument("--ratings", default=None, help="--score: path to the filled-in ratings JSONL")
    ap.add_argument("--judge-backend", choices=["stub", "litellm"], default="stub",
                     help="--score: 'stub' proves the pipeline runs but its agreement number is "
                          "meaningless (StubJudge has no real language understanding) -- use "
                          "'litellm' for an actual calibration figure")
    ap.add_argument("--judge-model", default=None, help="--score: required with --judge-backend litellm")
    ap.add_argument("--judge-repeats", type=int, default=1)
    ap.add_argument("--judge-temperature", type=float, default=0.0)
    ap.add_argument("--report-out", default=None, help="--score: write the full JSON report here too")
    args = ap.parse_args()

    if args.sample:
        items = build_sample(args.n, args.seed)
        write_sample_template(items, Path(args.out))
        by_agent: dict[str, int] = {}
        for it in items:
            by_agent[it["agent_id"]] = by_agent.get(it["agent_id"], 0) + 1
        print(f"Wrote {len(items)} items to {args.out}. Per-agent counts:")
        for agent_id in AGENT_IDS:
            print(f"  {agent_id:<34} {by_agent.get(agent_id, 0)}")
        print(
            "\nNext: for each line, fill in text_rated (the exact candidate instructions/response "
            "text this item was judged against for the specific run you're calibrating), "
            "human_rater_id, and human_value. Have at least one item per agent double-rated by a "
            "second human_rater_id if you want a human-vs-human agreement figure too. Then run "
            "--score against the filled-in file."
        )
        return

    if args.score:
        if not args.ratings:
            raise SystemExit("--score requires --ratings <path>")
        if args.judge_backend == "litellm" and not args.judge_model:
            raise SystemExit("--judge-backend litellm requires --judge-model")
        judge = build_judge_backend(args.judge_model or "stub", kind=args.judge_backend)
        report = score_ratings(Path(args.ratings), judge, repeats=args.judge_repeats,
                                temperature=args.judge_temperature)
        print(json.dumps(report, indent=2))
        if args.report_out:
            Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report_out).write_text(json.dumps(report, indent=2))
            print(f"\nWrote {args.report_out}")
        if args.judge_backend == "stub":
            print(
                "\nNOTE: this used --judge-backend stub. The agreement numbers above prove the "
                "pipeline runs end to end; they are NOT a real calibration figure -- StubJudge has "
                "no real language understanding (see llm_judge.py). Re-run with --judge-backend "
                "litellm and a real --judge-model before reporting this in the paper."
            )
        return


if __name__ == "__main__":
    main()
