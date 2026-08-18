# Changelog

## 2.3.0 — external journal review response, phase 0 (protocol + tooling, no real run data yet)

Responds to an external journal review of `docs/paper/paper-v3.md`; full triage in
`docs/paper/publication-plan.md`. All changes here are infrastructure/protocol — see that plan for
what still needs live Foundry access, a real experimental run, or a human rater (Phases 1-3).

- **Statistical fix (paper-v3.md §5.6):** the paired Wilcoxon signed-rank test used for the
  cross-system (Foundry vs. DSPy) comparison was invalid — replicate seeds from the two systems
  share no randomness, so pairing them by seed index was arbitrary. Now: one-sample Wilcoxon
  signed-rank for the within-system baseline-delta claim (still valid — paired against a fixed
  constant), Mann-Whitney U for the cross-system claim. Derived the Mann-Whitney sample-size floor
  (`2 / C(2n, n)`) — it clears the Holm-corrected threshold at k=6 per system, not k=9 like the
  invalid paired test needed.
- **`_baselines/dspy_mipro/metric.py`:** `score_response`'s penalty weights, floors, and severity
  table are now a single named `DEFAULT_WEIGHTS` dict, with an optional `weights=` override —
  backward-compatible (default behavior unchanged), and the foundation for weight-sensitivity
  analysis.
- **`_baselines/dspy_mipro/score_sensitivity.py` (new):** re-scores already-captured
  `(query, response, tool_calls)` logs under a grid of perturbed `score_response` weights — zero new
  LM calls — reporting how far each agent/run's mean score can move from the pre-registered
  baseline. Answers the "were these weights ever checked for robustness" review finding directly.
- **`_tools/human_calibration.py` (new):** judge-vs-human calibration for `llm_judge.py`, reusing
  `JudgeAgreementTracker` unchanged. `--sample` builds a stratified shortlist (oversampling the
  safety-critical agent and `should_edit`/semantic `must_have` items); `--score` re-runs the judge
  against the human-rated text and reports judge-vs-human (and human-vs-human, where rated by more
  than one person) agreement.
- **`_tools/model_pricing.py` (new) + `run_mipro_baseline.py` + `run_manifest_template.json`:** a
  cost-growth-ratio formula (word-count-proxy tokens, the same proxy `instruction_growth_ratio`
  already used, priced against a small, dated, explicitly `verified: False` per-model rate table),
  wired into both manifest formats as `baseline_est_cost_per_call_usd` /
  `optimized_est_cost_per_call_usd` / `est_cost_growth_ratio`. Restores paper-v3.md Table 7's cost
  column, which an earlier revision had dropped for lack of any supporting computation.
- **`_baselines/dspy_mipro/compare_to_foundry.py`:** added `est_cost_growth_ratio` summarization for
  both tracks. Also fixed a pre-existing crash found while smoke-testing this change: `summarize()`'s
  empty-input branch used a different CI dict key (`ci95`) than its populated branch
  (`ci95_bootstrap`), and the print loop only checked the latter — it crashed on the first agent
  with zero manifests, which is the common case in any partial run.

## 2.2.0 — shared LLM-judge layer for semantic rules and rubrics

Adds `_tools/llm_judge.py`, resolving the "UNJUDGED queue" limitation both `validate_candidate.py`
and the DSPy baseline previously documented: `semantic` instruction_rules and `rubrics` questions
can now be scored by an LLM judge instead of only regex-backed rules, single-sourced so both tracks
judge identically.

- `LiteLLMJudge` (real, lazy-imported `litellm` so `_tools/` keeps zero hard dependency for anyone
  who never opts in) and `StubJudge` (zero-cost, zero-network, lexical-overlap heuristic for offline
  smoke testing only — proves the plumbing, never treat its verdicts as evidence).
- Respects each agent's `judge_config`: `primary_judge_model` pinned to a vendor family disjoint
  from every supported Foundry `optimization_model`; an optional `cross_judge_model`, deliberately
  same-family as one condition, run in parallel to *measure* self-preference bias (Zheng et al.
  2023; Panickssery et al. 2024) via `repeats_per_item` majority-voting/averaging — never to
  override the primary verdict.
- `JudgeAgreementTracker`: corpus-level Cohen's kappa (binary rules) and Pearson r (Likert rubrics),
  computed once over all paired ratings accumulated in a run — deliberately has no per-item
  agreement method, since kappa's chance-correction term is only meaningful over a set of ratings.
  Both statistics are pure Python (no numpy/scipy) and unit-checked against hand-computable cases
  (perfect agreement → kappa=1.0; alternating disagreement → kappa≈0; perfect ±correlation →
  r=±1.0) in `llm_judge.py`'s own `__main__` self-check.
- `validate_candidate.py` gains `--judge-backend {stub,litellm}`, `--judge-model`, `--cross-judge`,
  `--cross-judge-model`, `--judge-repeats`, `--judge-temperature`. Default remains `none` — fully
  backward compatible, unchanged UNJUDGED-queue behavior for anyone not opting in.
- The DSPy baseline's `metric.py` gains `score_rubrics_for_response` and judge-aware
  `build_response_metric`/`instruction_level_report`; `run_mipro_baseline.py` gains `--use-judge`,
  `--judge-model`, `--cross-judge`, `--cross-judge-model`, `--judge-repeats`, `--judge-weight`
  (blend weight for the holdout score), and `--judge-during-search` (opt-in; judge is used for the
  final instruction report and holdout evaluation only by default, to control cost — the search
  loop's own metric stays deterministic-only unless this is passed).
- Verified end-to-end with StubJudge, zero API cost: all 10 agents × 2 seeds (20/20 runs) complete
  cleanly through `run_mipro_baseline.py --use-judge`, correctly moving every previously-UNJUDGED
  semantic rule to PASS/FAIL. `validate_candidate.py --judge-backend stub` independently confirmed
  to fully resolve all 10 agents' baselines with zero remaining UNJUDGED items — 9/10 correctly
  BLOCKED on their planted critical flaws, the control agent (`09`) passing clean.

## 2.1.0 — open DSPy MIPROv2 baseline

Adds `_baselines/dspy_mipro/`, an open, reproducible comparison point for the Foundry optimizer,
addressing the "how would this get accepted at an NLP/agents conference" review's top recommendation
(a closed, versioned, preview-stage vendor product isn't reproducible by a reader without access to
it — an open baseline run under the authors' own control is).

- Single-sourced against the same pack: `agent_loader.py` reads the identical `agent.yaml` /
  `instructions.md` / `tools.json` / dataset splits / `expected/expectations.json` the Foundry track
  uses — nothing is re-authored for DSPy.
- Same leakage guard: MIPROv2 only ever sees `dataset/optimize.jsonl` (internally re-split into
  train/val by `--seed`); `dataset/holdout.jsonl` is reserved for the final report, exactly
  mirroring `_tools/build_foundry_dataset.py`.
- Same contract-scoring code, not a reimplementation: `metric.py` imports `eval_match`/`validate`
  directly from `_tools/validate_candidate.py`.
- Same run-manifest shape as `_tools/run_manifest_template.json`, so `compare_to_foundry.py` can
  merge DSPy and Foundry runs into one table (with a percentile bootstrap 95% CI, not a
  normal-approximation CI, appropriate for the small k=3-5 replicate counts this pack expects).
- `run_all.py` runs k≥1 replicate seeds per agent by design, not a single Run1/Run2 draw.
- Verified end-to-end with a zero-cost, zero-network field-adaptive stub LM (`stub_lm.py`): all 10
  agents × 3 seeds (30/30 runs) complete the full pipeline — dataset loading, `dspy.ChainOfThought`
  and `dspy.ReAct` program construction with mocked tool calls, the full `MIPROv2.compile()` search
  loop (bootstrapping → instruction proposal → optuna-backed candidate selection), instruction
  extraction, and holdout evaluation — without error. This proves the plumbing; it says nothing
  about optimization quality, which requires a real `--task-lm`/`--prompt-lm`.
- Documented limitations carried into every result file: the two MCP agents (`04`, `07`) are
  optimized on an instructions-(+function-tools)-only basis (no real MCP server to call); no
  LLM-judge layer is wired up by default (pure regex/string scoring only, same "UNJUDGED queue"
  boundary as `validate_candidate.py`); `08`'s multi-turn rows are scored as flattened strings,
  inherited from the Foundry track's own current limitation.

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
