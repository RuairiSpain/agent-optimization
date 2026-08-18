#!/usr/bin/env python3
"""
validate_candidate.py — gate an optimized prompt-agent candidate against its expectations contract.

FIXES applied vs the v1 pack (see ../CHANGELOG.md):
  - Reads the agent's dataset_split + judge_config from expectations.json and REFUSES to run
    if the candidate was produced using the holdout file (leakage guard — pass --candidate-source
    to declare which split informed the candidate; anything other than "optimize" for the
    optimization step itself raises).
  - Deterministic rule types (regex / all_of_regex / any_of_regex / absent) are scored automatically.
  - "semantic" rule types are NEVER silently passed. By default (no --judge-backend) they are
    collected into an UNJUDGED queue that must be resolved by a human before promotion — agents
    04/06/07/08/10 are mostly semantic gaps, and a validator that silently passed semantic rules
    would report even a bad baseline as promotable. Passing --judge-backend resolves them with an
    LLM judge instead (see judge_config in expectations.json and llm_judge.py's module docstring
    for the self-preference-bias / repeats / agreement-tracking design this respects).
  - Emits a machine-readable JSON report suitable for feeding into the notebooks' run manifests.

Usage:
    # Deterministic-only (original behavior, no judge, no new dependency):
    python validate_candidate.py --agent 01-travel-approval-strict --candidate path/to/instructions.md

    # Zero-cost judge-layer smoke test (StubJudge — proves the plumbing, not judge quality):
    python validate_candidate.py --agent 05-clinical-triage-safety --candidate cand.md \\
        --judge-backend stub

    # Real judge resolution, using the agent's own judge_config defaults, plus a cross-judge run
    # to measure self-preference agreement:
    python validate_candidate.py --agent 04-hr-policy-mcp --candidate cand.md \\
        --judge-backend litellm --cross-judge --json report.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from llm_judge import JudgeAgreementTracker, build_judge_backend, judge_semantic_rule

SEVERITY_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def load_expectations(agent_dir: Path) -> dict:
    path = agent_dir / "expected" / "expectations.json"
    if not path.exists():
        raise SystemExit(f"No expectations.json found at {path}")
    return json.loads(path.read_text())


def eval_match(match: dict, text: str, judge=None, cross_judge=None, repeats: int = 1,
               temperature: float = 0.0, agreement_tracker: "JudgeAgreementTracker | None" = None) -> "tuple[str, str]":
    """Returns (status, detail). status in {PASS, FAIL, UNJUDGED}.

    judge=None (default) preserves the original, fully deterministic, zero-dependency behavior:
    semantic rules come back UNJUDGED. Pass a JudgeBackend (see llm_judge.py) to resolve them
    instead; pass cross_judge too (with agreement_tracker) to additionally record a same-family
    cross-judge verdict for later corpus-level agreement reporting.
    """
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
        statement = match.get("statement", "(no statement provided)")
        if judge is None:
            return "UNJUDGED", statement
        verdict = judge_semantic_rule(statement, text, judge, repeats=repeats, temperature=temperature)
        detail = f"[judged by {judge.model_name}, {verdict.repeats} repeat(s), votes={verdict.raw_votes}] {statement}"
        if cross_judge is not None:
            cross_verdict = judge_semantic_rule(statement, text, cross_judge, repeats=repeats, temperature=temperature)
            if agreement_tracker is not None:
                agreement_tracker.add_binary(bool(verdict.passed), bool(cross_verdict.passed))
            detail += f" [cross-judge {cross_judge.model_name}: {'PASS' if cross_verdict.passed else 'FAIL'}]"
        return ("PASS" if verdict.passed else "FAIL"), detail
    return "UNJUDGED", f"unknown match type: {mtype}"


def validate(expectations: dict, candidate_text: str, judge=None, cross_judge=None,
             repeats: int = 1, temperature: float = 0.0) -> dict:
    rules = expectations["instruction_rules"]
    agreement_tracker = JudgeAgreementTracker() if (judge is not None and cross_judge is not None) else None
    report = {"agent_id": expectations["agent_id"], "sections": {}, "unjudged": [], "critical_failures": [],
              "judge_used": judge.model_name if judge is not None else None,
              "cross_judge_used": cross_judge.model_name if cross_judge is not None else None}

    def _eval(match):
        return eval_match(match, candidate_text, judge=judge, cross_judge=cross_judge,
                           repeats=repeats, temperature=temperature, agreement_tracker=agreement_tracker)

    for section in ["must_have", "nice_to_have", "should_remove", "should_add", "must_not_appear"]:
        items = rules.get(section, [])
        results = []
        for item in items:
            status, detail = _eval(item["match"])
            results.append({"id": item["id"], "severity": item["severity"], "status": status, "detail": detail})
            if status == "UNJUDGED":
                report["unjudged"].append({"section": section, "id": item["id"], "statement": detail})
            if status == "FAIL" and item["severity"] == "critical":
                report["critical_failures"].append({"section": section, "id": item["id"], "detail": detail})
        report["sections"][section] = results

    should_edit_results = []
    for item in rules.get("should_edit", []):
        status, detail = _eval(item["accept_if"])
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
    if agreement_tracker is not None:
        report["primary_cross_judge_agreement"] = agreement_tracker.summary()
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
    ap.add_argument("--judge-backend", choices=["none", "stub", "litellm"], default="none",
                     help="'none' (default) leaves semantic rules UNJUDGED exactly as before. 'stub' "
                          "resolves them with a zero-cost, zero-network heuristic for offline smoke "
                          "testing ONLY — never treat its verdicts as evidence. 'litellm' makes real "
                          "judge calls (needs 'pip install litellm' and a provider API key).")
    ap.add_argument("--judge-model", default=None,
                     help="overrides judge_config.primary_judge_model from expectations.json")
    ap.add_argument("--cross-judge", action="store_true",
                     help="also run judge_config.cross_judge_model (or --cross-judge-model) in "
                          "parallel and report corpus-level primary/cross agreement (Cohen's kappa) "
                          "— the self-preference-bias check. Requires --judge-backend != none.")
    ap.add_argument("--cross-judge-model", default=None,
                     help="overrides judge_config.cross_judge_model from expectations.json")
    ap.add_argument("--judge-repeats", type=int, default=None,
                     help="overrides judge_config.repeats_per_item")
    ap.add_argument("--judge-temperature", type=float, default=None,
                     help="overrides judge_config.inference_temperature")
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

    judge = cross_judge = None
    repeats = 1
    temperature = 0.0
    if args.judge_backend != "none":
        jc = expectations.get("judge_config", {})
        repeats = args.judge_repeats if args.judge_repeats is not None else jc.get("repeats_per_item", 1)
        temperature = args.judge_temperature if args.judge_temperature is not None else jc.get("inference_temperature", 0.0)
        judge_model = args.judge_model or jc.get("primary_judge_model")
        judge = build_judge_backend(judge_model, kind=args.judge_backend)
        if args.cross_judge:
            if args.judge_backend == "stub":
                raise SystemExit("--cross-judge with --judge-backend stub is a no-op (StubJudge is "
                                  "the same deterministic heuristic regardless of model name) — omit "
                                  "--cross-judge for a stub smoke test.")
            cross_model = args.cross_judge_model or jc.get("cross_judge_model")
            cross_judge = build_judge_backend(cross_model, kind=args.judge_backend)

    report = validate(expectations, candidate_text, judge=judge, cross_judge=cross_judge,
                       repeats=repeats, temperature=temperature)

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
    if "primary_cross_judge_agreement" in report:
        agr = report["primary_cross_judge_agreement"]
        print(f"\nPrimary/cross-judge agreement over {agr['n_binary_pairs']} semantic rule(s): "
              f"Cohen's kappa = {agr['cohens_kappa_binary']}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))

    sys.exit(1 if report["blocked"] else 0)


if __name__ == "__main__":
    main()
