# Response to reviewers — round 2

Responds to [`review-round-2.md`](../review-round-2.md), the `agent-paper-reviewer` skill's review of
[`paper-v2.md`](../paper-v2.md). The revision produced from this response is
[`paper-v3.md`](../paper-v3.md); its content is folded forward into the current manuscript,
[`paper-v4.md`](../paper-v4.md).

Round 2 confirmed that round 1's most serious fixes (the statistical power ceiling and the
elect-and-reoptimize holdout leakage) hold up against a direct code-level re-check, not just against
the response table in [`round-1.md`](round-1.md). It also found one new, comparably serious
structural gap — the paper's "graded identically" claim did not hold for the response-level
composite score, which is the exact number Table 3 reports — plus two results tables that promised
quantities the pipeline could not yet produce, and a small arithmetic slip. Every blocking and
suggested change is addressed below.

| # | Required change | Status | Where |
|---|---|---|---|
| 1 | Fix or scope down the "graded identically" claim for the response-level score | **Done (scoped, not built)** | We take the review's option (b): `compare_to_foundry.py` no longer silently substitutes Foundry's in-sample `outputs.composite_score` for a missing `holdout_composite_score`; it now reports the gap explicitly. §5.2, §5.3, and the Abstract are rewritten to state plainly that the shared-code guarantee currently covers the instruction-level layer only, and that Foundry's response-level holdout score requires a harness this pack does not yet build. Added to §8 Limitations and §9 Future work. |
| 2 | Table 4's `regression_blocks`-on-holdout criterion has no data source | **Done (narrowed)** | Table 4's caption and column now report `blocked: false` only, the one criterion the pipeline actually records; the unimplemented per-test pass/fail clause is removed from the caption and listed instead as future work (§9). |
| 3 | Table 7's cost-growth-ratio column is never computed anywhere | **Done (dropped, later implemented)** | Dropped from Table 7 in this revision's initial pass; subsequently implemented (`_tools/model_pricing.py`, wired into `run_mipro_baseline.py` and `run_manifest_template.json` — see [`external-journal-review.md`](external-journal-review.md) item 11) and restored to Table 7 with an explicit note that the underlying price table is unverified against live vendor pricing. |
| 4 | Add a CI column to Table 8 | **Done** | Table 8's "independent replicate runs" column now reports mean ± sd and a bootstrap 95% CI, matching what §7's own interpretive bullet asks the reader to check the Run 3 score against. |
| 5 | Add the partial-overlap tool-call penalty term to §5.3's formula | **Done** | §5.3 now states the `-0.1` per-missing-tool partial-overlap penalty alongside the full-miss and forbidden-call terms. |
| 6 | Correct §4.2's "mean 10.3" | **Done** | Corrected to the directly-recomputed mean of 10.1 (totals 9, 10, 9, 10, 13, 10, 10, 10, 10, 10 across the ten agents). |
| 7 | Add the "rows omitted" note to Table 5 | **Done** | Table 5's caption now states the same "N total in the final version" note Tables 4 and 6 already carried. |
| 8 | Disclose the response-scoring gap and the dropped cost metric in Limitations | **Done** | §8 gains two new items: the Foundry-side response-scoring harness gap (item 1 above), and the absence of a cost-growth-ratio metric (item 3 above, later superseded once implemented — see [`external-journal-review.md`](external-journal-review.md)). |

All four of round 2's questions for the authors are answered by the changes above: Q1–Q2 by item 1's
scoping decision (§5.2, §5.3, §8), Q3 by item 3, Q4 by item 2.
