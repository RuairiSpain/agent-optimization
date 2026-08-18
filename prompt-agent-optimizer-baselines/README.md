# Foundry prompt-agent optimizer baselines

A sample pack of ten baseline **prompt agents** for Microsoft Foundry Agent Service's agent optimizer
(preview), built to evaluate the optimizer itself: what it fixes, what it silently leaves broken, and
what it invents. See `CHANGELOG.md` for the full list of methodological fixes applied in v2.0.0 and
exactly which prior review finding each one addresses.

An **open, reproducible baseline** (DSPy MIPROv2) runs against the identical pack — see
`_baselines/dspy_mipro/`. It exists so results aren't dependent on access to Foundry's closed preview
product: it reuses the same dataset split, the same `validate_candidate.py` contract-scoring code,
and the same run-manifest shape, so its output merges directly into one comparison table alongside
Foundry runs via `_baselines/dspy_mipro/compare_to_foundry.py`.

## Quick facts

- **10 agents**, **300 rows total** (20 optimize / 10 holdout each — see "Dataset split" below).
- **2 agents use MCP** (`04-hr-policy-mcp`, `07-incident-response-mcp`), each with the opposite
  retrieval-trigger flaw, so the pack tests both directions of the MCP-boundary problem. The other
  eight are pure prompt agents — MCP tool descriptions sit outside what the prompt-agent optimizer can
  rewrite, so retrieval behavior has to be governed entirely by instructions, which is exactly the
  boundary these two agents probe.
- **2 agents are "good baseline" controls** (`01-travel-approval-strict`, `09-code-review-assistant-strict`)
  in unrelated domains, so a stability (H0) finding can be checked for cross-domain replication rather
  than resting on a single case study.
- **1 agent tests multi-turn state** (`08-helpdesk-reset-multiturn`) — every other agent is exercised
  single-turn.
- Baseline quality spans **good → mixed → poor → underspecified** on purpose. Some follow instruction
  best practice; some deliberately don't.

## Dataset split (read this before running anything)

Every agent's data lives in two files:

- **`dataset/optimize.jsonl`** (20 rows) — the only file that may be uploaded to the Optimize wizard
  or passed to the CLI/SDK for the actual optimization run. `_tools/build_foundry_dataset.py` enforces
  this: it refuses to process a file named `holdout.jsonl` even if you point it there directly.
- **`dataset/holdout.jsonl`** (10 rows) — never shown to the optimizer. Used exclusively by your
  post-optimization scoring step, so a reported score delta reflects generalization, not fit to
  exactly what the wizard already saw.

This split exists because of a specific failure mode: if you optimize against a dataset and then
"prove" the optimized agent is better by scoring it against the *same* dataset, the optimizer is being
graded on a test it got to see the answers to. Every holdout row in this pack rephrases a training-set
pattern (different currency, different named condition, different secret format, different injected
instruction) with new specifics, precisely so a fix that only pattern-matched the training example's
exact wording is caught rather than rewarded.

## The two agent tracks

- **Stress-test agents** (02, 03, 04, 05, 06, 07, 08, 10) are deliberately flawed in specific,
  documented ways — contradictions, hedged policy, a buried privacy violation, an unsafe tail on an
  otherwise-good safety prompt, a vague or an over-eager MCP retrieval trigger, missing multi-turn
  state handling, financial fabrication dressed as pragmatism. Their baseline scores are *expected* to
  be low; that's the point. Grade the optimizer by whether it fixes the documented flaws without
  inventing new ones — not by the size of the score delta alone.
- **Control agents** (01, 09) already follow instruction best practice in two unrelated domains
  (travel-approval policy, code review). Grade the optimizer here by whether it leaves the numeric and
  policy structure intact and stays inside the noise band. A large score jump on either of these is a
  signal to inspect the candidate closely, not a result to celebrate.

## Layout

```
01-travel-approval-strict/       good baseline, 3 tools, no MCP — H0 control #1
02-support-triage-messy/         poor baseline, no tools
03-invoice-extractor-schema/     strict JSON contract, 2 tools
04-hr-policy-mcp/                MCP agent #1 — under-specified retrieval trigger, 2 tools + 3 MCP tools
05-clinical-triage-safety/       safety-critical, 2 tools
06-sales-brief-underspecified/   12-word baseline, no tools
07-incident-response-mcp/        MCP agent #2 — over-eager retrieval + tool-output injection, 2 tools + 3 MCP tools
08-helpdesk-reset-multiturn/     multi-turn identity-verification persistence, 2 tools
09-code-review-assistant-strict/ good baseline, 3 tools, no MCP — H0 control #2 (unrelated domain)
10-expense-claim-boundary/       capability honesty + financial fabrication + rounding, 2 tools
_schema/                         expectations.schema.json (v2.0.0)
_tools/                          validate_candidate.py, build_foundry_dataset.py,
                                  similarity_baseline.py, human_calibration.py,
                                  run_manifest_template.json
_baselines/dspy_mipro/           open DSPy MIPROv2 baseline — see its own README.md
CHANGELOG.md                     review findings → fixes, cross-referenced
manifest.json
```

Each agent folder is self-contained for the agent definition itself — `agent.yaml`, `instructions.md`,
`tools.json` (where applicable), `dataset/optimize.jsonl`, `dataset/holdout.jsonl`,
`expected/expectations.json`, and its own `README.md` explaining what it's designed to expose.

`_schema/` and `_tools/` are shared at the root rather than duplicated into every agent folder — the
tools resolve an agent by folder name relative to their own location
(`python _tools/validate_candidate.py --agent 04-hr-policy-mcp --candidate <path>`), so run them from
the pack root.

## The expectations contract

Each agent's `expected/expectations.json` carries:

- **`dataset_split`** — which file is optimize-only vs. holdout-only, and why.
- **`judge_config`** — the evaluation judge model, pinned to a vendor family disjoint from every
  supported Foundry `optimization_model`, plus a same-family cross-judge kept specifically to measure
  self-preference bias (Zheng et al. 2023; Panickssery et al. 2024) rather than to replace the primary
  judge.
- **`must_have`** — hard fails regardless of composite score; some `verbatim_required: true`.
- **`nice_to_have`** — marks a strong candidate, not a gate.
- **`should_edit`** — the exact baseline text, the problem, the expected change, and an `accept_if`
  criterion.
- **`should_remove`** / **`should_add`** — with the regexes or semantic statements that prove it.
- **`must_not_appear`** — the invention guards: hallucinated policy, extra schema keys, relaxed safety
  carve-outs, baked-in retrieved values, fabricated exchange rates.
- **`tool_rules`** — immutable names/types/enums, descriptions that should improve, tool pairs to
  disambiguate.
- **`rubrics`** — weighted binary/Likert evaluator questions to reproduce in the wizard's Criteria step.
- **`agent_tests`** — `tool_call.policy` of `required`/`forbidden`/`optional`, tagged
  `dataset_source: optimize | holdout`, with `regression_blocks: true` marking promotion gates.
- **`scoring`** — including `max_cost_growth_ratio`, so a score win is always read against its token
  and latency cost, not treated as free.
- **`known_traps`** — the specific ways a lazy or over-eager optimizer fails this sample, written down
  before running anything.

## Two working tools, one template

- **`_tools/validate_candidate.py`** — scores an optimized candidate's instructions against its
  contract. Deterministic rule types (`regex`, `all_of_regex`, `any_of_regex`, `absent`) are checked
  automatically; `semantic` rules are collected into an **UNJUDGED** queue and are never silently
  passed unless `--judge-backend {stub,litellm}` is passed to resolve them with an LLM judge (see
  `_tools/llm_judge.py` below). Refuses to run unless `--candidate-source optimize` is passed
  explicitly. Exits 1 on any critical deterministic (or judge-resolved) failure.
- **`_tools/llm_judge.py`** — shared judge layer resolving `semantic` rules and scoring `rubrics`
  questions, used by both `validate_candidate.py --judge-backend` and the DSPy baseline's
  `run_mipro_baseline.py --use-judge` (see `_baselines/dspy_mipro/README.md`). Respects each agent's
  `judge_config`: `primary_judge_model` pinned to a vendor family disjoint from every supported
  `optimization_model`, an optional same-family `cross_judge_model` run in parallel to *measure*
  self-preference bias (never to override the primary verdict) via `JudgeAgreementTracker`'s
  corpus-level Cohen's kappa / Pearson r, and `repeats_per_item` majority-voting/averaging. Zero
  hard dependency for anyone who never passes `--judge-backend`/`--use-judge`; `--judge-backend stub`
  gives a zero-cost, zero-network offline smoke test (StubJudge — a lexical-overlap heuristic with
  no real understanding, proves the plumbing only).
- **`_tools/build_foundry_dataset.py`** — strips authoring fields from `dataset/optimize.jsonl` to
  produce a portal- or CLI-ready upload (the wizard has no column-mapping step). Hard-refuses
  `holdout.jsonl` by filename.
- **`_tools/similarity_baseline.py`** — n-gram cosine similarity between candidate texts, reported
  against a **permutation null** (shuffled n-grams, same vocabulary — what similarity looks like from
  shared word choice alone) and a **cross-agent null** (unrelated agents' baselines — the similarity
  floor for genuinely unrelated prompts), plus an **expectations-agreement** axis (Jaccard overlap of
  which rule IDs each candidate passes) so lexical and substantive similarity are never conflated.
- **`_tools/human_calibration.py`** — judge-vs-human calibration for `llm_judge.py`, using the SAME
  `JudgeAgreementTracker` the primary/cross-judge self-preference check uses (it was written generic
  over "two raters," not specifically "two judges"). `--sample` builds a stratified shortlist of
  judge-eligible items (oversampling the safety-critical agent and `should_edit`/semantic `must_have`
  items) for a human rater to fill in against a specific run's real candidate text; `--score` re-runs
  the judge against that exact text and reports judge-vs-human agreement (plus human-vs-human, where
  more than one rater double-rated an item) — see `docs/paper/publication-plan.md` item #4 for why
  this exists: judge-vs-cross-judge agreement alone never calibrates the judge against a human.
- **`_tools/run_manifest_template.json`** — copy one per optimizer run. Captures exact model version
  IDs, timestamps, wizard config, dataset hash, and eval-time inference temperature, because Foundry's
  optimizer is a hosted, versioned, non-deterministic service and a "Run 1 vs Run 2" comparison is
  meaningless without knowing whether anything upstream changed between them.

Smoke-tested against every baseline: 02, 05 correctly come back **BLOCKED** on their planted critical
flaws; 01 and 09 pass with no deterministic critical failures, as designed for a good-baseline control.

## One honest caveat, unchanged from v1.0.0

The validator decides regex-backed rules deterministically but emits `semantic` rules as an
**UNJUDGED** queue rather than silently passing them. On agents where most of the interesting gaps are
semantic (04, 06, 07, 08 especially), the deterministic pass alone will report even a *bad* baseline
as mostly-promotable-looking. That's deliberate: it's the proof that regex gates alone aren't
sufficient, and an eval-model judge — configured per `judge_config`, cross-checked for self-preference
bias — has to be part of any harness built on top of this pack, not an optional extra.

## Workflow

Since prompt-agent optimization is portal-only in the current preview (see the notebooks under
`../notebooks/` for the full step-by-step, including which steps are PORTAL/CLI/CODE), the loop is:

1. Create the agent in Foundry from `agent.yaml` / `instructions.md` / `tools.json`.
2. `python _tools/build_foundry_dataset.py --agent <id> --out upload.jsonl` and upload it in the
   Optimize wizard.
3. Run the wizard, export the winning candidate's instructions.
4. `python _tools/validate_candidate.py --agent <id> --candidate <exported instructions> --candidate-source optimize --json report.json`
5. Score the candidate independently against `dataset/holdout.jsonl` (never uploaded in step 2).
6. Promote only if the validator passes *and* no `regression_blocks` test regressed on either split.
