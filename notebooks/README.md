# Notebooks — Microsoft Foundry Agent Service prompt-agent optimizer, walked through one case study

Ten Jupyter notebooks that walk through the main features of Microsoft Foundry Agent Service's
prompt-agent **Optimize** feature (preview), end to end, using **one running case study** throughout:
[`01-travel-approval-strict`](../prompt-agent-optimizer-baselines/01-travel-approval-strict/), a
well-written travel-expense-approval prompt agent from the
[`prompt-agent-optimizer-baselines`](../prompt-agent-optimizer-baselines/) pack shipped in this repo.

This directory is the `../notebooks/` the pack's own `README.md` and
`_tools/build_foundry_dataset.py` already pointed at before it existed.

## Why this case study

- It's a **control** agent — its baseline already follows instruction best practice, so you watch
  Foundry's optimizer either respect a good prompt or damage it, without a badly-written baseline as
  a second variable.
- **3 function tools, no MCP** — enough to show tool definitions and tool-call gating without the
  extra moving part of an MCP retrieval trigger.
- **Clear numeric policy** (approval thresholds, lodging caps, a 6-hour business-class rule), so
  "did the optimizer preserve the policy or quietly soften it" is something you can check by eye, not
  just by score.

Swap `AGENT_ID` in notebook 00's setup cell for any of the pack's other nine agents to re-run this
whole series against a different case study — see
[`../prompt-agent-optimizer-baselines/docs/agent-evaluation-guide.md`](../prompt-agent-optimizer-baselines/docs/agent-evaluation-guide.md)
for what each one is designed to expose.

## The plan

| # | Notebook | Foundry feature it demonstrates | Mode |
|---|---|---|---|
| 00 | `00_setup_and_overview.ipynb` | Environment setup, the case-study agent, the roadmap below | CLI |
| 01 | `01_agent_anatomy.ipynb` | Anatomy of a Foundry **prompt agent** — instructions, tools, dataset, eval contract | CODE |
| 02 | `02_create_agent_in_foundry_portal.ipynb` | Creating an agent in **Foundry Agent Service** | Portal |
| 03 | `03_prepare_and_upload_dataset.ipynb` | Preparing an **Optimize wizard** dataset upload, and its leakage guard | CLI + Portal |
| 04 | `04_run_optimize_wizard.ipynb` | Running the **Optimize wizard**: eval/optimization model selection, exporting a candidate | Portal + CODE |
| 05 | `05_validate_candidate_contract.ipynb` | Deterministic contract gating of an optimized candidate | CLI |
| 06 | `06_resolve_semantic_rules_with_judge.ipynb` | **LLM-judge** resolution of semantic rules, self-preference-bias check | CLI |
| 07 | `07_evaluate_optimized_candidate.ipynb` | Held-out evaluation, replicate seeds, when a score delta is real | CLI |
| 08 | `08_compare_to_open_baseline.ipynb` | Foundry vs. the open, reproducible **DSPy MIPROv2** baseline; cross-run similarity | CLI (real run optional) |
| 09 | `09_assemble_final_report.ipynb` | Rolling every artifact into one promotion decision | CODE |

Each notebook is labeled the same way the pack's own
[`docs/experiment-runbook.md`](../prompt-agent-optimizer-baselines/docs/experiment-runbook.md) labels
its steps:

| Label | What it means |
|---|---|
| **CLI** | Runs from the notebook kernel, no cost, no API key required. |
| **CLI (real run)** | Makes real model calls and costs money — always shown alongside a free smoke-test alternative. |
| **Portal** | A manual step in the Foundry Optimize wizard, written as numbered instructions rather than code. |
| **CODE** | Standalone Python, no Foundry call. |

## Running the series

```bash
cd notebooks
jupyter notebook   # or: jupyter lab
```

Run the notebooks in order the first time — 04 onward depends on files earlier notebooks produce
(a candidate under `<agent>/candidates/`, a run manifest under `runs/<agent_id>/`). After that, each
notebook is a standalone procedure you can re-run for a new agent or a new run.

**No live Foundry portal access in this checkout's environment?** Every **Portal** step is written as
manual instructions, not code you're expected to run non-interactively. Notebook 04 writes a
stand-in candidate file at the same path a real portal export would use, specifically so notebooks
05-09 stay runnable end to end without portal access. Replace that file with your own exported
candidate the moment you have one — nothing downstream needs to change.

Generated artifacts (exported candidates, run manifests, wizard upload files, similarity reports) are
git-ignored — they're reproducible by re-running the notebooks, not checked in.
