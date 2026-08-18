# DSPy MIPROv2 baseline

An open, reproducible comparison point for the Foundry (closed, hosted) prompt-agent optimizer,
run against the identical 10-agent / 300-row pack. This exists to answer the review finding that a
paper built only on a closed, versioned, preview-stage vendor product isn't reproducible by anyone
without access to it — this baseline can be run by anyone with a DSPy-supported model and no Foundry
access at all, and its results are directly comparable via `compare_to_foundry.py`.

## Why this makes the comparison fair, not just parallel

- **Same agents, same contract.** `agent_loader.py` reads the exact same `agent.yaml`,
  `instructions.md`, `tools.json`, `dataset/optimize.jsonl`, `dataset/holdout.jsonl`, and
  `expected/expectations.json` files the Foundry track uses. Nothing is re-authored for DSPy.
- **Same leakage guard.** `dataset/optimize.jsonl` is the only file ever passed to
  `MIPROv2.compile()` (as an internal train/val split, reshuffled per `--seed`).
  `dataset/holdout.jsonl` is never touched by the optimizer — it's used exclusively for the final
  `holdout_eval.json`, exactly mirroring `_tools/build_foundry_dataset.py`'s refusal to export it.
- **Same scoring code, not a reimplementation.** `metric.py` imports `eval_match`/`validate`
  directly from `../../_tools/validate_candidate.py` (via `importlib`, not copy-pasted) to grade the
  final optimized instructions' `must_have` / `should_remove` / `must_not_appear` compliance — the
  identical function that would grade an exported Foundry candidate.
- **Same run-manifest shape.** Every run writes a `run_manifest.json` following
  `../../_tools/run_manifest_template.json`, so `compare_to_foundry.py` can merge both tracks into
  one table without translating formats.
- **Replicate seeds, not a single draw.** `run_all.py` runs k≥1 seeds per agent by design (default
  examples below use 3-5) specifically because a single MIPROv2 run — like a single Foundry run — is
  one draw from a stochastic search process, not a representative result (see the root README's
  discussion of why "Run 1 vs Run 2" needs a real distribution, not two points).

## Known, documented limitations — read before citing a number from this baseline

1. **MCP agents (`04-hr-policy-mcp`, `07-incident-response-mcp`) are optimized on an
   instructions-(+function-tools)-only basis.** There is no real MCP server in this repo to call, and
   simulating one well enough to fairly test retrieval-trigger behaviour is out of scope for an open
   baseline. `AgentSpec.dspy_optimization_scope_note` carries this caveat into every result file for
   these two agents. **Never read a DSPy-vs-Foundry delta on 04/07 as a like-for-like MCP comparison.**
2. **`08-helpdesk-reset-multiturn`'s multi-turn dialogues are scored as single flattened strings**,
   same as the Foundry track currently does (see that agent's own README) — this baseline inherits
   that limitation rather than introducing a new one.
3. **Mock tools return small, clearly-synthetic canned data** (see `mock_tools.py`), never plausible
   real figures — this is deliberate, so a MIPROv2-proposed instruction can't get rewarded for
   repeating a fabricated mock value and corrupt the `must_not_appear` fabrication guards.
4. **Instruction growth is reported as an approximate word-count ratio**, not a real tokenizer count
   — good enough for a growth *ratio*, not for an absolute token/cost figure.
5. **The response-level metric only grades a row against a named `agent_tests` entry when the
   dataset row's `query` matches an `agent_tests[].input` string exactly.** Measured overlap is a
   documented minority of rows per agent (40-90%, varies by agent — see `metric.py` docstring); rows
   without a match fall back to the universal `must_not_appear` guard only.
6. **The judge layer is off by default** (`--use-judge`) — without it, `score_response` and
   `instruction_level_report` are both pure regex/string checks, zero API cost, and cannot evaluate
   `semantic` rules or `rubrics` questions (same "UNJUDGED queue" limitation `validate_candidate.py`
   documents without `--judge-backend`). See "Judge-LM layer" below for what turning it on changes,
   and its own caveats (self-preference bias, repeat-count cost, StubJudge's total lack of real
   judgment).

## Judge-LM layer (optional, `--use-judge`)

Resolves `semantic` instruction_rules and scores `rubrics` questions via
`../../_tools/llm_judge.py` — the SAME shared judge module the Foundry-side
`validate_candidate.py --judge-backend` flag uses, so both tracks judge semantic content
identically. Respects each agent's `judge_config` in `expected/expectations.json`:
`primary_judge_model` (pinned to a vendor family disjoint from every supported Foundry
`optimization_model`), `cross_judge_model` (deliberately same-family as one condition, run in
parallel to *measure* self-preference bias — Zheng et al. 2023; Panickssery et al. 2024 — never to
override the primary verdict), `repeats_per_item`, and `inference_temperature`.

```bash
# Zero-cost judge-layer smoke test (StubJudge — a lexical-overlap heuristic with NO real
# understanding; proves the plumbing, not judge quality):
python run_mipro_baseline.py --agent 05-clinical-triage-safety --dry-run --use-judge

# Real judge resolution using the agent's own judge_config defaults:
python run_mipro_baseline.py --agent 01-travel-approval-strict --seed 0 \
    --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --use-judge

# ...plus a cross-judge pass to report corpus-level primary/cross agreement (Cohen's kappa for
# semantic rules, Pearson r for Likert rubrics) — the self-preference-bias check:
python run_mipro_baseline.py --agent 01-travel-approval-strict --seed 0 \
    --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --use-judge --cross-judge
```

**Cost control, deliberate:** by default the judge is used only for the FINAL instruction-level
report and holdout evaluation, not inside MIPROv2's search loop (which would multiply judge calls
by `trials × trainset/valset size × repeats_per_item`). Pass `--judge-during-search` to opt into
the much more expensive fully-judged search signal. `--judge-weight` (default 0.4) controls how
much the holdout score blends judge-scored rubrics against the deterministic score.

**Verified end-to-end with StubJudge** (zero cost, zero network): all 10 agents × 2 seeds (20/20
runs) complete cleanly with `--use-judge` on, correctly moving every previously-UNJUDGED semantic
rule to a PASS/FAIL verdict; `validate_candidate.py --judge-backend stub` was separately confirmed
to fully resolve all 10 agents' baselines with zero remaining UNJUDGED items (9/10 correctly
BLOCKED on their planted critical flaws; the tenth, `09-code-review-assistant-strict`, is the
control agent with no critical flaw to find).

**StubJudge's heuristic is intentionally dumb** — lexical term overlap between the statement/question
and the text, nothing more — so its individual verdicts will disagree with what a careful human
reader would conclude on plenty of items (see the example run above, where it flags one of agent
01's must_have items as failing). That's expected and fine for a plumbing smoke test; never read a
`--dry-run --use-judge` verdict as evidence about a candidate's actual quality, only as proof the
judge-resolution code path executes correctly end to end.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Zero-cost smoke test (no API key, no network calls beyond the initial pip install)

Every stage of the pipeline — dataset loading, program construction (both `dspy.ChainOfThought` for
tool-free agents and `dspy.ReAct` for tool-using ones), the response-level metric, the full
`MIPROv2.compile()` search loop (bootstrapping → instruction proposal → Bayesian candidate
selection via optuna), instruction extraction, and holdout evaluation — was smoke-tested against a
deterministic, zero-network `StubLM` (`stub_lm.py`) that has no language understanding but returns
correctly-shaped placeholder values for whatever output fields any DSPy-internal signature asks for.
This proves the **plumbing**, not optimization **quality** — treat any score from a `--dry-run` as
meaningless except as a "did it crash" signal.

```bash
# One agent:
python run_mipro_baseline.py --agent 06-sales-brief-underspecified --dry-run

# The whole pack, 2 replicate seeds each (confirmed: 20/20 runs OK — all 10 agents, both a
# tool-free ChainOfThought agent and every ReAct/tool-using and MCP-function-tools-only agent):
python run_all.py --agents all --seeds 0 1 --dry-run
```

## Real runs (cost money, need an API key)

```bash
# One agent, one seed:
python run_mipro_baseline.py --agent 01-travel-approval-strict --seed 0 \
    --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium

# Full replicate sweep for the paper (k=5 seeds, matches the pack's registered primary agent):
python run_all.py --agents 01-travel-approval-strict --seeds 0 1 2 3 4 \
    --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium
```

`--task-lm`/`--prompt-lm` accept any `litellm`-resolvable model string (e.g. `openai/gpt-4.1-mini`,
`anthropic/claude-...`, `azure/...`); the corresponding API key must be in the environment
(`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. — dspy/litellm read these directly, nothing
pack-specific to configure). `--auto light|medium|heavy` controls MIPROv2's search budget (trial
count and candidate count) — `light` is cheap and fast, appropriate for CI-style smoke checks with a
real but cheap model; use `medium`/`heavy` for the numbers that actually go in a paper.

**Cost note:** `--prompt-lm` (MIPROv2's instruction-proposal model) is called far less often than
`--task-lm` (evaluated on every trainset/valset example, every trial). Mirroring the pack's Foundry
convention, pick `--task-lm` to match the deployed agent's real model and `--prompt-lm` to be a
stronger model, since that's the one actually authoring the candidate instructions.

## Merging into one comparison table

```bash
python compare_to_foundry.py --results-dir results --pack-root ../.. --out results/comparison.json
```

Reads every `results/<agent>/<seed>/run_manifest.json` this baseline wrote, and — if present — every
Foundry `run_manifest.json` under `<pack_root>/runs/<agent_id>/<run_label>.manifest.json` (the
convention each agent's `expected/expectations.json.run_manifest_ref` points at). Reports mean,
sample stdev, and a **percentile bootstrap 95% CI** (not a normal approximation — appropriate for the
small replicate counts, k=3-5, this pack expects) per agent per system. If no Foundry manifests exist
yet, it says so explicitly rather than filling the gap with a placeholder number.

## Composite-score weight sensitivity analysis

```bash
python score_sensitivity.py --results-dir results --out results/sensitivity_report.json
```

Re-scores every already-captured `(query, response, tool_calls)` triple in each run's
`holdout_eval.json` / `baseline_holdout_eval.json` under a grid of perturbed `score_response`
weights (severity weights, per-item penalties, the `regression_blocks` floor — all ±25% or an
adjacent alternative), and, where a log has a cached `rubric_score`, under a `judge_weight` grid too
— all with **zero new LM calls**, since the captured responses are reused as-is. Reports, per
agent/run, how far the mean score can move away from the pre-registered baseline weights across the
grid. This is a direct answer to the concern that the weights in `metric.DEFAULT_WEIGHTS` were
hand-tuned with no robustness check (see `docs/paper/publication-plan.md` item #3): a small delta
across the grid is evidence a paper's conclusion doesn't depend on the exact weight choice; a large
delta on a conclusion that's close to a threshold means it should be reported with that caveat. It
cannot show the weights are "correct" — there's no ground truth for that — only that a documented
family of reasonable alternatives does or doesn't change what gets reported. Scoped to the DSPy
track today, since Foundry's response-level scoring path doesn't exist yet (see the main pack
README's Limitations and `docs/paper/paper-v4.md` Section 5.3/8) — it will cover both tracks
unchanged, from whatever log the Foundry harness eventually writes, once that harness exists.

## Files

| File | Role |
|---|---|
| `agent_loader.py` | Loads one agent's files into a plain `AgentSpec` |
| `mock_tools.py` | Deterministic, stateless mock tool implementations + a call log |
| `metric.py` | Response-level MIPROv2 metric + instruction-level report (imports `validate_candidate.py`) |
| `dspy_program.py` | Builds the `dspy.ChainOfThought`/`dspy.ReAct` module per agent |
| `stub_lm.py` | Zero-cost, field-adaptive stub LM for `--dry-run` smoke testing only |
| `../../_tools/llm_judge.py` | Shared judge backend (`LiteLLMJudge`/`StubJudge`) + `JudgeAgreementTracker`, used by both this baseline and `validate_candidate.py --judge-backend` |
| `run_mipro_baseline.py` | CLI: one agent, one seed, full compile + holdout eval + manifest, `--use-judge`/`--cross-judge` |
| `run_all.py` | Loops `run_mipro_baseline.py` over agents × replicate seeds |
| `compare_to_foundry.py` | Merges DSPy + Foundry run manifests into one comparison table |
| `score_sensitivity.py` | Re-scores captured logs under a weight-perturbation grid — no new LM calls |
