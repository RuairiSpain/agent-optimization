# Review: Auditing Closed-Loop Prompt Optimization for LLM Agents: A Benchmark and Reproducible Baseline (Round 2)

## Summary of the paper

The paper introduces a ten-agent, 300-item benchmark for auditing whether closed-loop, evaluation-driven
prompt/tool-description optimizers (specifically Microsoft Foundry Agent Service's preview optimizer)
preserve safety-critical, policy-critical, and tool-boundary properties of an agent's instructions while
raising a composite evaluation score, and pairs it with an open, reproducible DSPy MIPROv2 baseline scored,
the paper claims, by the identical code-level contract on both tracks. This revision (v2) responds to a
round-1 review that found the statistical plan structurally incapable of reaching significance at its
stated replicate count, a holdout-leakage path in the iterative-refinement design, a misdescribed gating
category, and several other verifiable inconsistencies against the pack's own supporting documentation.
Section 6's results remain explicitly, repeatedly labeled illustrative placeholders — correctly, and not a
finding of this review.

## Strengths

- **The round-1 blocking fixes that touched code, not just prose, were verified to actually work, not just
  asserted.** The k=10 / Holm-Bonferroni reconciliation between §5.6 and `experiment-runbook.md` Step 7 and
  its "Definition of done" checklist now agree word-for-word on the same threshold and the same derivation
  (`2^(1-k)` floor, `k ≥ 9` after Holm correction across ten agents). More substantively, the
  elect-and-reoptimize holdout-leakage fix is real in the code, not only in the paper's text:
  `run_mipro_baseline.py` (lines 228–233, 291–295) computes `baseline_valset_mean_score` /
  `optimized_valset_mean_score` from `val_rows` — a slice of `dataset/optimize.jsonl` produced by
  `split_optimize_rows` — and never touches `spec.holdout_rows` for this purpose. The manifest's own
  `valset_note` field states this in the same words the paper and runbook now use. This is exactly the kind
  of "verify the code, not the response-to-reviewers table" check round 1 modeled, and it holds up.
- **The `should_edit` gating description and scoring mechanism are now precisely correct.** §4.2's "four
  categories gate when critical... two are purely advisory" matches `agent-evaluation-guide.md`'s table
  exactly, and §5.3's claim that `should_edit` is "checked through the identical mechanism, applied to each
  rule's `accept_if` criterion... rather than to its `current_text` field, which serves only as a diagnostic
  marker" is a precise, verified description of `validate_candidate.py`'s `validate()` function (lines
  120–131): `_eval(item["accept_if"])` drives the pass/fail status; `current_text` only feeds
  `baseline_text_still_present`, a non-gating diagnostic field.
- **The InjecAgent re-scoping (Table 1, §2.3) is now accurate and appropriately narrow**, correctly crediting
  InjecAgent with indirect/tool-output injection and re-scoping this paper's novelty claim to "an optimizer's
  effect on injection resistance" rather than the injection-vector axis itself.
- **Section 7's added decision rule** (a majority of k=10 replicate seeds, not a single failing run, before
  treating a Table 4 cell as the paper's central empirical claim) closes exactly the gap round 1 flagged and
  is stated with a concrete, if openly-labeled-as-working, threshold (≥6/10).
- **The response-to-reviewers table is mostly honest and traceable.** Of its 15 entries, the ones I could
  independently verify against source (items 3, 4, 5, 7, 8, 13, 15, and the two items reaching outside the
  paper) check out as described. This matters — a response table whose claims survive an independent
  code-level check is itself evidence of a careful revision process, even where (see below) two of its
  "Done" entries turn out to be incomplete rather than wrong.

## Weaknesses

Ordered most serious first. Items 1–3 are newly identified in this round by tracing the paper's scoring and
reporting claims through code the round-1 review did not examine as closely
(`compare_to_foundry.py`, `run_manifest_template.json`) — they are not placeholder-content complaints, and
all three would remain true after a full, honest experimental run.

1. **The paper's central "graded identically" claim does not hold for the response-level composite score —
   the exact number Table 3 (the headline result) reports.** The Abstract, §3 ("A shared scoring path"), and
   §5.3 all state that both tracks are scored by "a single shared, code-level contract" / "the same
   contract-checking implementation used to grade an exported Foundry candidate." This is true for the
   *instruction-level* layer (`validate_candidate.py` is genuinely imported and run against both an exported
   Foundry candidate's text and DSPy's optimized instructions). It is **not** true for the *response-level*
   layer that produces Table 3's number: `score_response` (the function §5.3 itself cites as "the exact
   implementation") lives in `_baselines/dspy_mipro/metric.py` and is called nowhere outside that directory
   (verified: `grep -rln "score_response"` returns only `metric.py` and `run_mipro_baseline.py`). No script
   or runbook step anywhere in the pack runs an exported Foundry candidate against real holdout queries to
   capture its actual responses and tool calls for scoring. `compare_to_foundry.py`'s
   `foundry_holdout_scores()` (lines 84–93) reads `outputs.holdout_composite_score` if present, and
   otherwise **falls back to `outputs.composite_score`** — which, per `run_manifest_template.json`'s own
   comment, is "the wizard's own reported number," i.e., Foundry's closed, internal evaluation, computed
   against whatever was uploaded to the Optimize wizard. Per Step 3 of the runbook, that upload is built
   exclusively from `dataset/optimize.jsonl` (`build_foundry_dataset.py` "refuses to process
   `dataset/holdout.jsonl`, even if you point it there directly"). So, as the pipeline is actually built and
   documented today, the Foundry column of Table 3 would either be blank or would silently substitute an
   **in-sample, non-shared-code score mislabeled as a holdout composite score** — directly contradicting
   §5.2's claim that "final scoring for every reported number in Section 6 uses the 10-item holdout split."
   This is a missing piece of infrastructure (a harness that invokes the deployed Foundry candidate against
   `dataset/holdout.jsonl` and scores its responses/tool calls with `score_response`), not a wording problem,
   and it undermines the validity of every downstream number derived from the Foundry column — including the
   Wilcoxon p-values and effect sizes in the same table.
2. **Table 4's own (round-1-revised) definition promises a quantity the codebase cannot currently produce.**
   The caption now defines the gate-pass rate as `blocked: false` **and** "every `regression_blocks`
   agent_test passing on the held-out split." The first half has a real source
   (`optimized_instruction_report_blocked` in the manifest, per the runbook's Step 10 table). The second half
   does not: the only place `regression_blocks` is used anywhere in the codebase is inside `score_response`
   (`metric.py` lines 128–129), where it floors a continuous per-item score at 0.15 on a hard violation — an
   implicit signal inside a float, not a reported pass/fail value — and the runbook's Step 10 source-mapping
   table doesn't cite any field for it either. There is currently no way to fill in the second half of
   Table 4's own definition from the pipeline as built.
3. **Table 7 (new in this revision) promises a metric that is never computed anywhere in the codebase.** Its
   caption reads "Mean instruction word-count growth ratio **and estimated cost growth ratio**," compared
   against both `max_instruction_growth_ratio` and `max_cost_growth_ratio`. Only the instruction growth
   ratio exists in code (`instruction_growth_ratio_words_approx`, a word-count proxy, in
   `run_mipro_baseline.py`). No script computes a cost growth ratio for either track: the Foundry manifest
   template has unused `est_cost_per_call_usd` / `est_latency_ms` fields with no ratio logic attached, and
   the DSPy manifest has no cost or latency field at all. Compounding this, the table's own columns
   ("Foundry growth ratio," "DSPy growth ratio") don't even indicate which of the two ratios the single
   number in each cell represents. This table cannot be filled with real numbers using the current tooling.

## Detailed comments by section

### Abstract
"Scored by a single shared, code-level contract so both systems are graded identically" is stated as a
core methodological guarantee. As detailed in Weakness 1, this is true for instruction-level scoring and not
(yet) true for the response-level composite score that Table 3 actually reports. Either qualify this
sentence to name the layer it applies to, or build the missing Foundry-side response harness before this
claim can stand as written.

### Introduction
No new issues beyond Weakness 1–3; the three-way gap argument (unchanged from v1, already praised in round
1) remains the paper's strongest piece of writing.

### Related work
Table 1 and §2.3's InjecAgent re-scoping is now accurate (Strengths). §2.6's caption disambiguation
("qualitative, author-assessed... distinct from the placeholder experimental data in Section 6") correctly
implements round 1's Required Change 11 — the two different senses of "illustrative" no longer share a word.

### Dataset / materials (Section 4)
§4.2's gating-category description is now correct (Strengths). Its "9 to 13 tests per agent (mean 10.3)"
does not survive a direct recount: counting `agent_tests` across all ten agents' actual
`expected/expectations.json` files gives totals of 9, 10, 9, 10, 13, 10, 10, 10, 10, 10 — sum 101, mean
**10.1**, not 10.3. The stated range (9–13) is correct, and the gating-percentage claim ("70% to 100%, mean
≈ 87%") checks out against the same recount (gating counts 8, 7, 7, 9, 12, 8, 9, 10, 8, 10 → range 70–100%,
mean ≈86.9%, aggregate 88/101≈87.1%). This is a small, low-stakes arithmetic slip, but it is exactly the
class of paper-vs-source number round 1 asked to be verified directly, and the sentence explicitly claims
"[c]ounted directly across all ten agents' `expected/expectations.json` files" — so the standard the paper
sets for itself here is that this number should be exactly right.

### Methodology (Section 5)
§5.2's "final scoring for every reported number in Section 6 uses the 10-item holdout split" is contradicted
by Weakness 1 as the pipeline currently stands. §5.3's composite-score formula is now defined (correctly
resolving round 1's Required Change 1 in spirit) but is incomplete relative to `score_response`'s actual
logic: it states the `required`-policy tool-call penalty only for the "no matching call observed" case
(-0.3) and omits the partial-overlap case the code also implements (`score -= 0.1 * len(wanted - overlap)`
when some but not all required tools were called; `metric.py` line 122). A reader trying to reimplement the
formula from the paper alone — the explicit purpose of round 1's request and the response table's "Done"
claim — would miss this term. §5.3's response-level scoring also isn't reachable for the Foundry track at
all yet (Weakness 1), which is a more serious gap than the missing term. §5.4's elect-and-reoptimize
description is now accurate and verified against both the runbook and `run_mipro_baseline.py` (Strengths).
§5.5–5.6 are unchanged from a round-1 pass that found them sound and remain so.

### Results (Section 6)
Correctly and unmissably labeled as placeholder throughout — no content-level critique offered on the
numbers themselves, consistent with the reviewing standard. Two structural issues affect the *tables'
design*, independent of their placeholder content: Table 4's second gating criterion and Table 7's cost
column cannot currently be populated with real data (Weaknesses 2–3), and Table 8, read together with §7's
own interpretive instruction ("if it falls within that distribution's confidence interval..."), reports only
"mean ± sd" for the distribution column with no CI — so a reader following §7's own guidance has nothing to
check the Run 3 score against in the table meant to supply it. Table 5 (primary/cross-judge agreement) still
shows a single agent row (05) with no "rows omitted, N total in the final version" note, unlike Tables 4 and
6, which both received this note per round 1's Required Change 12 (marked fully "Done" in the response
table, which overstates what was actually applied — 2 of 3 target tables got the note, not 3 of 3).

### Limitations (Section 8)
Genuinely honest and specific, as in round 1. It does not disclose the response-level scoring-path gap
(Weakness 1) or the unimplemented cost-growth-ratio metric (Weakness 3) — both belong here at minimum if
they are not fixed before the next revision, on the same standard this section otherwise holds itself to.

### Conclusion
Correctly marked as a placeholder; no issue.

### References
No new issues; round 1's InjecAgent miscitation is resolved (Strengths), and the paper's own honest
disclosure that several citations remain unverified against primary sources is unchanged and still
appropriate.

## Questions for the authors

1. For the Foundry track's response-level holdout score (Table 3): is there a harness — not yet documented
   in `experiment-runbook.md` or present in the codebase — that invokes the exported/deployed Foundry
   candidate against `dataset/holdout.jsonl` and scores its actual responses and tool calls with
   `score_response`? If so, where does it live and why isn't it referenced from the runbook's Step 10 table?
   If not, how is Table 3's "Foundry (optimized)" column intended to be populated with a number that is
   genuinely comparable to the DSPy column?
2. Is `outputs.composite_score` in a Foundry run manifest ever intended to be a holdout-split number, or is
   it understood by the authors to always be the wizard's own in-sample (optimize-split) evaluation? If the
   latter, should `compare_to_foundry.py`'s silent fallback from `holdout_composite_score` to
   `composite_score` be removed so a missing holdout score is reported as missing rather than silently
   backfilled with a different, non-comparable quantity?
3. Is a cost-growth-ratio computation planned (e.g., from token counts and a per-model price table) before
   Table 7 is populated, or should Table 7's cost column be dropped from the paper's scope for this revision
   cycle, with cost growth left to future work?
4. Is a per-test pass/fail boolean for `regression_blocks` agent_tests on holdout planned as an explicit,
   recorded field (as opposed to being inferred from a score landing at or near the 0.15 floor), so Table 4's
   second criterion has an unambiguous data source?

## Required changes

1. **(blocking)** Build (or explicitly scope out of this paper's claims) a response-level scoring path for
   the Foundry track that runs the exported/deployed candidate against `dataset/holdout.jsonl` and scores its
   real responses and tool calls with the same `score_response` function the DSPy track uses, so Table 3's
   "Foundry (optimized)" column is a genuine, shared-code, holdout-only number. Until this exists, either (a)
   qualify the Abstract's and §5.3's "graded identically" / "single shared implementation" language to state
   plainly that this currently applies to the instruction-level layer only, or (b) remove the silent
   `composite_score` fallback in `compare_to_foundry.py` so a missing Foundry holdout score is reported as
   missing rather than backfilled with the wizard's own in-sample number under a "holdout" label.
2. **(blocking)** Either implement a per-test, recorded pass/fail signal for `regression_blocks` agent_tests
   on the holdout split (not just the implicit 0.15-floor effect on a continuous score) so Table 4's stated
   definition is actually reportable, or narrow Table 4's caption to the one criterion the pipeline currently
   supports (`blocked: false`) and remove the `regression_blocks`-agent_test clause until the supporting
   field exists.
3. **(blocking)** Either implement an actual cost-growth-ratio computation for both tracks (token/latency- or
   price-based) and wire it into the manifests Table 7 draws from, or drop "estimated cost growth ratio" from
   Table 7's caption and columns for this revision, leaving only the instruction word-count growth ratio the
   pipeline actually produces today.
4. **(suggested)** Add a bootstrap 95% CI column to Table 8's "independent replicate runs" distribution, to
   match what §7's own interpretive bullet asks the reader to check the Run 3 score against ("falls within
   that distribution's confidence interval").
5. **(suggested)** Add the composite formula's partial-overlap term for `required` tool-call policy
   violations (`-0.1` per missing tool when some but not all required tools were called) to §5.3's formula
   description, so the formula is complete relative to `score_response`.
6. **(suggested)** Correct §4.2's "mean 10.3" to the directly-recomputed value (mean 10.1 across the ten
   agents' actual `agent_tests` counts: 9, 10, 9, 10, 13, 10, 10, 10, 10, 10).
7. **(suggested)** Add the "rows omitted, N total in the final version" note to Table 5, matching the note
   already present on Tables 4 and 6, and update the response-to-reviewers table's item 12 to reflect that
   this was applied to two of the three target tables, not all three.
8. **(suggested)** Add the response-level scoring-path gap (Required change 1) and the unimplemented
   cost-growth-ratio metric (Required change 3) to §8's Limitations list if they are not resolved before the
   next revision — both fit the section's otherwise unusually honest standard of naming real gaps plainly.

## Scores

- **Soundness:** 2/4 — round 1's most serious problems (statistical power ceiling, iterative-refinement
  holdout leakage, misdescribed gating category) are now genuinely fixed and verified against the actual
  code, not just claimed fixed. But this round surfaces a new, comparably serious structural gap: the
  paper's central "both tracks graded identically by shared code" claim does not hold for the response-level
  composite score that Table 3 actually reports, because no code path exists to score an exported Foundry
  candidate's real holdout responses at all. Two of the paper's newly-added results tables (4's second
  criterion, 7's cost column) also promise numbers the current tooling cannot produce.
- **Contribution:** 3/4 — unchanged from round 1. The "audit the optimizer, not the agent" framing remains
  specific and appears to be a real, underserved gap; the reproducible open-baseline design is a genuine,
  portable contribution once the scoring-path gap identified here is closed.
- **Overall recommendation:** Major Revision.

## Meta-review

This revision did the real work round 1 asked for: the statistical power fix and the iterative-refinement
leakage fix are not just present in the prose, they are correctly implemented in the code that will actually
produce the paper's numbers, which is the standard that matters. That is genuine progress and should be
recognized as such. But a round-2 pass that traces the paper's remaining central claim — "both systems are
graded identically by a single shared implementation" — through the same level of code detail round 1
applied to the statistical plan finds that this claim is not yet true for the one number the whole comparison
depends on: Table 3's Foundry holdout composite score has no code path that produces it from real holdout
responses scored by the shared metric, only a fallback to Foundry's own closed, in-sample wizard score. This
is not a placeholder-data problem (Section 6 remains correctly and unmissably labeled) and it is not cosmetic
— it is the same class of issue as round 1's leakage finding: a structural gap between what the paper's prose
promises about its own protocol and what the underlying pipeline can currently deliver, discoverable only by
reading the code the paper cites rather than trusting its description of that code. If the authors fix only
one thing before the next round, it should be this: build the missing Foundry-side response-scoring harness
(or explicitly and narrowly rescope the "graded identically" claim to the instruction-level layer alone)
before any real Table 3 number is reported, because every other number in this paper's central comparison —
the Wilcoxon tests, the effect sizes, the growth-ratio trade-off framing in Section 7 — is downstream of that
one column being genuinely comparable to its DSPy counterpart.
