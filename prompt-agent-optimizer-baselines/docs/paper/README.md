# Paper draft and review trail

This folder holds the paper draft through its three required revision passes, plus the reviewer
feedback that drove each revision. The reviewer is a distinct persona — a strict, senior
editor-in-chief for a top-tier AI/agents venue — defined as a reusable project skill at
[`.claude/skills/agent-paper-reviewer/SKILL.md`](../../../.claude/skills/agent-paper-reviewer/SKILL.md),
not the same voice that wrote the paper. Read the skill file for the review persona and protocol.

## Trail

| File | What it is |
|---|---|
| `paper-v1.md` | First full draft. Every result in Section 6 is explicitly labeled illustrative placeholder data — this draft exists to show the paper's intended shape and to be reviewed, not to be cited. |
| `review-round-1.md` | The reviewer's structured review of `paper-v1.md`. |
| `paper-v2.md` | Revision addressing every required change from round 1, with a response-to-reviewers note at the top. |
| `review-round-2.md` | The reviewer's structured review of `paper-v2.md`. |
| `paper-v3.md` | Final revision addressing every required change from round 2. |

## Status

All three passes here were produced without a real experimental run behind them — the paper's
results section is, and remains through all three versions, a template for what the real results
table will look like once `docs/experiment-runbook.md` has actually been executed against real
Foundry and DSPy optimization runs. Nothing in any version of this paper should be cited as an
experimental finding. Treat `paper-v3.md` as the structural and methodological template to fill in
with real data, not as a finished, submittable paper.
