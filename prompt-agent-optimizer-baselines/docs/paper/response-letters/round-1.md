# Response to reviewers — round 1

Responds to [`review-round-1.md`](../review-round-1.md), the `agent-paper-reviewer` skill's review of
[`paper-v1.md`](../paper-v1.md). The revision produced from this response is
[`paper-v2.md`](../paper-v2.md); its content is folded forward into [`paper-v3.md`](../paper-v3.md)
and the current manuscript, [`paper-v4.md`](../paper-v4.md).

We thank the reviewer for a review that found real, load-bearing problems in the protocol, not just
in the (correctly, intentionally) placeholder results. Every blocking required change is addressed
below; every suggested change is applied. Two changes reached outside the paper itself into
`docs/experiment-runbook.md` and `_baselines/dspy_mipro/run_mipro_baseline.py`, since the reviewer
verified the paper's claims by cross-checking those files directly and found the inconsistency
lived partly in them, not only in the paper's prose.

| # | Required change | Status | Where |
|---|---|---|---|
| 1 | Define the composite-score formula | **Done** | §5.3 now states the exact formula and clarifies instruction-level `blocked` and response-level composite score are reported as two separate numbers by design, never combined into one |
| 2 | Fix the statistical power ceiling | **Done** | §5.6 now states the exact minimum-p-value formula, requires k ≥ 9 (we specify k = 10) for any Holm-corrected significance claim, and makes the bootstrap CI and effect size the primary report at any k |
| 3 | Reconcile k across paper and runbook | **Done** | `experiment-runbook.md` Step 7 rewritten to state the k ≥ 9 / k = 10 requirement explicitly and match §5.6 |
| 4 | Fix holdout leakage in elect-and-reoptimize | **Done** | Election now uses MIPROv2's own internal validation slice of `dataset/optimize.jsonl` (a new `run_manifest.json` field), never `dataset/holdout.jsonl`; `run_mipro_baseline.py` updated to compute and record this score |
| 5 | Correct the `should_edit` gating description | **Done** | §4.2 corrected: four categories gate when critical (`must_have`, `should_remove`, `must_not_appear`, `should_edit`), two are purely advisory (`should_add`, `nice_to_have`) |
| 6 | Verify the agent_tests count/ratio claim | **Done** | §4.2 replaced with the actual observed range (9–13 tests per agent, 70–100% gating, mean ≈ 87%), computed directly from all ten agents' `expected/expectations.json` |
| 7 | Verify the InjecAgent characterization | **Done** | §2.3 and Table 1 corrected: InjecAgent does evaluate indirect, tool-mediated injection on a fixed agent; the paper's novelty claim is re-scoped to the optimizer-under-rewrite axis, not the injection-vector axis |
| 8 | Cite Foundry's own documented behavior | **Done** | Added a dated product-documentation reference, cited at every direct claim about Foundry's behavior |
| 9 | Add a growth-ratio results table | **Done** | New Table 7 |
| 10 | Add an iterative-refinement results table | **Done** | New Table 8 |
| 11 | Disambiguate "illustrative" (Table 1) from "placeholder" (§6) | **Done** | Table 1's caption now reads "qualitative, author-assessed" |
| 12 | Add "rows omitted" notes to Tables 4–6 | **Done in round 1, but incomplete** | Round 2 found only Tables 4 and 6 actually got the note; Table 5 did not. Fixed in round 2's response (see [`round-2.md`](round-2.md) item 7). |
| 13 | Add a systematic-vs-stochastic decision rule to §7 | **Done** | |
| 14 | Add the power ceiling and leakage risk to Limitations | **Superseded** | Both are now fixed in the protocol rather than disclosed as open limitations; §8 instead discloses the *cost* of the fix (k = 10 is expensive) as its replacement limitation |
| 15 | Clarify `should_edit` scoring | **Done** | §5.3 states `should_edit` is scored via its `accept_if` criterion through the same regex/semantic/judge pathway as every other rule type |

All six of the reviewer's questions are answered inline in the revised text (§5.3 for Q3, §5.4 for
Q1/Q2/Q6, §5.5 for Q4; Q5's citation-form request is addressed by the note retained in §8).
