# 01 — travel-approval-strict

**Baseline quality:** good. **MCP:** no. **Tools:** 3 function tools. **Rows:** 30 (20 optimize / 10 holdout).

Control sample and one of two cross-agent replicates for the H0 (stability) hypothesis — see
`09-code-review-assistant-strict` for the second, unrelated-domain replicate. The baseline already
follows instruction best practice: a clear role, non-negotiable numeric thresholds, a procedure that
calls tools before deciding, a fixed four-section output contract, and hard boundaries (restricted
destinations, anti-fabrication). The only real flaw is a single hedged closing line.

## What this sample tests

- **Preservation under rewrite.** MH-01/03/04 require the four approval tiers, the lodging caps, the
  6-hour business-class rule and the restricted-destination hard stop to survive a rewrite intact.
  Optimizers like to "tidy" numeric policy into softer language — that's a hard fail here.
- **Boundary handling.** The dataset deliberately probes every threshold edge inclusively and
  exclusively: exactly $1,500, exactly $3,000, $3,001, $7,501, lodging at exactly $250/$400, and a
  business-class leg at exactly 6:00 (which should NOT qualify — the rule requires the leg to
  *exceed* 6 hours). The baseline is ambiguous about boundary inclusivity (NH-01); a strong candidate
  resolves it.
- **Rule-conflict precedence.** trv-019 (holdout) asks what happens when the cost is missing but the
  destination is restricted — the restricted-destination check must win regardless.
- **Noise-band discipline.** Because the baseline already scores 0.75-0.9, expect legitimate deltas
  inside the ±0.03 noise band. The point of this sample is showing readers when *not* to deploy a
  candidate despite a positive headline number.

## Fixes applied in this revision (see root `CHANGELOG.md`)

- Dataset split into `dataset/optimize.jsonl` (20 rows, uploadable) and `dataset/holdout.jsonl` (10
  rows, never uploaded — enforced by `_tools/build_foundry_dataset.py`). T-08/T-09 in
  `expected/expectations.json` are scored only against the holdout split.
- `judge_config` pins the primary judge to a model family disjoint from every optimization-model
  option, with a same-family cross-judge kept specifically to measure self-preference bias.
- `scoring.max_cost_growth_ratio` added so a score win is read as a quality/cost trade-off, not a
  free improvement.
