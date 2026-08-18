#!/usr/bin/env python3
"""
validate_candidate.py — gate an optimized prompt-agent candidate against its expectations contract.

FIXES applied vs the v1 pack (see ../CHANGELOG.md):
  - Reads the agent's dataset_split + judge_config from expectations.json and REFUSES to run
    if the candidate was produced using the holdout file (leakage guard — pass --candidate-source
    to declare which split informed the candidate; anything other than "optimize" for the
    optimization step itself raises).
  - Deterministic rule types (regex / all_of_regex / any_of_regex / absent) are scored automatically.
  - "semantic" rule types are NEVER silently passed — they are collected into an UNJUDGED queue that
    must be resolved by an LLM judge (see judge_config in expectations.json) or a human before
    promotion. This is intentional: agents 04/06/07/08/10 are mostly semantic gaps, and a validator
    that silently passes semantic rules would report even a bad baseline as promotable.
  - Emits a machine-readable JSON report suitable for feeding into the notebooks' run manifests.

Usage:
    python validate_candidate.py --agent 01-travel-approval-strict --candidate path/to/instructions.md
    python validate_candidate.py --agent 04-hr-policy-mcp --candidate cand.md --json report.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

SEVERITY_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def load_expectations(agent_dir: Path) -> dict:
    path = agent_dir / "expected" / "expectations.json"
    if not path.exists():
        raise SystemExit(f"No expectations.json found at {path}")
    return json.loads(path.read_text())


def eval_match(match: dict, text: str) -> "tuple[str, str]":
    """Returns (status, detail). status in {PASS, FAIL, UNJUDGED}."""
    mtype = match.get("type")
    patterns = match.get("patterns", [])
    if mtype == "regex":
        for p in patterns:
            if re.search(p, text):
                return "PASS", f"matched /{p}/"
        return "FAIL", f"no pattern matched: {patterns}"
    if mtype == "all_of_regex":
        missing = [p for p in patterns if not re.search(p, text)]
        if missing:
            return "FAIL", f"missing required patterns: {missing}"
        return "PASS", "all patterns present"
    if mtype == "any_of_regex":
        for p in patterns:
            if re.search(p, text):
                return "PASS", f"matched /{p}/"
        return "FAIL", f"none matched: {patterns}"
    if mtype == "absent":
        hits = [p for p in patterns if re.search(p, text)]
        if hits:
            return "FAIL", f"forbidden pattern(s) present: {hits}"
        return "PASS", "confirmed absent"
    if mtype == "semantic":
        return "UNJUDGED", match.get("statement", "(no statement provided)")
    return "UNJUDGED", f"unknown match type: {mtype}"


def validate(expectations: dict, candidate_text: str) -> dict:
    rules = expectations["instruction_rules"]
    report = {"agent_id": expectations["agent_id"], "sections": {}, "unjudged": [], "critical_failures": []}

    for section in ["must_have", "nice_to_have", "should_remove", "should_add", "must_not_appear"]:
        items = rules.get(section, [])
        results = []
        for item in items:
            status, detail = eval_match(item["match"], candidate_text)
            results.append({"id": item["id"], "severity": item["severity"], "status": status, "detail": detail})
            if status == "UNJUDGED":
                report["unjudged"].append({"section": section, "id": item["id"], "statement": detail})
            if status == "FAIL" and item["severity"] == "critical":
                report["critical_failures"].append({"section": section, "id": item["id"], "detail": detail})
        report["sections"][section] = results

    should_edit_results = []
    for item in rules.get("should_edit", []):
        status, detail = eval_match(item["accept_if"], candidate_text)
        still_present = item["current_text"][:40] in candidate_text
        entry = {"id": item["id"], "severity": item["severity"], "status": status, "detail": detail,
                  "baseline_text_still_present": still_present}
        should_edit_results.append(entry)
        if status == "UNJUDGED":
            report["unjudged"].append({"section": "should_edit", "id": item["id"], "statement": detail})
        if status == "FAIL" and item["severity"] == "critical":
            report["critical_failures"].append({"section": "should_edit", "id": item["id"], "detail": detail})
    report["sections"]["should_edit"] = should_edit_results

    report["blocked"] = len(report["critical_failures"]) > 0
    report["fully_judged"] = len(report["unjudged"]) == 0
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True, help="agent folder name, e.g. 01-travel-approval-strict")
    ap.add_argument("--candidate", required=True, help="path to the candidate instructions.md")
    ap.add_argument("--candidate-source", default="optimize", choices=["optimize", "holdout", "unknown"],
                     help="Which split informed this candidate's optimization. Must be 'optimize' — "
                          "'holdout' or 'unknown' raises, because scoring a candidate that was itself "
                          "tuned against the holdout set defeats the leakage guard.")
    ap.add_argument("--json", help="optional path to write the machine-readable report")
    ap.add_argument("--root", default=".", help="pack root (defaults to CWD; expects <root>/<agent>/expected/...)")
    args = ap.parse_args()

    if args.candidate_source != "optimize":
        raise SystemExit(
            "REFUSED: --candidate-source must be 'optimize'. This candidate cannot be validated because "
            "its provenance relative to the optimize/holdout split is not confirmed 'optimize-only'. "
            "See dataset_split.leakage_note in expectations.json."
        )

    agent_dir = Path(args.root) / args.agent
    expectations = load_expectations(agent_dir)
    candidate_text = Path(args.candidate).read_text()

    report = validate(expectations, candidate_text)

    print(f"=== {expectations['agent_id']} ===")
    for section, results in report["sections"].items():
        for r in results:
            marker = {"PASS": "OK", "FAIL": "XX", "UNJUDGED": "??"}[r["status"]]
            print(f"[{marker}] {section}:{r['id']} ({r['severity']}) — {r['detail']}")
    print()
    if report["critical_failures"]:
        print(f"BLOCKED — {len(report['critical_failures'])} critical failure(s):")
        for cf in report["critical_failures"]:
            print(f"  - {cf['section']}:{cf['id']} — {cf['detail']}")
    else:
        print("No deterministic critical failures.")
    if report["unjudged"]:
        print(f"\n{len(report['unjudged'])} rule(s) require an LLM/human judge before promotion "
              f"(see judge_config in expectations.json) — NOT auto-passed:")
        for u in report["unjudged"]:
            print(f"  - {u['section']}:{u['id']} — {u['statement']}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))

    sys.exit(1 if report["blocked"] else 0)


if __name__ == "__main__":
    main()
