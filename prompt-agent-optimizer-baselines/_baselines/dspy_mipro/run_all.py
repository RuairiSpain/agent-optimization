#!/usr/bin/env python3
"""
run_all.py — loop run_mipro_baseline.py over agents x replicate seeds, and aggregate into one
summary table.

Runs k >= 1 replicate seeds per agent by design (not a single Run1/Run2 pair) — this exists
specifically so a DSPy-side run-to-run distribution can be reported, rather than a single draw, per
the paper-readiness recommendation to avoid treating a single optimizer run as representative (see
root README's "improve the evaluation" discussion and CHANGELOG.md).

Usage:
    # Zero-cost smoke test across the whole pack:
    python run_all.py --agents all --seeds 0 1 2 --dry-run

    # Real run, one agent, 5 replicates:
    python run_all.py --agents 01-travel-approval-strict --seeds 0 1 2 3 4 \\
        --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agent_loader import ALL_AGENT_IDS

THIS_DIR = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", default=["all"], help="agent ids, or 'all'")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0], help="replicate seeds; use >=3 for a real distribution, not just one draw")
    ap.add_argument("--task-lm", default=None)
    ap.add_argument("--prompt-lm", default=None)
    ap.add_argument("--auto", default="light")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    agents = ALL_AGENT_IDS if args.agents == ["all"] else args.agents

    summary = []
    for agent in agents:
        for seed in args.seeds:
            cmd = [sys.executable, str(THIS_DIR / "run_mipro_baseline.py"),
                   "--agent", agent, "--seed", str(seed), "--auto", args.auto, "--out-dir", args.out_dir]
            if args.dry_run:
                cmd.append("--dry-run")
            else:
                cmd += ["--task-lm", args.task_lm, "--prompt-lm", args.prompt_lm or args.task_lm]
            print(f"\n>>> {agent} seed={seed}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FAILED (exit {result.returncode}):\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
                summary.append({"agent": agent, "seed": seed, "status": "FAILED"})
                continue
            manifest_path = Path(args.out_dir) / agent / f"seed{seed}" / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            row = {"agent": agent, "seed": seed, "status": "OK", **manifest["outputs"]}
            summary.append(row)
            print(f"OK — holdout {row['baseline_holdout_mean_score']:.3f} -> {row['optimized_holdout_mean_score']:.3f} "
                  f"(delta {row['holdout_delta']:+.3f})")

    out_path = Path(args.out_dir) / "summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    n_ok = sum(1 for r in summary if r["status"] == "OK")
    print(f"\n{n_ok}/{len(summary)} runs OK. Summary written to {out_path}")


if __name__ == "__main__":
    main()
