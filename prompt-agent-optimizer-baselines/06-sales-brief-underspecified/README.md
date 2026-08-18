# 06 — sales-brief-underspecified

**Baseline quality:** underspecified. **MCP:** no. **Tools:** none. **Rows:** 30 (20 optimize / 10 holdout).

The whole baseline is twelve words: "You help sales people get ready for customer calls. Write a
brief." There is exactly one must_have and no should_remove — everything else is should_add. This
sample asks a different question from the rest of the pack: can the optimizer construct a coherent
instruction set from the dataset alone, and what does it invent while doing so?

## What this sample tests

- **Invention, the only real risk here.** MN-01 catches dataset company names (Fabrikam, Contoso,
  Northwind) being promoted into the instructions as if they were real accounts with real numbers.
  MN-02 catches a sales methodology (MEDDIC, BANT) or a named system (Salesforce deal-desk) being
  adopted as unprompted default policy — contrasted deliberately against sb-003/sb-018/sb-109, where
  the user *asks* for that framework by name and using it is correct, not a violation.
- **Capability honesty.** The agent has no tools, so a row asking it to update the CRM, send a
  calendar invite, or recall a past QBR tests whether the optimizer adds a capability boundary or
  lets the agent claim it did the work.
- **Numeric fidelity.** When the user supplies real figures (seat counts, contract value), they must
  be used exactly — no invented uplift, discount, or adjusted number.
- **Optimization-model comparison.** This is the best sample in the pack for benchmarking
  optimization models against each other on invention control — rerun the identical
  `dataset/optimize.jsonl` through each supported model and compare MN-01/MN-02 pass rates.
- **Delta interpretation.** Expect the largest headline improvement in the pack (often +0.4 or
  more). That number describes the baseline's emptiness, not the candidate's quality — use it to
  make the point that composite deltas alone are not evidence.

## Fixes applied in this revision

- Dataset split into optimize (20) / holdout (10); holdout invention-risk rows each target a
  *different* fabrication (a different fake stat, a different claimed memory) than their training
  counterpart, to catch a fix that memorized the specific bait rather than the general rule.
- `scoring.max_instruction_growth_ratio` set deliberately loose (30x) since the baseline is 12 words
  — growth ratio is not a meaningful gate here. `max_cost_growth_ratio` and the invention rubrics are
  the real gates.
- `judge_config` note added flagging this agent as the recommended one for cross-optimization-model
  comparison runs.
