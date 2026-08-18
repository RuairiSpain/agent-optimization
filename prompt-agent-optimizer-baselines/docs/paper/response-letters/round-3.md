# Response to reviewers — round 3

Responds to [`../review-round-3.md`](../review-round-3.md), the `agent-paper-reviewer` skill's
review of [`paper-v4.md`](../paper-v4.md) — the revision produced by
[`external-journal-review.md`](external-journal-review.md). Unlike rounds 1 and 2, this round did
not find a design flaw in the protocol; it found that the *paperwork describing the protocol's own
revision history* did not match what version control actually shows, plus a handful of smaller
internal-consistency slips. Every blocking and suggested change is addressed below.

| # | Required change | Status | Where |
|---|---|---|---|
| 1 | The commit that produced `paper-v4.md` also edited `paper-v3.md` in place, contradicting the claim that `paper-v3.md` was kept as "the prior version of record" | **Done** | `paper-v3.md` restored, byte-identical, from `git show 823e78f:.../paper-v3.md` — the commit immediately before Phase 0 began, i.e. the exact version the external reviewer actually read. Every code comment and doc cross-reference that pointed at `paper-v3.md` for content that now lives only in `paper-v4.md` was updated to point at `paper-v4.md` instead (see the CHANGELOG's round-3 entry for the full file list). This response letter is deliberately explicit about what was corrected, for the same reason the reviewer flagged the original problem: a "before" vs. "after" claim should be checkable against the actual diff, not just asserted. |
| 2 | Section 8's "confirmed via literature search" sentence omitted AgentDojo despite its References entry pointing there | **Done** | Added Debenedetti et al. (2024, AgentDojo) to the named list in `paper-v4.md` Section 8. |
| 3 | The response letter's claim that "the manuscript itself is unchanged... beyond what §8 already disclosed" (external-review item 3) was inaccurate — no such disclosure existed | **Done** | Added a Limitations bullet and a Future Work bullet to `paper-v4.md` naming the weight-sensitivity gap and pointing to `score_sensitivity.py`. [`external-journal-review.md`](external-journal-review.md) item 3 now carries an explicit correction note rather than a silently rewritten claim. |
| 4 | Table 7's caption claims `run_manifest_template.json` "writes" `est_cost_growth_ratio`, which it does not — it only defines a null field | **Done** | Reworded: `run_mipro_baseline.py` computes and writes a real value for the DSPy track; `run_manifest_template.json` defines the same field, null by default, for a future harness to populate. |
| 5 | Section 5.3 doesn't state whether the partial-overlap tool-call penalty counts as a `regression_blocks`-floor "hard violation" | **Done** | Added a clause naming the three cases that do count (full miss, forbidden-call violation, `must_not_contain` match) and stating the partial-overlap case does not, matching `score_response`'s actual `hard_violation` logic. |
| 6 | Stray code comments mislabel the external review as this skill's "round 2," or still point at `paper-v3.md` for content that moved | **Done** | Fixed in `metric.py` (no longer conflates the external review with this skill's own round 2) and `score_sensitivity.py` (three `paper-v3.md` references corrected to `paper-v4.md`, and its module docstring no longer calls the external review "round 2 of the external review cycle"). |

All four of round 3's questions for the authors are answered by the changes above: Q1 by item 1
(restore, not relabel), Q2 by item 2 (drafting slip, now corrected), Q3 by item 3 (yes — done in this
response), Q4 by item 5 (excluded, now stated explicitly).
