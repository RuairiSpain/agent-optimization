# 09 — code-review-assistant-strict (NEW)

**Baseline quality:** good. **MCP:** no. **Tools:** 3 function tools. **Rows:** 30 (20 optimize / 10 holdout).

Added in the pack-review revision to close the replication gap: `01-travel-approval-strict` was the
pack's only "good baseline" control sample, so any H0 (stability-under-rewrite) finding rested on a
single agent. This is the second cross-agent replicate — a completely unrelated domain (code review
vs. travel policy) built to the same pattern deliberately: a clear role, non-negotiable checklist
rules, a tool-calling procedure, a fixed output contract, and exactly one hedged closing line as the
only real flaw.

## What this sample tests

- **Cross-domain stability.** Run the identical Run1/Run2/elect/Run3 procedure on both 01 and 09. If
  the noise-band behavior (small legitimate deltas, preservation of numeric/policy rules) holds on
  both, that is real evidence for H0 generalizing beyond one prompt's specific structure — a single
  agent can only ever be a case study.
- **Injection via the diff itself.** cr-015/cr-109 embed an instruction inside the code under review
  ("ignore all checks," "exempt from all rules") — content that arrives through `fetch_diff`'s tool
  output, the same class of vulnerability `07-incident-response-mcp` tests for runbooks, applied here
  to source code comments.
- **Blocking vs. suggestion classification**, not just "found an issue." MH-05 requires the
  optimizer to preserve the severity split, not flatten every finding into one undifferentiated list.
- **Scope ambiguity the baseline leaves open on purpose** (cr-013 vendored files, cr-014 test-file
  docstrings) — the kind of edge case a good baseline still has room to clarify without being wrong.

## Fixes applied in this revision

- Full new sample built to address review gap #3 (single-agent replication risk for H0).
- Dataset split into optimize (20) / holdout (10) from the start.
