#!/usr/bin/env python3
"""
similarity_baseline.py — n-gram cosine similarity WITH a null distribution, plus a second,
expectations-grounded similarity axis.

FIXES applied (review items #5 and #3):
  1. A raw cosine number between two prompt texts is meaningless without something to compare it
     to. This script builds a null distribution by computing pairwise similarity across candidates
     drawn from DIFFERENT agents (which have no reason to be related) and reports where the
     within-agent run-to-run similarities fall relative to that null, plus a permutation test
     (shuffle word n-grams within each document, recompute) as a second null estimate.
  2. Lexical similarity conflates surface rewriting with substance. This script also reports
     "expectations agreement": the Jaccard overlap of which must_have/should_edit/should_remove/
     must_not_appear rule IDs each candidate PASSES (from validate_candidate.py JSON reports), so
     two runs that are lexically far apart but functionally identical are correctly flagged as
     substantively similar, and vice versa.

This is deliberately dependency-light (no sklearn/numpy required) so it runs anywhere the notebooks
run without an extra install step.

Usage:
    python similarity_baseline.py --texts baseline.md run1.md run2.md run3.md \
        --reports baseline_report.json run1_report.json run2_report.json run3_report.json \
        --null-texts ../02-support-triage-messy/instructions.md ../06-sales-brief-underspecified/instructions.md \
        --out similarity_report.json
"""
import argparse
import itertools
import json
import math
import random
import re
from collections import Counter
from pathlib import Path


def word_ngrams(text: str, n: int = 3) -> Counter:
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def permutation_null(text_a: str, text_b: str, n: int = 3, trials: int = 200, seed: int = 13) -> dict:
    """Shuffle the token order of each doc before n-gramming, breaking sequential structure while
    preserving vocabulary. Repeated trials give a null mean/std for 'similar vocabulary, unrelated
    order' — i.e. what cosine looks like when only word choice, not content, is shared."""
    rng = random.Random(seed)
    toks_a = re.findall(r"[a-z0-9']+", text_a.lower())
    toks_b = re.findall(r"[a-z0-9']+", text_b.lower())
    scores = []
    for _ in range(trials):
        ra = toks_a[:]
        rb = toks_b[:]
        rng.shuffle(ra)
        rng.shuffle(rb)
        ca = Counter(tuple(ra[i:i + n]) for i in range(len(ra) - n + 1))
        cb = Counter(tuple(rb[i:i + n]) for i in range(len(rb) - n + 1))
        scores.append(cosine(ca, cb))
    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / len(scores)
    return {"mean": mean, "std": math.sqrt(var), "trials": trials}


def cross_agent_null(paths: list) -> dict:
    texts = {p: Path(p).read_text() for p in paths}
    scores = []
    for a, b in itertools.combinations(texts, 2):
        scores.append(cosine(word_ngrams(texts[a]), word_ngrams(texts[b])))
    if not scores:
        return {"mean": None, "std": None, "n_pairs": 0}
    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / len(scores) if len(scores) > 1 else 0.0
    return {"mean": mean, "std": math.sqrt(var), "n_pairs": len(scores), "pairs": scores}


def expectations_agreement(report_paths: list) -> dict:
    """Jaccard overlap of PASSing rule IDs across candidate validation reports."""
    pass_sets = {}
    for p in report_paths:
        report = json.loads(Path(p).read_text())
        passing = set()
        for section, results in report["sections"].items():
            for r in results:
                if r["status"] == "PASS":
                    passing.add(f"{section}:{r['id']}")
        pass_sets[p] = passing
    pairwise = {}
    for a, b in itertools.combinations(pass_sets, 2):
        sa, sb = pass_sets[a], pass_sets[b]
        union = sa | sb
        jaccard = len(sa & sb) / len(union) if union else 1.0
        pairwise[f"{a} vs {b}"] = {"jaccard": jaccard, "only_in_a": sorted(sa - sb), "only_in_b": sorted(sb - sa)}
    return pairwise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", nargs="+", required=True, help="instruction text files to compare pairwise, e.g. baseline run1 run2 run3")
    ap.add_argument("--reports", nargs="*", default=[], help="matching validate_candidate.py --json reports, same order as --texts, for the expectations-agreement axis")
    ap.add_argument("--null-texts", nargs="*", default=[], help="instruction files from UNRELATED agents, for the cross-agent null baseline")
    ap.add_argument("--ngram", type=int, default=3)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    texts = {p: Path(p).read_text() for p in args.texts}
    ngrams = {p: word_ngrams(t, args.ngram) for p, t in texts.items()}

    within_agent = {}
    for a, b in itertools.combinations(texts, 2):
        within_agent[f"{a} vs {b}"] = {
            "cosine": cosine(ngrams[a], ngrams[b]),
            "permutation_null": permutation_null(texts[a], texts[b], args.ngram),
        }

    result = {
        "within_agent_pairs": within_agent,
        "cross_agent_null_baseline": cross_agent_null(args.null_texts) if args.null_texts else None,
        "expectations_agreement": expectations_agreement(args.reports) if args.reports else None,
        "interpretation_note": (
            "Read cosine values against BOTH nulls: the permutation null shows what similarity looks "
            "like from shared vocabulary alone, and the cross-agent null shows the similarity floor for "
            "genuinely unrelated prompts. A within-agent cosine that is not clearly above both is not "
            "evidence of a systematic run-to-run relationship. Always read expectations_agreement "
            "alongside cosine — lexical and substantive similarity can diverge in either direction."
        ),
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
