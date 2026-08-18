#!/usr/bin/env python3
"""
build_foundry_dataset.py — produce a portal-upload-ready file for the Foundry Optimize wizard.

FIX (leakage, review item #1): this script reads ONLY dataset/optimize.jsonl. It will refuse to
run against dataset/holdout.jsonl even if pointed at it explicitly, because the holdout split
exists specifically to never be seen by the optimizer — the whole point of the split is defeated
if this tool can upload it. The holdout file is consumed exclusively by the post-optimization
scoring notebook (07_evaluate_optimized_candidate.ipynb), never by the wizard.

The portal wizard has no column-mapping step, so the authoring fields (id, tags) are stripped and
only the columns the evaluator schema expects survive: query, ground_truth.

Usage:
    python build_foundry_dataset.py --agent 01-travel-approval-strict --out upload_01.jsonl
    python build_foundry_dataset.py --agent 04-hr-policy-mcp --format csv --out upload_04.csv
"""
import argparse
import csv
import json
from pathlib import Path

FORBIDDEN_BASENAME = "holdout.jsonl"


def load_rows(path: Path) -> list:
    if path.name == FORBIDDEN_BASENAME:
        raise SystemExit(
            f"REFUSED: {path} is the holdout split. It must never be uploaded to the optimizer wizard "
            f"— that would erase the optimize/holdout separation this pack relies on for unbiased "
            f"post-optimization scoring. Use dataset/optimize.jsonl instead."
        )
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def strip_authoring_fields(row: dict) -> dict:
    return {"query": row["query"], "ground_truth": row["ground_truth"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.root) / args.agent / "dataset" / "optimize.jsonl"
    rows = [strip_authoring_fields(r) for r in load_rows(src)]

    out = Path(args.out)
    if args.format == "jsonl":
        with out.open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    else:
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["query", "ground_truth"])
            w.writeheader()
            w.writerows(rows)

    print(f"Wrote {len(rows)} rows (optimize split only) to {out}")


if __name__ == "__main__":
    main()
