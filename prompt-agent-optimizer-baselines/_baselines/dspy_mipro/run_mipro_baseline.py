#!/usr/bin/env python3
"""
run_mipro_baseline.py — run DSPy's MIPROv2 optimizer against one agent from the
foundry-prompt-agent-optimizer-baselines pack, as an open, reproducible comparison point for the
Foundry (closed, hosted) optimizer track.

Comparability with the Foundry track, by construction:
  - Reads the SAME agent.yaml / instructions.md / tools.json / dataset splits / expectations.json
    as the Foundry track (agent_loader.py).
  - Optimizes ONLY against dataset/optimize.jsonl, internally re-split into a train/val slice by
    --seed. dataset/holdout.jsonl is NEVER passed to MIPROv2 — it is used exclusively for the final
    holdout_eval.json this script writes, exactly mirroring the leakage guard in
    _tools/build_foundry_dataset.py / _tools/validate_candidate.py.
  - The final optimized instructions are graded with the SAME must_have/should_remove/
    must_not_appear contract via metric.instruction_level_report, which imports
    _tools/validate_candidate.py directly rather than reimplementing it.
  - Writes a run_manifest.json in the same shape as _tools/run_manifest_template.json so DSPy and
    Foundry runs can sit in one results table (see compare_to_foundry.py).

KNOWN LIMITATION (see agent_loader.py docstring): for 04-hr-policy-mcp and 07-incident-response-mcp,
only the function-calling tools are wired — there is no real MCP server here to call, so this
baseline evaluates those two agents on an instructions-(+function-tools)-only basis. Never read a
DSPy-vs-Foundry delta on 04/07 as a like-for-like MCP-retrieval comparison.

Usage:
    # Zero-cost, zero-API smoke test of the whole pipeline (produces no meaningful optimization):
    python run_mipro_baseline.py --agent 06-sales-brief-underspecified --dry-run

    # Real run (requires an LM the installed litellm/dspy can reach, and its API key in the env):
    python run_mipro_baseline.py --agent 01-travel-approval-strict --seed 0 \\
        --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import dspy

from agent_loader import load_agent
from dspy_program import build_module, get_program_instructions
from metric import build_response_metric, instruction_level_report, score_response
from mock_tools import get_call_log, reset_call_log
from stub_lm import StubLM


def split_optimize_rows(rows: list, seed: int, val_fraction: float) -> tuple[list, list]:
    rng = random.Random(seed)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    n_val = max(1, round(len(shuffled) * val_fraction))
    return shuffled[n_val:], shuffled[:n_val]  # train, val


def rows_to_examples(rows: list) -> list[dspy.Example]:
    return [dspy.Example(query=r.query).with_inputs("query") for r in rows]


def evaluate_on_rows(program, rows, expectations) -> dict:
    per_row = []
    for row in rows:
        reset_call_log()
        try:
            pred = program(query=row.query)
            response_text = getattr(pred, "response", None)
            if response_text is None:
                response_text = str(pred)
        except Exception as e:  # keep going — one bad row shouldn't kill the whole eval
            response_text = f"[PROGRAM ERROR: {type(e).__name__}: {e}]"
        tool_calls = list(get_call_log())
        score = score_response(row.query, response_text, tool_calls, expectations)
        per_row.append({"id": row.id, "query": row.query, "response": response_text,
                         "tool_calls": tool_calls, "score": score})
    mean_score = sum(r["score"] for r in per_row) / len(per_row) if per_row else 0.0
    return {"per_row": per_row, "mean_score": mean_score, "n": len(per_row)}


def approx_token_count(text: str) -> int:
    """Word-count proxy for token count — no tokenizer dependency. Documented as approximate;
    good enough for a growth RATIO, not for an absolute cost figure."""
    return len(text.split())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", required=True, help="agent folder name, e.g. 01-travel-approval-strict")
    ap.add_argument("--seed", type=int, default=0, help="controls the train/val split of optimize.jsonl and MIPROv2's own search seed")
    ap.add_argument("--run-label", default=None, help="defaults to seed<N>")
    ap.add_argument("--task-lm", default=None, help="dspy.LM model string for the program being optimized (e.g. openai/gpt-4.1-mini). Required unless --dry-run.")
    ap.add_argument("--prompt-lm", default=None, help="dspy.LM model string MIPROv2 uses to propose new instructions. Defaults to --task-lm.")
    ap.add_argument("--auto", choices=["light", "medium", "heavy"], default="light", help="MIPROv2 search budget")
    ap.add_argument("--num-threads", type=int, default=4)
    ap.add_argument("--val-fraction", type=float, default=0.3, help="fraction of optimize.jsonl held back as MIPROv2's OWN internal valset — distinct from, and always in addition to, dataset/holdout.jsonl")
    ap.add_argument("--dry-run", action="store_true", help="use a zero-cost stub LM to smoke-test the pipeline end to end; produces no meaningful optimization, only proves the wiring works")
    ap.add_argument("--root", default="../..", help="pack root, relative to this file's directory")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    if not args.dry_run and not args.task_lm:
        raise SystemExit("--task-lm is required unless --dry-run is set. See the module docstring for examples.")

    root = (Path(__file__).parent / args.root).resolve()
    spec = load_agent(args.agent, pack_root=root)
    run_label = args.run_label or f"seed{args.seed}"
    prompt_lm_name = args.prompt_lm or args.task_lm

    if args.dry_run:
        stub = StubLM(spec.baseline_instructions)
        task_lm, prompt_lm = stub, stub
        optimization_model_label = "stub-lm (offline smoke test — NOT a real model, no optimization quality claim)"
        eval_model_label = optimization_model_label
    else:
        task_lm = dspy.LM(model=args.task_lm)
        prompt_lm = dspy.LM(model=prompt_lm_name)
        optimization_model_label = prompt_lm_name
        eval_model_label = args.task_lm

    dspy.configure(lm=task_lm)

    module = build_module(spec)
    metric = build_response_metric(spec)

    train_rows, val_rows = split_optimize_rows(spec.optimize_rows, seed=args.seed, val_fraction=args.val_fraction)
    trainset, valset = rows_to_examples(train_rows), rows_to_examples(val_rows)

    teleprompter = dspy.teleprompt.MIPROv2(
        metric=metric, prompt_model=prompt_lm, task_model=task_lm,
        auto=args.auto, num_threads=args.num_threads, seed=args.seed, verbose=False,
    )

    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    compiled = teleprompter.compile(module, trainset=trainset, valset=valset, requires_permission_to_run=False)
    elapsed_seconds = round(time.time() - t0, 1)

    optimized_instructions = get_program_instructions(compiled)
    optimized_report = instruction_level_report(optimized_instructions, spec.expectations)
    baseline_report = instruction_level_report(spec.baseline_instructions, spec.expectations)

    # `module` is guaranteed untouched by compile() (MIPROv2 deep-copies internally), so it is a
    # valid same-pipeline, same-mocks baseline comparison point for the holdout evaluation.
    baseline_holdout = evaluate_on_rows(module, spec.holdout_rows, spec.expectations)
    optimized_holdout = evaluate_on_rows(compiled, spec.holdout_rows, spec.expectations)

    out_dir = Path(args.out_dir) / args.agent / run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "optimized_instructions.md").write_text(optimized_instructions)
    (out_dir / "instruction_report.json").write_text(json.dumps(optimized_report, indent=2))
    (out_dir / "baseline_instruction_report.json").write_text(json.dumps(baseline_report, indent=2))
    (out_dir / "holdout_eval.json").write_text(json.dumps(optimized_holdout, indent=2))
    (out_dir / "baseline_holdout_eval.json").write_text(json.dumps(baseline_holdout, indent=2))

    manifest = {
        "run_id": f"dspy-mipro-{args.agent}-{run_label}",
        "agent_id": args.agent,
        "run_label": run_label,
        "source": "dspy-mipro-v2",
        "dspy_version": dspy.__version__,
        "timestamp_utc": started_at,
        "elapsed_seconds": elapsed_seconds,
        "dry_run": args.dry_run,
        "optimization_model": {"name": optimization_model_label},
        "eval_model": {"name": eval_model_label},
        "wizard_config": {
            "teleprompter": "MIPROv2", "auto": args.auto, "seed": args.seed,
            "val_fraction": args.val_fraction, "trainset_size": len(trainset), "valset_size": len(valset),
        },
        "dataset": {
            "optimize_file": "dataset/optimize.jsonl",
            "holdout_file": "dataset/holdout.jsonl",
            "optimize_rows": len(spec.optimize_rows),
            "holdout_rows": len(spec.holdout_rows),
            "leakage_note": "holdout.jsonl is never passed to trainset/valset or to MIPROv2.compile() — see module docstring.",
        },
        "scope_note": spec.dspy_optimization_scope_note,
        "outputs": {
            "instruction_word_count_baseline": approx_token_count(spec.baseline_instructions),
            "instruction_word_count_optimized": approx_token_count(optimized_instructions),
            "instruction_growth_ratio_words_approx": round(
                approx_token_count(optimized_instructions) / max(1, approx_token_count(spec.baseline_instructions)), 3
            ),
            "baseline_instruction_report_blocked": baseline_report["blocked"],
            "optimized_instruction_report_blocked": optimized_report["blocked"],
            "baseline_instruction_critical_failures": len(baseline_report["critical_failures"]),
            "optimized_instruction_critical_failures": len(optimized_report["critical_failures"]),
            "baseline_holdout_mean_score": round(baseline_holdout["mean_score"], 4),
            "optimized_holdout_mean_score": round(optimized_holdout["mean_score"], 4),
            "holdout_delta": round(optimized_holdout["mean_score"] - baseline_holdout["mean_score"], 4),
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(json.dumps(manifest["outputs"], indent=2))
    print(f"\nWrote results to {out_dir}")


if __name__ == "__main__":
    main()
