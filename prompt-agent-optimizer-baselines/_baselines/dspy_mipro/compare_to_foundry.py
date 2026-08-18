#!/usr/bin/env python3
"""
compare_to_foundry.py — merge DSPy MIPROv2 baseline results with Foundry optimizer run manifests
into one comparison table.

Foundry side: expects one run_manifest.json per run at
    <pack_root>/runs/<agent_id>/<run_label>.manifest.json
matching the shape of _tools/run_manifest_template.json (this is the convention
expected_json.run_manifest_ref points at in each agent's expected/expectations.json). If no Foundry
manifests exist yet at that path (e.g. no portal access in this environment), this script still
produces the DSPy-only half of the table and says so explicitly — it never fabricates a Foundry
number to fill the gap.

Statistics: pure Python, no numpy/scipy dependency (neither is installed in this environment).
Reports mean, sample stdev, and a percentile BOOTSTRAP 95% CI (resampled with replacement over the
replicate seeds actually run) rather than a normal-approximation CI, since replicate counts here are
typically small (k=3-5) and bootstrap percentile CIs don't assume normality. This is a deliberate
answer to the earlier review finding that "elect best of two runs" and single-draw comparisons are
not statistically meaningful — this script only reports a distribution once >=2 replicate seeds
exist for a cell, and says so when fewer are available.

Usage:
    python compare_to_foundry.py --results-dir results --pack-root ../.. --out comparison.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

from agent_loader import ALL_AGENT_IDS


def load_dspy_runs(results_dir: Path) -> dict[str, list[dict]]:
    by_agent: dict[str, list[dict]] = {aid: [] for aid in ALL_AGENT_IDS}
    for agent_dir in sorted(results_dir.glob("*/")):
        agent_id = agent_dir.name
        if agent_id not in by_agent:
            continue
        for run_dir in sorted(agent_dir.glob("*/")):
            manifest_path = run_dir / "run_manifest.json"
            if manifest_path.exists():
                by_agent[agent_id].append(json.loads(manifest_path.read_text()))
    return by_agent


def load_foundry_runs(pack_root: Path) -> dict[str, list[dict]]:
    by_agent: dict[str, list[dict]] = {aid: [] for aid in ALL_AGENT_IDS}
    runs_dir = pack_root / "runs"
    if not runs_dir.exists():
        return by_agent
    for agent_dir in sorted(runs_dir.glob("*/")):
        agent_id = agent_dir.name
        if agent_id not in by_agent:
            continue
        for manifest_path in sorted(agent_dir.glob("*.manifest.json")):
            by_agent[agent_id].append(json.loads(manifest_path.read_text()))
    return by_agent


def bootstrap_ci(values: list[float], n_resamples: int = 2000, seed: int = 7) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return (lo, hi)


def summarize(values: list[float]) -> dict:
    if not values:
        # Same key shape as the non-empty branch below (ci95_bootstrap, not ci95) -- a caller (e.g.
        # main()'s print loop) that only checks one key name must not have to special-case "0
        # values" separately from "1+ values".
        return {"n": 0, "mean": None, "stdev": None, "ci95_bootstrap": None, "note": "no runs available"}
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else None
    ci = bootstrap_ci(values)
    note = "single run — no distribution, do not read as representative" if len(values) == 1 else None
    return {"n": len(values), "mean": round(mean, 4), "stdev": round(stdev, 4) if stdev is not None else None,
            "ci95_bootstrap": [round(ci[0], 4), round(ci[1], 4)] if ci else None, "note": note}


def foundry_holdout_scores(manifests: list[dict]) -> tuple[list[float], int]:
    """Foundry run manifests only carry a holdout-comparable score once a response-level scoring
    harness — one that runs the exported/deployed candidate against dataset/holdout.jsonl and scores
    its real responses with the shared score_response function — writes
    outputs.holdout_composite_score. That harness does not exist in this pack yet (see
    docs/paper/review-round-2.md Weakness 1 and docs/paper/paper-v4.md Sec 5.2/8): the Optimize
    wizard's own outputs.composite_score is a different, in-sample number computed against whatever
    was uploaded to the wizard (dataset/optimize.jsonl, per experiment-runbook.md Step 3) — it is not
    a holdout score and is never substituted here, even though the two fields can look
    interchangeable. Returns (scores, n_in_sample_only) so callers can report, rather than silently
    absorb, manifests that have an in-sample score but no genuine holdout score."""
    scores = []
    n_in_sample_only = 0
    for m in manifests:
        outputs = m.get("outputs", {})
        v = outputs.get("holdout_composite_score")
        if v is not None:
            scores.append(v)
        elif outputs.get("composite_score") is not None:
            n_in_sample_only += 1
    return scores, n_in_sample_only


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--pack-root", default="../..")
    ap.add_argument("--out", default="results/comparison.json")
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    pack_root = (Path(__file__).parent / args.pack_root).resolve()

    dspy_runs = load_dspy_runs(results_dir)
    foundry_runs = load_foundry_runs(pack_root)

    table = {}
    for agent_id in ALL_AGENT_IDS:
        dspy_manifests = dspy_runs[agent_id]
        foundry_manifests = foundry_runs[agent_id]

        dspy_deltas = [m["outputs"]["holdout_delta"] for m in dspy_manifests]
        dspy_optimized = [m["outputs"]["optimized_holdout_mean_score"] for m in dspy_manifests]
        dspy_blocked = [m["outputs"]["optimized_instruction_report_blocked"] for m in dspy_manifests]
        dspy_growth = [m["outputs"]["instruction_growth_ratio_words_approx"] for m in dspy_manifests]
        # est_cost_growth_ratio is None whenever --task-lm wasn't in model_pricing.PRICE_TABLE (or
        # under --dry-run) -- filter those out rather than let a None poison the mean, and report
        # how many manifests actually had a priced cost estimate.
        dspy_cost_growth_values = [m["outputs"].get("est_cost_growth_ratio") for m in dspy_manifests]
        dspy_cost_growth_priced = [v for v in dspy_cost_growth_values if v is not None]
        any_dry_run = any(m.get("dry_run") for m in dspy_manifests)

        foundry_scores, foundry_in_sample_only = foundry_holdout_scores(foundry_manifests)

        if not foundry_manifests:
            foundry_status = "no manifests found under <pack_root>/runs/{}/*.manifest.json".format(agent_id)
        elif not foundry_scores:
            # foundry_manifests is non-empty but foundry_holdout_scores() found no
            # outputs.holdout_composite_score on any of them: there is no response-level scoring
            # harness in this pack yet that runs the exported Foundry candidate against
            # dataset/holdout.jsonl and scores it with score_response (see docs/paper/paper-v4.md
            # Sec 5.2/8 and docs/paper/review-round-2.md). We report that gap instead of silently
            # filling it with the wizard's own in-sample composite_score.
            foundry_status = (
                f"{len(foundry_manifests)} manifest(s) found but none has "
                "outputs.holdout_composite_score set (a response-level, holdout-scored harness for "
                "the Foundry track does not exist in this pack yet). "
                f"{foundry_in_sample_only} of them report an in-sample outputs.composite_score from "
                "the Optimize wizard instead — that number is intentionally NOT used here, since it "
                "is not comparable to the DSPy track's holdout-only score."
            )
        else:
            foundry_status = "OK"

        table[agent_id] = {
            "dspy_mipro_v2": {
                "n_runs": len(dspy_manifests),
                "contains_dry_run_data": any_dry_run,
                "holdout_delta": summarize(dspy_deltas),
                "optimized_holdout_score": summarize(dspy_optimized),
                "instruction_blocked_rate": (sum(dspy_blocked) / len(dspy_blocked)) if dspy_blocked else None,
                "instruction_growth_ratio": summarize(dspy_growth),
                "est_cost_growth_ratio": summarize(dspy_cost_growth_priced),
                "n_runs_missing_cost_estimate": len(dspy_manifests) - len(dspy_cost_growth_priced),
            },
            "foundry_optimizer": {
                "n_runs": len(foundry_manifests),
                "n_in_sample_only_no_holdout_score": foundry_in_sample_only,
                "holdout_score": summarize(foundry_scores),
                "est_cost_growth_ratio": summarize(
                    [m["outputs"]["est_cost_growth_ratio"] for m in foundry_manifests
                     if m.get("outputs", {}).get("est_cost_growth_ratio") is not None]
                ),
                "status": foundry_status,
            },
        }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(table, indent=2))

    print(f"{'agent':<34} {'dspy n':>7} {'dspy Δ (mean±95%CI)':>28} {'foundry n':>10} {'foundry score':>16}")
    for agent_id, row in table.items():
        d = row["dspy_mipro_v2"]["holdout_delta"]
        d_str = f"{d['mean']:+.3f} [{d['ci95_bootstrap'][0]:+.3f},{d['ci95_bootstrap'][1]:+.3f}]" if d["ci95_bootstrap"] else (f"{d['mean']:+.3f} (n=1)" if d["mean"] is not None else "—")
        f = row["foundry_optimizer"]["holdout_score"]
        f_str = f"{f['mean']:.3f}" if f["mean"] is not None else "—"
        dry_flag = " [DRY-RUN]" if row["dspy_mipro_v2"]["contains_dry_run_data"] else ""
        print(f"{agent_id:<34} {row['dspy_mipro_v2']['n_runs']:>7} {d_str:>28} {row['foundry_optimizer']['n_runs']:>10} {f_str:>16}{dry_flag}")

    print(f"\nWrote {args.out}")
    if all(row["foundry_optimizer"]["n_runs"] == 0 for row in table.values()):
        print("\nNo Foundry run manifests found anywhere under <pack_root>/runs/. This table is "
              "DSPy-only until Foundry portal runs are executed and their manifests placed at "
              "<pack_root>/runs/<agent_id>/<run_label>.manifest.json (see _tools/run_manifest_template.json).")
    elif any(row["foundry_optimizer"]["n_in_sample_only_no_holdout_score"] for row in table.values()):
        print("\nSome Foundry manifests exist but have no outputs.holdout_composite_score — this pack "
              "does not yet include a harness that scores an exported Foundry candidate's real "
              "holdout responses with score_response. Their foundry_optimizer.holdout_score is "
              "correctly empty rather than backfilled from the wizard's in-sample composite_score; "
              "see each agent's foundry_optimizer.status for details.")


if __name__ == "__main__":
    main()
