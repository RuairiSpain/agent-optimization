# Changelog

## 2.0.0 — full revision: review fixes applied, pack expanded to 10 agents / 30 rows each

This revision applies every fix identified in the pack review, expands the sample set from 6 to 10
agents, and expands each agent's dataset from 10-15 rows to 30 (20 optimize / 10 holdout).

### Review findings → fixes (cross-referenced)

| # | Finding | Fix applied |
|---|---|---|
| 1 | Train/test leakage — the same dataset the wizard optimized against was also used to "prove" improvement | Every agent's data is now split into `dataset/optimize.jsonl` (20 rows, uploadable) and `dataset/holdout.jsonl` (10 rows, never uploaded). `_tools/build_foundry_dataset.py` hard-refuses any file named `holdout.jsonl` by filename, not just by convention. `_tools/validate_candidate.py` requires `--candidate-source optimize` and refuses otherwise. `expected/expectations.json.dataset_split` documents the split and its rationale per agent. |
| 2 | Dataset sizes (10-15 rows) too small for the statistical claims implied | Scaled to 30 rows per agent (300 total, up from ~80). Framed explicitly in each README as still better suited to regression gating than to high-power inferential statistics at n=20/n=10 — scale further before quoting p-values in a paper. |
| 3 | Order-statistic bias in "elect the best of Run1/Run2, then Run3" | Not a pack-content fix (this lives in the experiment notebooks), but this revision adds a second cross-domain "good baseline" control agent (`09-code-review-assistant-strict`) specifically so an H0 (stability) finding can be checked for replication across two unrelated domains instead of resting on `01-travel-approval-strict` alone. |
| 4 | "Run 2 will systematically beat Run 1" has no mechanism; needs to stay exploratory, not confirmatory | Pack-level support: `judge_config.repeats_per_item` (3, or 5 for the safety-critical agent) is now specified per agent so repeated-run noise can be estimated before any directional claim is made. |
| 5 | n-gram/cosine similarity needs a null baseline and a substantive-similarity axis | `_tools/similarity_baseline.py` rewritten: reports cosine against a **permutation null** (shuffled n-grams, same vocabulary) and a **cross-agent null** (unrelated agents' baselines), plus an **expectations-agreement** axis (Jaccard overlap of which rule IDs each candidate passes) so lexical and substantive similarity are never read as the same thing. |
| 6 | LLM-judge self-preference bias unaddressed | Every agent's `expected/expectations.json` now has a `judge_config` block pinning `primary_judge_model` to a vendor family disjoint from every supported `optimization_model` (gpt-5.x, DeepSeek-V*), with a same-family `cross_judge_model` kept specifically to measure the bias gap, not to replace the primary judge. |
| 7 | Tension between "keep quality/rubric scores high" and "stress-test with edge cases" | Resolved by treating the pack as a stress-test suite where high scores are the *outcome* being measured on a fix, not a constraint on the input agents — documented explicitly in the root README's "how to read this pack" section below. The two new "good baseline" control agents (01, 09) exist to demonstrate what "already high quality, must not regress" looks like, separately from the deliberately-flawed agents. |
| 8 | Coverage gaps: n=1 on MCP, no tool-output injection vector, no multi-turn, no cost/latency reporting | Four new agents added: `07-incident-response-mcp` (second MCP agent, opposite retrieval skew, tool-output prompt injection, tool-failure), `08-helpdesk-reset-multiturn` (context-accumulation and claimed-verification-bypass testing), `09-code-review-assistant-strict` (second good-baseline replicate, injection via diff content), `10-expense-claim-boundary` (capability honesty, financial fabrication, rounding/boundary arithmetic). `scoring.max_cost_growth_ratio` added to every agent's contract so a score win is always read as a quality/cost trade-off. |
| 9 | No reproducibility manifest for a hosted, versioned, non-deterministic optimizer | `_tools/run_manifest_template.json` added — one per optimizer run, capturing exact model version IDs, timestamps, wizard config, dataset hash, and eval-time inference temperature. `expected/expectations.json.run_manifest_ref` in every agent points at where its runs' manifests are expected to live. |

### Pack expansion

- **Agents: 6 → 10.** New: `07-incident-response-mcp`, `08-helpdesk-reset-multiturn`,
  `09-code-review-assistant-strict`, `10-expense-claim-boundary` — see manifest.json for what each
  targets.
- **Rows per agent: 10-15 → 30** (20 optimize / 10 holdout), for all ten agents, existing and new.
  Every added holdout row rephrases a training-set adversarial/edge-case pattern with different
  specifics (different currency, different secret format, different employee ID, different injected
  instruction) rather than repeating the exact training phrasing, so a fix that only pattern-matched
  the training example's literal wording is caught.
- **Schema: v1 → v2.0.0.** `_schema/expectations.schema.json` gained `dataset_split`, `judge_config`,
  `run_manifest_ref`, and `scoring.max_cost_growth_ratio`. All ten agents' `expected/expectations.json`
  conform to v2.0.0.

### How to read this pack after this revision

This pack has two agent "tracks," not one undifferentiated set:

- **Stress-test agents** (02, 03, 04, 05, 06, 07, 08, 10) are deliberately flawed in specific,
  documented ways. Their baseline composite scores are *expected* to be low — that is not a defect in
  the sample, it is the point. Grade the optimizer by whether it fixes the documented flaws (the
  `must_have`/`should_remove`/`should_edit` items and `regression_blocks` tests) without inventing new
  ones (`must_not_appear`), not by the size of the composite-score delta alone.
- **Control agents** (01, 09) are already good. Grade the optimizer here by whether it leaves the
  numeric/policy structure intact and stays inside the noise band — a large score jump on one of these
  two is itself a signal to inspect the candidate closely, not a win.

## 1.0.0 — initial release

Six baseline prompt agents (01-travel-approval-strict, 02-support-triage-messy,
03-invoice-extractor-schema, 04-hr-policy-mcp, 05-clinical-triage-safety,
06-sales-brief-underspecified), each with an `expected/expectations.json` contract, plus
`_tools/validate_candidate.py` and `_tools/build_foundry_dataset.py`.
