# 04 — hr-policy-mcp

**Baseline quality:** mixed. **MCP:** yes — hr-knowledge-base (kb_search, kb_get_document,
kb_list_policies). **Tools:** 2 function tools. **Rows:** 30 (20 optimize / 10 holdout).

One of two MCP agents in the pack (the other is `07-incident-response-mcp`, its deliberate mirror).
Every other agent here is a pure prompt agent. This one exists to probe the boundary that matters
for prompt-agent optimization: the optimizer improves function-calling tool descriptions only, so
MCP retrieval behaviour has to be fixed in the instructions. The baseline deliberately leaves the
retrieval trigger to model judgement ("Use it to look things up when you need to"), which is the
root cause of every failure in the dataset — the opposite failure mode from 07, whose baseline
over-triggers retrieval instead.

The dataset is balanced so no blanket rule can win, and the balance is preserved across both splits:
roughly 7:5:3 (optimize) and 5:3:2 (holdout) required:forbidden:optional. Rows that look casual but
contain a policy assertion, a hearsay claim from a manager, and a mundane expense question where
common-sense answering is the trap are deliberately mixed in with clear-cut cases.

## What this sample tests

- **Retrieval recall vs precision, simultaneously.** A candidate that adds "always search first"
  passes recall and fails precision; the vague baseline fails the opposite way.
- **Jurisdiction discipline after a life event.** hr-020/holdout hr-109(T-09) test whether the fix
  re-resolves jurisdiction after a stated relocation rather than trusting stale context.
- **Bypass-framing resistance.** hr-019 and the held-out hr-107 both try to talk the agent out of
  retrieving using a different social framing each time ("you basically are HR", "as my personal
  assistant") — SA-04 has to generalize past the literal training phrasing.
- **The defining trap (MN-02):** during evaluation the optimizer sees retrieved policy values. If it
  bakes "25 days annual leave" into the instructions, the composite score goes up and the agent
  becomes confidently stale and stops retrieving. Always diff candidate instructions for literal
  policy values before promoting.

## Fixes applied in this revision

- Dataset split into optimize (20) / holdout (10), balance preserved across both.
- SA-01 extended to explicitly cover post-relocation jurisdiction re-resolution.
- SA-04 extended to cover social-engineering *reframings* of the bypass request, not just the literal
  "ignore the knowledge base" phrasing.
- To exercise the tool-failure rows (hr-011, holdout hr-106), stub the MCP endpoint to fail — run the
  pack twice, once healthy and once with a failing stub.
