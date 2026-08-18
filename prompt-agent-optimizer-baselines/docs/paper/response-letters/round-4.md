# Response to reviewers — round 4

Responds to [`../review-round-4.md`](../review-round-4.md), the `agent-paper-reviewer` skill's
review of the two unreviewed passes layered onto `paper-v4.md` since round 3: the new Section 2.7
(per-system comparison) and the novelty-check pass (Bedrock AgentCore, LCO, Constraint Drift,
MAS-PromptBench, and Section 2.8's commercial-tooling distinction). Minor Revision, Soundness 3/4,
Contribution 4/4 — no structural problems; both blocking items were the same class of issue round 3
found (a claim that doesn't survive a check against the paper's own stated standard for making it),
now recurring in the newest material rather than the core protocol. Every required change is
addressed below.

| # | Required change | Status | Where |
|---|---|---|---|
| 1 | Table 1's "Open, reproducible" cell for MAS-PromptBench said "Yes" with no basis, inconsistent with how the paper treats every other 2026-preprint-only citation added in the same pass | **Done** | Corrected to "Not confirmed," matching JTPRO, LCO, and AgentLure/Argus's treatment. No code/data release was actually verified for MAS-PromptBench during the original search — this was a slip, not a deliberate distinction. |
| 2 | Section 2.7 cites "Section 4.1" for a `tool_rules` axis that is never defined anywhere in the manuscript body | **Done** | Added a full paragraph to Section 4.2 describing `tool_rules` (`immutable`, `descriptions_should_improve`, `disambiguation_pairs`) as the mechanism implementing the Abstract's tool-boundary-correctness axis; Section 2.7's pointer corrected to Section 4.2 and its field names matched exactly. |
| 3 | Section 2.8 says "five platforms"/"these five vendors" while Section 8 says "six... citations," with no reconciling sentence | **Done** | Section 2.8's opening sentence now states "six citations across five vendors... LangChain contributes two" once, up front. |
| 4 | Table 1's Bedrock row asserts "system prompts + tool descriptions" scope with no anchor anywhere else in the paper, unlike the carefully quoted/hedged rest of the row | **Done** | Softened to state the scope is not independently confirmed beyond Amazon's own "recommendations" language, pointing to the References entry's `[AUTHOR ACTION]` caveat rather than asserting unsourced specificity. |
| 5 | Section 4.4 ("What gap this fills") points to 2.6 and 2.7 but not 2.8 | **Done** | Added a clause naming Section 2.8's distinct axis (commercial infrastructure vs. academic near-neighbors) to Section 4.4's opening sentence. |
| 6 | "At least two major cloud vendors" (Section 1) doesn't disclose whether this reflects a systematic survey or an opportunistic finding | **Done** | Added a clause stating the two were found opportunistically during this paper's search, not a systematic survey, so "at least two" is a floor, not an exhaustive count. |
| 7 | Two References entries share the identical tag "(LangChain, 2026)" with no disambiguator | **Done** | Split into `LangChain. (2026a)` (LangSmith) and `LangChain. (2026b)` (Promptim); both in-text citations updated to match. |
| 8 | Table 1's caption explains the Foundry/Bedrock vendor-documentation exceptions but not that the Constraint Drift row scores a position paper against columns built for evaluated systems | **Done** | Added a third exception to the caption explaining the Constraint Drift row's cells describe an argument, not a result, and why its cells aren't a bare No/N/A. |

All three of round 4's questions for the authors are answered by the changes above: Q1 by item 1
(no release was actually confirmed — this was a slip), Q2 by item 2 (oversight from focusing 4.1/4.2
on the gating-severity schema; now fixed, not an intentional scoping decision), Q3 by item 4 (the
Bedrock scope claim was less-verified than the dataset quote and is now hedged accordingly).
