#!/usr/bin/env python3
"""
score_sensitivity.py — composite-score weight sensitivity / robustness analysis.

Reviewer finding (an external journal review of paper-v3.md — a separate review from this project's
own agent-paper-reviewer skill rounds 1/2; see docs/paper/publication-plan.md item #3): the severity
weights, per-item penalties, and floor in score_response (metric.py) were pre-registered but never
checked for robustness — a different, equally defensible choice of weights could in principle
re-rank which system looks better on a given agent, and nothing in the paper showed that doesn't
happen.

This script answers that directly, and cheaply: it re-scores ALREADY-CAPTURED (query, response,
tool_calls) triples from a run's holdout_eval.json under a grid of perturbed weight tables (see
metric.DEFAULT_WEIGHTS for the shape), using the SAME score_response function every other number in
this pack uses — no reimplementation, no new LM calls, no new optimization runs. It answers
"would a different reasonable weight choice have changed our conclusion," not "is our weight choice
correct" (there is no ground truth for that; see docs/paper/paper-v4.md Section 8 for the honest
scope of what this can and can't establish).

SCOPE AS BUILT: only DSPy holdout_eval.json logs exist today (Foundry's response-level scoring path
doesn't exist yet — see docs/paper/paper-v4.md Section 5.3/8). This script therefore reports
per-agent, per-run robustness for the DSPy track only. Once the Foundry response-level harness
(paper-v4.md Section 9) exists and produces a per-row log in the same {id, query, response, tool_calls}
shape, point --results-dir at wherever it writes and this script covers both tracks unchanged — the
grid, the aggregation, and the reported statistic don't need to change, only the log source does.

Usage:
    # Sweep the default grid over every holdout_eval.json under results/:
    python score_sensitivity.py --results-dir results

    # Narrower sweep, one agent:
    python score_sensitivity.py --results-dir results --agent 01-travel-approval-strict
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from agent_loader import ALL_AGENT_IDS, load_agent
from metric import DEFAULT_WEIGHTS, score_response

# The perturbation grid. Each entry is a (label, partial-override) pair; "baseline" (no override)
# is always included first so every other config's delta is reported relative to it. Ranges chosen
# per docs/paper/publication-plan.md item #3: severity weights +/-25%, floor at two alternatives to
# the pre-registered 0.15, judge_weight at three alternatives (applied separately, see
# --judge-weight-grid below, only when a log has cached rubric_score values).
def _scaled_severity(factor: float) -> dict:
    return {k: round(v * factor, 4) for k, v in DEFAULT_WEIGHTS["severity"].items()}


DEFAULT_GRID: list[tuple[str, dict]] = [
    ("baseline (pre-registered weights)", {}),
    ("severity -25%", {"severity": _scaled_severity(0.75)}),
    ("severity +25%", {"severity": _scaled_severity(1.25)}),
    ("must_contain/must_not_contain -25%",
     {"must_contain_missing": round(DEFAULT_WEIGHTS["must_contain_missing"] * 0.75, 4),
      "must_not_contain_present": round(DEFAULT_WEIGHTS["must_not_contain_present"] * 0.75, 4)}),
    ("must_contain/must_not_contain +25%",
     {"must_contain_missing": round(DEFAULT_WEIGHTS["must_contain_missing"] * 1.25, 4),
      "must_not_contain_present": round(DEFAULT_WEIGHTS["must_not_contain_present"] * 1.25, 4)}),
    ("tool-call penalties -25%",
     {"tool_required_full_miss": round(DEFAULT_WEIGHTS["tool_required_full_miss"] * 0.75, 4),
      "tool_required_partial_miss_per_tool": round(DEFAULT_WEIGHTS["tool_required_partial_miss_per_tool"] * 0.75, 4),
      "tool_forbidden_violation": round(DEFAULT_WEIGHTS["tool_forbidden_violation"] * 0.75, 4)}),
    ("tool-call penalties +25%",
     {"tool_required_full_miss": round(DEFAULT_WEIGHTS["tool_required_full_miss"] * 1.25, 4),
      "tool_required_partial_miss_per_tool": round(DEFAULT_WEIGHTS["tool_required_partial_miss_per_tool"] * 1.25, 4),
      "tool_forbidden_violation": round(DEFAULT_WEIGHTS["tool_forbidden_violation"] * 1.25, 4)}),
    ("regression_blocks floor 0.10", {"regression_blocks_floor": 0.10}),
    ("regression_blocks floor 0.20", {"regression_blocks_floor": 0.20}),
]

JUDGE_WEIGHT_GRID = [0.2, 0.4, 0.6]  # applied only where a row has a cached rubric_score


def _find_holdout_logs(results_dir: Path, agent_filter: str | None) -> list[tuple[str, str, Path]]:
    """Returns (agent_id, run_label, path) for every results/<agent>/<run_label>/holdout_eval.json
    found. Also picks up baseline_holdout_eval.json if present (same shape, baseline instructions'
    responses) so the baseline side of a delta can be swept too."""
    found = []
    for agent_dir in sorted(results_dir.glob("*/")):
        agent_id = agent_dir.name
        if agent_id not in ALL_AGENT_IDS:
            continue
        if agent_filter and agent_id != agent_filter:
            continue
        for run_dir in sorted(agent_dir.glob("*/")):
            for fname in ("holdout_eval.json", "baseline_holdout_eval.json"):
                p = run_dir / fname
                if p.exists():
                    found.append((agent_id, f"{run_dir.name}/{fname}", p))
    return found


def sweep_one_log(log_path: Path, expectations: dict, judge_weight_grid: list[float]) -> dict:
    """Re-scores every per_row entry in one holdout_eval.json under DEFAULT_GRID (and, where a row
    has a cached rubric_score, under judge_weight_grid too), using the untouched captured
    query/response/tool_calls -- zero new LM calls. Returns per-config summary stats."""
    log = json.loads(log_path.read_text())
    rows = log.get("per_row", [])
    if not rows:
        return {"n_rows": 0, "note": "empty per_row -- nothing to sweep"}

    weight_results = {}
    for label, override in DEFAULT_GRID:
        scores = [
            score_response(r["query"], r["response"], r.get("tool_calls", []), expectations,
                            weights=override or None)
            for r in rows
        ]
        weight_results[label] = {
            "mean": round(statistics.mean(scores), 4),
            "stdev": round(statistics.stdev(scores), 4) if len(scores) > 1 else None,
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
        }

    baseline_mean = weight_results["baseline (pre-registered weights)"]["mean"]
    max_abs_delta = max(abs(v["mean"] - baseline_mean) for v in weight_results.values())

    result = {
        "n_rows": len(rows),
        "deterministic_weight_sweep": weight_results,
        "deterministic_max_abs_mean_delta_from_baseline": round(max_abs_delta, 4),
    }

    judge_rows = [r for r in rows if r.get("rubric_score") is not None]
    if judge_rows:
        jw_results = {}
        for jw in judge_weight_grid:
            blended = [(1 - jw) * r["deterministic_score"] + jw * r["rubric_score"] for r in judge_rows]
            jw_results[jw] = round(statistics.mean(blended), 4)
        result["judge_weight_sweep"] = {
            "n_rows_with_cached_rubric_score": len(judge_rows),
            "mean_by_judge_weight": jw_results,
            "max_abs_delta_across_judge_weight_grid": round(max(jw_results.values()) - min(jw_results.values()), 4),
        }
    else:
        result["judge_weight_sweep"] = {"note": "no cached rubric_score on any row -- this log was "
                                                 "scored deterministic-only; judge_weight has no effect to sweep"}
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--agent", default=None, help="restrict to one agent id, e.g. 01-travel-approval-strict")
    ap.add_argument("--out", default=None, help="write full JSON report here (default: print to stdout only)")
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    logs = _find_holdout_logs(results_dir, args.agent)
    if not logs:
        print(f"No holdout_eval.json / baseline_holdout_eval.json found under {results_dir}/. "
              "Run run_mipro_baseline.py first (a --dry-run smoke test is enough to exercise this "
              "script structurally, though its per-row scores are stub-LM output, not real data).")
        return

    report: dict[str, Any] = {"grid_config": [label for label, _ in DEFAULT_GRID],
                               "judge_weight_grid": JUDGE_WEIGHT_GRID, "logs": {}}
    agent_cache: dict[str, dict] = {}
    print(f"{'agent':<34} {'log':<40} {'rows':>5} {'max |Δmean| (weights)':>24} {'max |Δmean| (judge_w)':>24}")
    for agent_id, log_name, path in logs:
        if agent_id not in agent_cache:
            agent_cache[agent_id] = load_agent(agent_id).expectations
        result = sweep_one_log(path, agent_cache[agent_id], JUDGE_WEIGHT_GRID)
        report["logs"].setdefault(agent_id, {})[log_name] = result
        jw_delta = result.get("judge_weight_sweep", {}).get("max_abs_delta_across_judge_weight_grid")
        jw_str = f"{jw_delta:.4f}" if jw_delta is not None else "n/a"
        w_delta = result.get("deterministic_max_abs_mean_delta_from_baseline")
        w_str = f"{w_delta:.4f}" if w_delta is not None else "n/a"
        print(f"{agent_id:<34} {log_name:<40} {result.get('n_rows', 0):>5} {w_str:>24} {jw_str:>24}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"\nWrote full report to {args.out}")

    print(
        "\nHow to read this: 'max |Δmean|' is how far a per-agent, per-run mean score can move "
        "away from the pre-registered baseline weights across the perturbation grid, holding the "
        "captured responses/tool calls fixed. A large delta on an agent whose Table 3/Table 4 "
        "conclusion (paper-v4.md) is close to a threshold means that conclusion is weight-sensitive "
        "and should be reported with that caveat; a small delta across the whole grid is evidence "
        "the conclusion is robust to reasonable disagreement about the exact weights. This script "
        "does not and cannot show the weights are 'correct' -- only that a documented family of "
        "alternatives does or doesn't change what the paper would report."
    )


if __name__ == "__main__":
    main()
