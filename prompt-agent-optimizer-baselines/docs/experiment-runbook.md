# Experiment runbook

This runbook walks you through every step needed to run the full evaluation: optimizing each agent
through Foundry, optimizing it again through the open DSPy baseline, resolving the semantic rules
with a judge, and assembling the results you need for the paper.

Follow the steps in order the first time. After that, treat each numbered section as a standalone
procedure you can repeat for a new agent or a new run.

## Before you start

You need:

- A clone of this repository, with a shell open at the pack root
  (`prompt-agent-optimizer-baselines/`).
- Python 3.10 or later.
- Foundry Agent Service preview access, enabled for your subscription, for the steps marked
  **Portal**.
- API keys for the models you plan to use as `--task-lm`, `--prompt-lm`, and your judge models, for
  the steps marked **CLI (real run)**. Set them as environment variables — `OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`, or whatever your provider requires. `litellm` (a DSPy dependency) reads these
  directly; you don't configure them anywhere in this repository.

Each step is labeled:

| Label | What it means |
|---|---|
| **CLI** | Run from your shell, no cost, no API key required. |
| **CLI (real run)** | Run from your shell; makes real model calls and costs money. |
| **Portal** | A manual step in the Foundry Optimize wizard. |

## Step 1: Set up the DSPy baseline environment

**CLI**

```bash
cd prompt-agent-optimizer-baselines/_baselines/dspy_mipro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Confirm the install and the pack's dataset loading both work before you go further:

```bash
python agent_loader.py
```

You should see one line per agent, each reporting 20 optimize rows, 10 holdout rows, and the correct
tool/MCP count. If a line is missing or a count looks wrong, stop here and check your clone before
continuing — every later step depends on this loading correctly.

## Step 2: Smoke-test the whole pipeline for free

**CLI**

Before spending any money, confirm the DSPy optimization loop itself runs end to end using a
zero-cost stub model:

```bash
python run_all.py --agents all --seeds 0 1 --dry-run --auto light
```

This exercises every stage — dataset loading, program construction, the full MIPROv2 search loop,
instruction extraction, and holdout evaluation — for all ten agents, without calling a real model.
Expect `20/20 runs OK` in the summary line. A `--dry-run` score is meaningless as evidence of
optimization quality; it only tells you the wiring works. Do this again any time you change the pack
or the baseline code, before you spend money on a real run.

## Step 3: Prepare and upload one agent's dataset to Foundry

**CLI**, then **Portal**

The wizard has no column-mapping step, so strip the authoring fields first:

```bash
cd prompt-agent-optimizer-baselines
python _tools/build_foundry_dataset.py --agent 01-travel-approval-strict --out upload_01.jsonl
```

This command reads only `dataset/optimize.jsonl` and refuses to process `dataset/holdout.jsonl`,
even if you point it there directly — the holdout split exists specifically so the optimizer never
sees it, and this is where that guarantee is enforced.

In the Foundry portal:

1. Create a prompt agent from `01-travel-approval-strict/agent.yaml`,
   `01-travel-approval-strict/instructions.md`, and `01-travel-approval-strict/tools.json`.
2. Open the agent's **Optimize** tab.
3. Upload `upload_01.jsonl` as the evaluation dataset.
4. Select an eval model and an optimization model. Pick the eval model from a vendor family
   disjoint from the optimization model, matching the `judge_config.primary_judge_model` convention
   in `expected/expectations.json` — this avoids a same-family self-preference bias in the
   evaluator (see the paper's related-work section for the citation on this).
5. Run the optimization.

Repeat for each agent you're evaluating.

## Step 4: Export and validate a Foundry candidate

**Portal**, then **CLI**

1. In the wizard's results view, export the winning candidate's instructions as plain text or
   markdown. Save it as, for example, `01-travel-approval-strict/candidates/foundry_run1.md`.
2. Validate it against the agent's contract:

```bash
python _tools/validate_candidate.py \
  --agent 01-travel-approval-strict \
  --candidate 01-travel-approval-strict/candidates/foundry_run1.md \
  --candidate-source optimize \
  --json 01-travel-approval-strict/candidates/foundry_run1.report.json
```

Read the printed report. A line prefixed `[XX]` under `BLOCKED` is a critical failure — don't
promote the candidate. Lines prefixed `[??]` are semantic rules waiting on a judge; continue to the
next step before you decide whether the candidate passes.

## Step 5: Resolve the semantic rules with a judge

**CLI (real run)**, or **CLI** for a free smoke test

A judge is required to resolve any rule the deterministic pass leaves `UNJUDGED`. Smoke-test the
judge wiring for free first:

```bash
python _tools/validate_candidate.py \
  --agent 01-travel-approval-strict \
  --candidate 01-travel-approval-strict/candidates/foundry_run1.md \
  --judge-backend stub
```

`--judge-backend stub` uses a lexical-overlap heuristic with no real understanding — it proves the
resolution logic runs, not that the verdicts are trustworthy. Never read its output as evidence.

For a real judge pass, using the agent's own `judge_config` defaults:

```bash
python _tools/validate_candidate.py \
  --agent 01-travel-approval-strict \
  --candidate 01-travel-approval-strict/candidates/foundry_run1.md \
  --judge-backend litellm \
  --cross-judge \
  --json 01-travel-approval-strict/candidates/foundry_run1.judged.json
```

`--cross-judge` additionally runs `judge_config.cross_judge_model` — a model deliberately from the
same vendor family as one of the optimization conditions — so you can measure, not just assume,
whether the primary judge is inflating scores for outputs from its own family. The report's
`primary_cross_judge_agreement` field gives you a Cohen's kappa over every semantic rule judged in
this run; read it before you trust the primary judge's verdicts.

A candidate is promotable only when `blocked` is `false` **and** every `UNJUDGED` item has been
resolved to a non-critical-failure verdict. See
[`agent-evaluation-guide.md`](agent-evaluation-guide.md#what-counts-as-a-promotable-candidate) for
the full promotion checklist.

## Step 6: Run the DSPy baseline for the same agent

**CLI (real run)**

```bash
cd _baselines/dspy_mipro
python run_mipro_baseline.py \
  --agent 01-travel-approval-strict --seed 0 \
  --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium \
  --use-judge --cross-judge
```

`--task-lm` is the model the optimized instructions run on — pick the model you'd actually deploy
the agent with. `--prompt-lm` is the model MIPROv2 uses to propose new instructions — pick a
stronger model here, since it's the one authoring the candidate. `--auto` controls the search budget
(`light`, `medium`, or `heavy`); use `medium` or `heavy` for numbers that go in the paper.

This single command produces everything Steps 3–5 produced for the Foundry track: an optimized
instructions file, an instruction-level report, and a holdout evaluation, all written to
`_baselines/dspy_mipro/results/01-travel-approval-strict/seed0/`.

## Step 7: Run replicate seeds, not a single run

**CLI (real run)**

A single optimization run — on either track — is one draw from a stochastic search process, not a
representative result. How many replicate seeds you need depends on what you intend to claim:

- **k ≥ 3** gives a descriptive estimate (mean, standard deviation, bootstrap confidence interval).
  Report a wide CI honestly at this scale rather than treating it as a tight estimate.
- **k ≥ 9** is the minimum for the paired Wilcoxon signed-rank test in the paper's Section 5.6 to be
  able to reach significance at all after Holm-Bonferroni correction across ten agents. This isn't a
  stylistic preference: the exact test's smallest achievable two-sided p-value at k replicate pairs
  is 2^(1−k), so at k=5 the floor is 0.0625 — no effect size, however large, can produce p < 0.05.
  Run **k = 10** if you intend to report a Holm-corrected significance claim for any agent; at
  k < 9, only the descriptive CI and effect size are reportable, and the paper says so explicitly
  rather than reporting a p-value that can't mean what a p-value normally means.

```bash
python run_all.py \
  --agents 01-travel-approval-strict --seeds 0 1 2 3 4 5 6 7 8 9 \
  --task-lm openai/gpt-4.1-mini --prompt-lm openai/gpt-5 --auto medium \
  --use-judge
```

For the Foundry track, repeat Steps 3–5 the same number of times for the same agent, saving each
exported candidate under a distinct name (`foundry_run1.md`, `foundry_run2.md`, and so on) and
recording each run's exact model versions and timestamp in a copy of
`_tools/run_manifest_template.json`, saved alongside the candidate. Foundry is a hosted, versioned
service — without this record, you can't tell a genuine run-to-run difference from a silent
model-version change between runs.

Running k = 10 real optimization runs per agent, per track, is expensive — for the ten-agent pack
that's 100 optimization runs minimum before you've compared a single alternative optimization
target. Treat k = 10 as the bar for a significance claim you plan to publish, and k = 3–5 as
sufficient for an exploratory pass or a CI-only report while you're still iterating on the pack
itself.

### If you're running the elect-and-reoptimize design

Some experiment designs call for electing the best of an initial pair of runs and optimizing again
from there (see the paper's methodology section for why this needs care). This design has a second
failure mode beyond the order-statistic bias the paper discusses: if you use `dataset/holdout.jsonl`
to decide which of Run 1 / Run 2 to elect, and then also report Run 3's score on that same holdout
split, the holdout split has leaked into a decision that shaped the final reported candidate — the
same leakage the optimize/holdout split exists to prevent in the first place. Elect using a source
the final report doesn't also depend on:

1. Run two independent replicate seeds (Run 1, Run 2).
2. Score both using the internal validation score `run_mipro_baseline.py` already computes during
   `MIPROv2.compile()` — the slice of `dataset/optimize.jsonl` held back as `--val-fraction` for
   MIPROv2's own use, never `dataset/holdout.jsonl`. This score is already written to each run's
   `run_manifest.json`; you don't need a separate scoring pass to get it.
3. Elect whichever scored higher as the seed for Run 3.
4. Run Run 3 as a fresh optimization starting from the elected candidate's instructions.
5. When you report the result, compare Run 3 only to the elected candidate — not to Run 1 or Run 2
   individually. `max(Run 1, Run 2)` is higher than either one by construction, so comparing Run 3
   back to a single earlier run isn't evidence that re-optimizing helped; it's arithmetic.

## Step 8: Merge both tracks into one comparison table

**CLI**

```bash
cd _baselines/dspy_mipro
python compare_to_foundry.py \
  --results-dir results --pack-root ../.. --out results/comparison.json
```

This reads every DSPy `run_manifest.json` your replicate runs produced, and — if you've saved
Foundry run manifests under `<pack_root>/runs/<agent_id>/<run_label>.manifest.json` — merges both
into one table with a percentile bootstrap 95% confidence interval per agent per system. If you
haven't saved any Foundry manifests yet, the command says so explicitly instead of silently leaving
that half of the table blank-looking.

## Step 9: Compute text similarity across runs

**CLI**

To compare how similar the optimized instructions are across runs (for example, Run 1 vs. Run 2 vs.
Run 3 from Step 7):

```bash
cd prompt-agent-optimizer-baselines
python _tools/similarity_baseline.py \
  --texts 01-travel-approval-strict/candidates/foundry_run1.md \
          01-travel-approval-strict/candidates/foundry_run2.md \
          01-travel-approval-strict/candidates/foundry_run3.md \
  --reports 01-travel-approval-strict/candidates/foundry_run1.report.json \
            01-travel-approval-strict/candidates/foundry_run2.report.json \
            01-travel-approval-strict/candidates/foundry_run3.report.json \
  --null-texts 06-sales-brief-underspecified/instructions.md \
               09-code-review-assistant-strict/instructions.md \
  --out 01-travel-approval-strict/candidates/similarity.json
```

Read the cosine similarity against **both** null baselines the tool reports: the permutation null
(what similarity looks like from shared vocabulary alone) and the cross-agent null (the similarity
floor for genuinely unrelated prompts). A raw cosine number on its own tells you nothing — it needs
a null to be interpreted against. Also read `expectations_agreement` alongside the cosine score:
two runs can be lexically far apart but pass the same contract items, or lexically close while one
of them silently drops a safety rule the other kept.

## Step 10: Assemble results for the paper

Once you've completed Steps 3–9 for every agent you're evaluating, you have everything the paper's
results section needs:

| Paper table | Source |
|---|---|
| Baseline vs. optimized composite score, per agent, per track | `compare_to_foundry.py`'s output |
| Regression-gate pass rate | `validate_candidate.py` / `run_manifest.json`'s `optimized_instruction_critical_failures` field, per replicate seed |
| Primary/cross-judge agreement | `primary_cross_judge_agreement` in each judged report |
| Cross-run textual similarity | `similarity_baseline.py`'s output |
| Instruction and cost growth ratio | `run_manifest.json`'s `instruction_growth_ratio_words_approx` field |

Keep every raw `run_manifest.json`, candidate file, and validation report — the paper's results
should cite these files directly rather than a number transcribed by hand, so a reader can trace any
figure in the paper back to the exact run that produced it.

## Definition of done, per agent

An agent's evaluation is complete for a **descriptive-only** report (mean, CI, no significance
claim) when you have:

- [ ] At least 3 replicate Foundry runs, each with a saved candidate, run manifest, and validation
      report (judged, with cross-judge agreement recorded).
- [ ] At least 3 replicate DSPy runs, same requirements, via `run_all.py`.
- [ ] A `compare_to_foundry.py` table that includes both tracks for this agent.
- [ ] A `similarity_baseline.py` report comparing the replicate runs within each track.
- [ ] Every gating test (`regression_blocks: true`) checked on `dataset/holdout.jsonl` for the
      winning candidate on each track, not just `dataset/optimize.jsonl`.

It's complete for a **Holm-corrected Wilcoxon significance claim** (Step 7's k ≥ 9 requirement)
only when the first four checkboxes above are satisfied at k = 10 replicate seeds per track, not 3.
Report descriptive-only results for any agent that doesn't meet the k = 10 bar rather than reporting
a p-value the sample size can't support — see the paper's Section 5.6 for why.

Only once every agent you're reporting on meets this checklist should its numbers replace the
placeholder tables in the paper draft (see [`paper/`](paper/)).
