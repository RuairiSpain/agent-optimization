# Paper draft and review trail

This folder holds the paper draft through its revision passes, plus the reviewer feedback that
drove each revision. Two review sources exist:

1. **The internal reviewer persona** — a distinct, strict senior editor-in-chief for a top-tier
   AI/agents venue, defined as a reusable project skill at
   [`.claude/skills/agent-paper-reviewer/SKILL.md`](../../../.claude/skills/agent-paper-reviewer/SKILL.md).
   Not the same voice that wrote the paper. Read the skill file for the review persona and protocol.
   This ran two rounds, per the original three-pass plan (v1 → review → v2 → review → v3).
2. **An external journal review** of `paper-v3.md`, pasted into this project from outside the
   internal skill cycle. Its response is `response-letters/external-journal-review.md`, and the
   revision it produced is `paper-v4.md`. `docs/publication-plan.md` (one level up, in
   `docs/paper/`) is the fuller triage of that review, including which items need live Foundry
   access, a real experimental run, or a human rater before they can be resolved at all — read that
   first if you want the "why," not just the "what changed."

Every response to a review round lives in `response-letters/`, separate from the manuscript itself —
this keeps the paper file readable as a paper, not a revision log. Each manuscript version's own
"Draft status" line names which response letter(s) it addresses.

## Trail

| File | What it is |
|---|---|
| `paper-v1.md` | First full draft. Every result in Section 6 is explicitly labeled illustrative placeholder data — this draft exists to show the paper's intended shape and to be reviewed, not to be cited. |
| `review-round-1.md` | The internal reviewer's structured review of `paper-v1.md`. |
| `response-letters/round-1.md` | Response to round 1, mapping every required change to what changed and where. |
| `paper-v2.md` | Revision addressing every required change from round 1. |
| `review-round-2.md` | The internal reviewer's structured review of `paper-v2.md`. |
| `response-letters/round-2.md` | Response to round 2. |
| `paper-v3.md` | Revision addressing every required change from round 2 — the last version produced entirely within the internal three-pass plan. |
| `response-letters/external-journal-review.md` | Response to the external journal review of `paper-v3.md`; full triage in `publication-plan.md`. |
| `publication-plan.md` | The fuller plan for getting this paper publication-ready: statistical redesign detail, literature verification, phased roadmap (what's buildable now vs. what needs live access/budget/human raters), and venue strategy. |
| `paper-v4.md` | Current manuscript. Addresses the external review's Phase 0 items (statistical fix, related work, cost metric, Table 1 boundary note) and is the first version with the response-to-reviewers scaffolding moved out of the manuscript body entirely. |

## Status

Every pass here was produced without a real experimental run behind it — the paper's results
section is, and remains through every version, a template for what the real results table will look
like once `docs/experiment-runbook.md` has actually been executed against real Foundry and DSPy
optimization runs. Nothing in any version of this paper should be cited as an experimental finding.
Treat `paper-v4.md` as the structural and methodological template to fill in with real data (per
`publication-plan.md`'s Phases 1-4), not as a finished, submittable paper.
