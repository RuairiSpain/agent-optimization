# Review: Auditing Closed-Loop Prompt Optimization for LLM Agents: A Benchmark and Reproducible Baseline (Round 4)

## Summary of the paper

The paper introduces a ten-agent, 300-item benchmark for auditing whether closed-loop,
evaluation-driven prompt/tool-description optimizers (Microsoft Foundry Agent Service's preview
optimizer, as the paper's primary subject) preserve safety-critical, policy-critical, and
tool-boundary properties of an agent's instructions while raising a composite evaluation score,
paired with an open, reproducible DSPy MIPROv2 baseline and a statistical protocol for comparing the
two. This round reviews two unreviewed passes layered onto the round-3-approved manuscript: a new
Section 2.7 giving a system-by-system comparison against the five closest related harnesses (VeRO,
JTPRO, AgentDojo, AgentLure/Argus, AgentSecBench), and a broad novelty-check pass adding a second
commercial closed-loop optimizer (Amazon Bedrock AgentCore Optimization), three new 2026 citations
(Wan et al./LCO, Li et al./Constraint Drift, Bai & Shi/MAS-PromptBench), and a new Section 2.8
distinguishing the paper's contribution from six commercial prompt-regression-testing products. The
core protocol (Sections 3–5) is untouched by either pass and remains the version rounds 1–3 already
found sound; Section 6 remains correctly, unmissably labeled as placeholder data throughout — not a
finding of this review.

## Strengths

- **Section 2.7's five per-system comparisons are the strongest new writing in this revision, and
  they hold up under a skeptical, source-checking read.** Each of VeRO, JTPRO, AgentDojo,
  AgentLure/Argus, and AgentSecBench gets a genuinely two-sided treatment — what that system's own
  evaluation would catch that this benchmark doesn't (JTPRO's isolated-vs-joint optimization
  question, AgentDojo's attack-surface breadth, AgentSecBench's noninterference formalism), and what
  this benchmark catches that the cited system's own design has no structural place for (a
  before/after comparison across an automated rewrite). The AgentLure paragraph is unusually honest
  for a related-work section: it states plainly that agent 07's fixed injection patterns are "a real
  gap in agent 07's design, not a strength we're claiming," which is exactly the kind of
  self-critical framing the reviewing standard rewards and prior rounds' related-work sections
  sometimes lacked.
- **The LCO/Constraint Drift scoping in Section 2.1 is carefully hedged and does not overclaim.** I
  checked this specifically because it is an easy place to overreach: the paper never claims to be
  "the" empirical instantiation of Li et al.'s call for "Constraint State Governance" — it says this
  paper is "a step toward the kind of empirical instrument their call for governance implies is
  missing, scoped narrowly to the rewrite-time case," which is the correct, defensible framing given
  Li et al. is explicitly a position paper about within-trajectory runtime persistence, not
  rewrite-time persistence. Likewise, LCO is correctly and repeatedly described as "a mitigation
  applied at a single agent's execution time, not an audit of any closed-loop, cross-run optimizer,"
  never as a competing benchmark.
- **The citation-sourcing disclosure in Section 8 was extended consistently, not selectively, to the
  new material.** All eight new-or-recent product/vendor citations (Microsoft, Amazon, and the six
  Section 2.8 platforms) are grouped under one disclosure stating none of these domains were reachable
  from this environment and that all eight are sourced from search-result summaries rather than a
  directly fetched page. This is the same evidentiary standard already applied to Microsoft/Foundry in
  earlier rounds — the paper did not quietly relax its own bar when six more citations arrived at once,
  which would have been an easy place to cut a corner.
- **Round 3's six fixes are all still intact and none have regressed.** I re-checked each: Section 8
  still lists Debenedetti et al. (2024, AgentDojo) among the literature-search-confirmed works;
  Section 5.3 still states explicitly that the partial-overlap tool-call penalty is not a "hard
  violation" for the `regression_blocks` floor; Table 7's caption still correctly distinguishes what
  `run_mipro_baseline.py` computes from what `run_manifest_template.json` merely defines; the
  weight-sensitivity Limitations/Future-Work bullets are present. Two unreviewed editing passes did not
  quietly undo prior fixes.
- **The References list remains correctly alphabetized after all insertions**, and I spot-checked ten
  in-text citations (Wan et al., Li et al., Bai & Shi, Amazon, Braintrust, Confident AI/DeepEval,
  LangChain/LangSmith, LangChain/Promptim, Langfuse, PromptLayer) against the list with no missing or
  duplicate entries found.

## Weaknesses

Ordered most serious first.

1. **Table 1's "Open, reproducible" cell for MAS-PromptBench (Bai & Shi, 2026) says "Yes" with no
   basis anywhere in the paper, and is inconsistent with how every other similarly-recent 2026 preprint
   in the same table is treated.** The paper's own stated rule for this column ("'Not confirmed' in the
   rightmost column means we did not verify a code/data release for that system as part of this
   literature pass") is applied to JTPRO, LCO, AgentLure/Argus, and AgentSecBench — all 2026 arXiv
   preprints added via the same literature-search discipline, none with an independently confirmed
   code/data release. MAS-PromptBench is exactly the same kind of citation (arXiv-only, no venue stated
   in its own References entry, added in the same novelty-check pass as LCO and Constraint Drift, which
   *do* get "Not confirmed"), yet its row alone gets a bare "Yes." VeRO and AgentDojo's "Yes" cells are
   distinguishable because both have a confirmed, code-obligated venue (VeRO: ICML 2026; AgentDojo:
   NeurIPS Datasets and Benchmarks Track) stated directly in their own References entries — no such
   signal exists for MAS-PromptBench. This reads as a slip against the paper's own explicitly stated
   standard, in a paper whose central thesis is that a claim should be checked against evidence rather
   than asserted by default. It is the same category of problem round 3 flagged as blocking (Weakness 2
   there: a citation-provenance claim that doesn't hold up against the paper's own stated rule for
   making it), now recurring in the newest material.
2. **Section 2.7 cites Section 4.1 for a term ("`tool_rules` axis... immutable names/types/enums") that
   Section 4.1 never defines — and no part of the manuscript body defines it anywhere.** The exact
   sentence: "a tool-schema edit that loosens a required parameter's enum or drops a disambiguating
   description — exactly the kind of change our `tool_rules` axis (immutable names/types/enums, Section
   4.1) exists to catch." I checked: `tool_rules` (with its `immutable`, `descriptions_should_improve`,
   and `disambiguation_pairs` sub-fields) is a real, load-bearing part of every agent's
   `expectations.json` and is documented in the repository's own `README.md` — it is not invented — but
   it is never once described in the manuscript itself. Section 4.1 (the design-principle paragraph and
   Table 2) says nothing about it; Section 4.2 (the six gating categories — `must_have`, `should_remove`,
   `must_not_appear`, `should_edit`, `should_add`, `nice_to_have`) is a different part of the same schema
   and doesn't mention `tool_rules` either. This matters beyond a stray pointer: the Abstract advertises
   "tool-boundary correctness" as one of the benchmark's five audited axes, and `tool_rules` is
   apparently the mechanism that implements it, yet a reader who tries to verify that claim from the
   paper text alone — exactly the standard the Abstract sets ("defined precisely enough to be
   re-implemented from the paper alone") — cannot find where tool-boundary correctness is actually
   specified. This is a genuine, newly introduced gap between what Section 2.7 assumes the reader
   already knows and what the rest of the manuscript actually teaches them.
3. **Section 2.8 says "Five platforms" and "these five vendors" while naming and citing six distinct
   products (Braintrust, PromptLayer, LangSmith, Promptim, Langfuse, DeepEval).** On a careful read this
   is reconcilable — LangSmith and Promptim are both LangChain products, so "five platforms" is true if
   counted by company rather than by citation — but the paper never says this explicitly, and Section
   8's own Limitations disclosure describes "the six commercial regression-testing tooling citations,"
   using the *other* number in the very next section. A reader who notices the mismatch has to work out
   the reconciliation themselves; the paper should state it once ("six citations across five vendors,
   since LangChain contributes two") rather than leave two different correct-but-different counts
   sitting unexplained twenty pages apart.
4. **Table 1's Bedrock AgentCore Optimization row asserts a specific optimization scope — "Yes (system
   prompts + tool descriptions)" — that appears nowhere in the running text and is not the quoted claim
   the rest of the paper relies on for this product.** Section 1 and Section 2.8 both ground their
   Bedrock claims in one directly quoted phrase from the vendor's own documentation ("against a defined
   test dataset"); the "system prompts + tool descriptions" specificity in the table has no comparable
   anchor anywhere else in the paper and isn't hedged the way the rest of the Bedrock material carefully
   is (e.g., "not the same as an enforced held-out adversarial split," in the same row). Given the
   paper's own discipline of quoting rather than paraphrasing vendor claims it hasn't independently
   verified, this cell should either get the same quote-or-flag treatment or be softened to match the
   References entry's own `[AUTHOR ACTION]` caveat.
5. **Section 4.4 ("What gap this fills") still only points to "Section 2.6 (Table 1)... Section 2.7,"
   not Section 2.8, even though 2.8 is now part of the paper's overall gap argument.** This is the exact
   pattern round 3 approved when 2.7 was added (4.4 was updated to add "and 2.7" at that time); the same
   update was not made when 2.8 arrived. It's a minor omission — 2.8's argument (differentiation from
   commercial regression-testing infrastructure) is a different axis from 4.4's (differentiation from
   academic benchmarks and methods) — but 4.4 is explicitly the paper's single "here is the gap, stated
   plainly" section, and a reader who reaches it without having separately noticed 2.8 would come away
   with an incomplete picture of the full gap the paper claims to fill.
6. **"From at least two major cloud vendors as of this writing" (Section 1) is technically defensible
   but unhedged as a claim about market breadth.** Exactly two vendors are named (Microsoft, Amazon), no
   others are mentioned anywhere in the paper, and nothing discloses whether this reflects an exhaustive
   check of major agent-hosting platforms (e.g., Google, or other agent-builder products) or simply the
   two the authors happened to find. "At least two" is a true, conservative statement given two named
   instances, but paired with the framing this sentence is doing rhetorical work for (establishing "an
   emerging product category" rather than "one vendor's preview feature," per the commit message that
   introduced this sentence), a reader could reasonably want to know whether this was a systematic
   survey or an opportunistic finding. One clause either way would resolve it.
7. **Two References entries share the identical author-year tag "(LangChain, 2026)" with no
   disambiguator**, for two different products (LangSmith and Promptim). The in-text prose partly works
   around this by naming the product alongside the year ("LangSmith (2026)," "Promptim library
   (LangChain, 2026)"), so a careful reader can resolve it, but this is exactly the kind of citation
   hygiene that normally requires a "2026a"/"2026b" split, and its absence is a real, if minor, gap
   against the paper's stated citation-verification discipline (Section 8).
8. **Table 1's Constraint Drift row is defensible on close reading but the caption doesn't acknowledge
   it as a distinct case.** The caption explains two exceptions to "every row is a peer-reviewed or
   preprint paper" — the Foundry and Bedrock vendor-documentation rows — but says nothing about the fact
   that the Constraint Drift row is scoring a position paper (explicitly "no benchmark or method
   released") against six columns built for systems that do something empirically. The row's own cells
   are careful (`N/A (position paper)` in the rightmost column, a bespoke "Argues for it, does not
   measure it" cell rather than a bare No/N/A), so this isn't a factual error, but the caption — which
   already goes out of its way to explain Foundry's and Bedrock's provenance — is the natural place to
   also tell the reader how to read a row that isn't a system at all, and currently doesn't.

## Detailed comments by section

### Abstract
Unchanged from the version round 3 approved. No new issues.

### Introduction
The Bedrock AgentCore paragraph (new) is well-integrated and its central quote ("against a defined
test dataset") is used consistently everywhere it recurs later (Table 1, Section 2.8). The "at least
two major cloud vendors" phrase is the one soft spot (Weakness 6) — worth one clarifying clause, not a
rewrite. The Wan et al./Li et al. paragraph is appropriately scoped (see Strengths) and does not
overclaim relative to either cited work's actual contents.

### Related work
This is where nearly all of this round's findings live. Section 2.1's three new paragraphs
(MAS-PromptBench, LCO, Constraint Drift) are well-written and correctly scoped. Section 2.6/Table 1
carries two concrete problems: the MAS-PromptBench reproducibility-status inconsistency (Weakness 1,
the most important finding in this review) and the Bedrock scope claim without a text anchor (Weakness
4); the Constraint Drift row's caption gap (Weakness 8) is minor. Section 2.7 is excellent
related-work writing let down by one broken internal pointer (Weakness 2) that a reader relying on the
paper text alone cannot resolve. Section 2.8 is a needed and well-argued addition — the two
distinctions it draws (what fills the test suite; whether leakage is structurally prevented) are the
right ones and are specific rather than generic — but its "five platforms" framing needs to be
reconciled with Section 8's "six citations" framing (Weakness 3), and Section 4.4 should point to it
(Weakness 5).

### Dataset / materials (Section 4)
Untouched by this round's two passes and not re-audited in depth here, consistent with the task scope;
no new issues found in what I did check (Sections 4.1–4.4 as referenced from the new material).
Worth noting for the authors: Section 4 is where the missing `tool_rules` description (Weakness 2)
should actually be added, since 4.1/4.2 are the natural home for it and it's currently documented only
in the repository's `README.md`, not the paper.

### Methodology (Section 5)
Untouched by this round's two passes; round 3's verification of 5.3 and 5.6 stands and I found no
regressions when tracing the new Section 2.7 material's claims about the scoring mechanism (e.g., the
`forbidden` tool-call-policy reference in the JTPRO paragraph) back against Section 5.3's actual
formula — they match.

### Results (Section 6)
Correctly and unmissably labeled as placeholder throughout; no content-level critique, consistent with
the reviewing standard.

### Limitations (Section 8)
The citation-sourcing disclosure was extended correctly and even-handedly to all eight new
product/vendor citations (Strength above). The one issue is the "six... citations" vs. Section 2.8's
"five platforms" numbering mismatch (Weakness 3), which surfaces here as much as in 2.8 itself since
this is the section that states the "six" count.

### Conclusion
Correctly marked as a placeholder; no issue.

### References
Alphabetization is intact after all insertions (verified: Alpay → Amazon → Andriushchenko → Bai →
Braintrust → Confident AI → Debenedetti → Demšar → Dietterich → ... → Zhou, Y., with every letter
transition correct, including the trickier cases: "Confident AI" before "Debenedetti," "LangChain"
before "Langfuse," "Wan" before "Wang"). No duplicate or orphaned entries found in a ten-citation
spot-check. The one real gap is Weakness 7 — two same-year LangChain entries with no a/b
disambiguator — which is a citation-hygiene issue localized to the References list itself rather than
a cross-reference problem.

## Questions for the authors

1. For MAS-PromptBench: was a code/data release actually confirmed during the novelty-check search
   (in which case Table 1 should say so and cite the basis), or was "Yes" simply copied from a
   different row / assumed by default? If the latter, was the same assumption checked against the other
   three 2026-preprint rows that instead say "Not confirmed"?
2. Is there a reason `tool_rules` was left undocumented in the manuscript body while `must_have`/
   `should_remove`/`must_not_appear`/`should_edit`/`should_add`/`nice_to_have` were fully described in
   Section 4.2? Was this an intentional scoping decision (e.g., planned for a later revision) or an
   oversight from focusing 4.1/4.2 on the gating-severity schema rather than the tool-schema-immutability
   schema?
3. Was the Bedrock AgentCore "system prompts + tool descriptions" scope claim (Table 1) drawn from the
   same literature-search pass that produced the "against a defined test dataset" quote, or from a
   different, less-verified source? If the former, the text elsewhere should carry the same quote or
   citation anchor; if the latter, it should carry the same hedge the References entry already does.

## Required changes

1. **(blocking)** Correct Table 1's "Open, reproducible" cell for MAS-PromptBench (Bai & Shi, 2026) to
   "Not confirmed," consistent with how JTPRO, LCO, and AgentLure/Argus — all 2026 preprints added under
   the identical literature-search discipline with no independently confirmed code/data release — are
   already treated in the same table, or provide the specific basis for "Yes" if one genuinely exists
   (e.g., a confirmed venue or a located repository) and state it in the row or a footnote.
2. **(blocking)** Fix Section 2.7's `tool_rules` cross-reference. Either (a) add a short description of
   the `tool_rules` schema (immutable names/types/enums, description-quality flags, disambiguation
   pairs) to Section 4.1 or 4.2 and keep the pointer, or (b) point Section 2.7's citation to wherever the
   schema is actually described once added. As written, "Section 4.1" resolves to nothing that defines
   the term, which undercuts the Abstract's "re-implementable from the paper alone" claim for one of the
   benchmark's five stated audit axes (tool-boundary correctness).
3. **(suggested)** Reconcile Section 2.8's "five platforms"/"these five vendors" with Section 8's "six
   ... citations" — state once, in either section, that six citations span five vendors because
   LangChain contributes two (LangSmith and Promptim).
4. **(suggested)** Either source the "system prompts + tool descriptions" claim in Table 1's Bedrock row
   with the same rigor as the "against a defined test dataset" quote it sits next to, or soften it to
   match the row's own hedged treatment of the rest of Bedrock's documented behavior.
5. **(suggested)** Add "and 2.8" to Section 4.4's opening cross-reference sentence, or add one sentence
   there acknowledging the commercial-tooling distinction 2.8 draws, so the paper's single "what gap this
   fills" section reflects the full related-work landscape as it now stands.
6. **(suggested)** Add one clause to Section 1's "at least two major cloud vendors" sentence disclosing
   whether this reflects a systematic vendor check or the two instances the authors happened to find.
7. **(suggested)** Disambiguate the two "LangChain. (2026)" References entries (LangSmith, Promptim)
   with "2026a"/"2026b" suffixes, updating the in-text citations to match.
8. **(suggested)** Extend Table 1's caption to note that the Constraint Drift row scores a position
   paper (no released system) against columns built for evaluated systems, and briefly state the
   No-vs-N/A convention used for it, alongside the existing Foundry/Bedrock provenance caveat.

## Scores

- **Soundness:** 3/4 — the core protocol (Sections 3–5), independently re-verified in round 3, remains
  untouched and sound. What holds this at 3/4 rather than 4/4 is that the same category of problem round
  3 found in the paper's own paperwork — a claim that doesn't survive a check against the paper's own
  stated standard for making it — recurs in this round's newest material (the MAS-PromptBench
  reproducibility-status slip is a near-exact structural echo of round 3's AgentDojo citation-list
  omission), plus one genuinely broken internal cross-reference (`tool_rules` → Section 4.1) that a
  reader cannot resolve from the manuscript alone.
- **Contribution:** 4/4 — Section 2.7's per-system, two-sided comparisons ("what they'd catch that we
  don't, what we'd catch that they don't") are exactly the comparable-terms delta the standard for this
  score requires, applied individually to every close neighbor rather than asserted in aggregate; Section
  2.8 closes the remaining plausible objection (an infrastructure vendor already does this) with the same
  rigor. The contribution claim is now about as thoroughly defended against near-neighbors as related-work
  writing reasonably gets.
- **Overall recommendation:** Minor Revision.

## Meta-review

This round finds no structural problems — nothing here touches the statistical design, the scoring
formula, the leakage controls, or any other part of the protocol rounds 1–3 already stress-tested. What
it finds is a second instance of a pattern round 3 first named: material added in a fast, unreviewed
pass (here, two passes back to back) is slightly less carefully cross-checked against the paper's own
stated standards than the core manuscript is. The MAS-PromptBench "Yes" in Table 1 is the sharpest
example — it is precisely the kind of unverified-but-confident-looking cell the paper's own "Not
confirmed" convention exists to prevent, sitting two rows away from three other 2026 preprints that get
the more honest label. If the authors fix only one thing first, it should be that cell, for the same
reason round 3's meta-review gave for its top item: this paper's entire premise is that a claim should
be checked against what actually happened rather than accepted by default, and a related-work table is
not exempt from that standard just because it's qualitative rather than experimental. None of this
round's findings require touching Section 5 or the experimental design, and all eight required changes
are fixable in an afternoon without materially changing any claim already made. Once they're addressed,
the paper's remaining path to Accept is exactly what round 3 already identified: Phase 1 (the Foundry
harness) and Phase 2 (a real experimental run), not anything wrong with the manuscript's own reasoning.
