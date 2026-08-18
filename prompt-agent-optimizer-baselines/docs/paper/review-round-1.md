# Review: Auditing Closed-Loop Prompt Optimization for LLM Agents: A Benchmark and Reproducible Baseline

## Summary of the paper

The paper introduces a ten-agent, 300-item benchmark for auditing whether closed-loop, evaluation-driven
prompt/tool-description optimizers (specifically Microsoft Foundry Agent Service's preview optimizer)
preserve safety-critical, policy-critical, and tool-boundary properties of an agent's instructions while
raising a composite evaluation score. It pairs this benchmark with an open, reproducible DSPy MIPROv2
baseline scored by the same code-level contract, and a detailed statistical protocol (replicate-seed
design, judge self-preference control, Holm-corrected Wilcoxon tests) for comparing the two. Section 6's
results are explicitly, repeatedly labeled as illustrative placeholders; the paper's actual claim at this
stage is about the benchmark design and the experimental/statistical protocol, not about any finding.

## Strengths

- **The core framing is a real, well-argued gap, not a rebranded capability benchmark.** Section 1's
  three-way distinction — APO research measures "did the score go up," agent capability benchmarks
  measure "can the agent do the task," agent safety benchmarks measure "is the agent vulnerable to a
  fixed prompt" — and the claim that none of these hold the *optimizer* under test while measuring
  preservation of properties outside its own reward signal, is specific and, modulo the InjecAgent
  question raised below, appears to be a genuine hole in the landscape rather than an assertion.
- **Section 7 ("How to read the results once they are real") is unusually good practice.** Pre-registering
  the interpretation logic — what a given pattern in Table 3/4/5/6 would and would not license as a
  conclusion — before the real numbers exist is exactly the kind of discipline that prevents post-hoc
  narrative-fitting once real data arrives. Very few draft papers do this.
- **The train/test design is a genuine, well-motivated methodological contribution when it holds.** Making
  every held-out adversarial pattern a *rephrasing* of an optimizer-visible pattern (Section 4.3) is a
  concrete, checkable way to distinguish "the fix generalized" from "the fix pattern-matched the training
  phrasing" — and the agent-by-agent detail in `agent-evaluation-guide.md` (agent 02's fraud-team
  impersonation rephrasing SR-01, agent 07's rephrased injection/severity/capability patterns, agent 10's
  currency/boundary/target swaps) confirms this was actually implemented per-agent, not just asserted.
- **The judge self-preference design (Section 5.5) is a direct, cited methodological response to a known
  failure mode (Panickssery et al., 2024), not a vague nod to it** — disjoint-family primary judge, a
  deliberately same-family cross-judge run in parallel specifically to *measure* the bias, majority-vote
  resolution over repeated judge calls, with the repeat count raised specifically on the one safety-
  critical agent. This is confirmed consistent in `agent-evaluation-guide.md`'s agent 05 section.
- **The limitations section (Section 8) is genuinely honest, not decorative** — it names a closed
  non-deterministic hosted service, a single-baseline comparison, sample-size limits, an MCP-simulation
  gap, a stub-judge smoke-test path that must never be read as data, and unverified citations. This is the
  kind of limitations section the skill this review follows explicitly asks for and rarely gets.
- **Placeholder data is handled correctly.** Every table in Section 6 is unmissably tagged
  `[PLACEHOLDER]` at the cell level, the section opens with a banner stating no claim should be read as a
  finding, and Section 10's conclusion is explicitly marked as a shape-only placeholder. This is exactly
  the standard a draft at this stage should meet, and it is met throughout — no illustrative number is
  presented in a way a careless reader could mistake for a real result.

## Weaknesses

Ordered most serious first. All of these are methodology/design/writing issues that would still need
fixing after real data is plugged in — none is a complaint about placeholder content.

1. **The statistical plan as specified cannot reach its own stated significance threshold at the
   replicate counts the paper (and its own runbook) actually calls for.** With k=5 paired replicate seeds,
   the exact paired Wilcoxon signed-rank test's minimum achievable two-sided p-value is 2/2⁵ = 0.0625 —
   it is mathematically impossible to report p < 0.05 for any single agent at k=5, regardless of effect
   size. `experiment-runbook.md`'s actual minimum bar ("at least three... replicate seeds," and its
   "Definition of done" checklist requiring only "At least 3 replicate runs") makes this worse: at k=3 the
   floor is 2/2³ = 0.25. After Holm-Bonferroni correction across ten per-agent comparisons, the strictest
   comparison must beat α/10 = 0.005, which requires k ≥ 9–10 even in principle. As written, Section 5.6's
   headline statistical test is structurally incapable of ever reporting a significant per-agent result —
   this would remain true even with a perfect, fully-run experiment.
2. **The "elect-and-reoptimize" (iterative refinement) design leaks the holdout split into the
   optimization process it is meant to be held out from.** `experiment-runbook.md`'s procedure for this
   condition (Step 7) is explicit: score Run 1 and Run 2 on `dataset/holdout.jsonl`, elect whichever
   scores higher, and use the elected candidate as the seed for Run 3 — which is then itself evaluated on
   the same holdout split for the paper's reported numbers. This directly contradicts the paper's central,
   repeated claim (Abstract; Section 4.3; Section 5.2) that the holdout split is "never shown to the
   optimizer" and exists specifically "to guard against the optimizer being credited for fitting the same
   data it was evaluated on." Section 5.4 carefully guards against one validity failure in this design
   (order-statistic selection bias from `max(run1, run2)`) but says nothing about this second, more basic
   leakage path.
3. **Section 4.2 misdescribes its own contract structure.** The paper states the six categories split so
   that "the first three gate promotion when marked critical severity and the latter three are advisory."
   `agent-evaluation-guide.md`'s own category table says `should_edit` gates promotion "when marked
   critical," in the identical way to `must_have`/`should_remove`/`must_not_appear` — it is not purely
   advisory like `should_add`/`nice_to_have`. This is not a stylistic quibble: it means Table 4's
   "promotion-gate pass rate," defined only via `regression_blocks` tests, does not correspond to the full
   set of things that gate promotion per the guide's own "What counts as a promotable candidate" section
   (which also includes unresolved semantic rules and growth-ratio bounds).
4. **The composite score reported in Table 3 is never actually defined.** Section 5.3 describes two
   scoring *layers* (instruction-level, response-level) but never states the formula that turns them into
   the single float per agent/system that Table 3 reports as "Mean holdout composite score." Without this,
   a reader cannot tell whether a `must_have` failure zeroes the score, subtracts a fixed penalty, or is
   folded in as one term among many — which matters enormously for interpreting any real number that later
   replaces the placeholders.
5. **The "17–23 agent_tests, roughly half tagged `regression_blocks`" claim (Section 4.2) does not match
   at least one agent as documented.** `agent-evaluation-guide.md`'s agent 05 section states "Ten on
   `optimize.jsonl` (nine of the ten are gating); three held out" — a total of 13 agent_tests (below the
   paper's stated 17–23 range) of which at least 9/13 (69%, likely more once the three held-out tests are
   counted) are gating, not "roughly half." This needs to be checked against every agent's actual
   `expectations.json`, not just asserted as a pack-wide average.
6. **Table 1's characterization of InjecAgent is in tension with InjecAgent's own cited title**, and the
   paper's novelty claim for agent 07 rests on it. Table 1 lists InjecAgent as testing only "user-turn
   injection," but the paper's own reference entry is "InjecAgent: Benchmarking **Indirect** Prompt
   Injections in **Tool-Integrated** Large Language Model Agents" — indirect, tool-mediated injection is
   that benchmark's stated subject, not user-turn injection. Section 2.3's claim that "our injection-via-
   tool-output design... is, to our knowledge, the first to test this specific interaction" needs to be
   re-examined once this is resolved, since it currently rests on a characterization that appears to
   contradict the cited work's own title. Per the reviewing standard this review follows, this is flagged
   for the authors to confirm, not asserted as a fabrication — but it needs resolving before the novelty
   claim can be evaluated.
7. **No citation anchors any of the paper's direct claims about Foundry's own documented behavior**,
   despite Foundry being the paper's primary subject of study and a moving target (public preview).
   Section 1's description of the optimizer's propose/score/select loop, Section 2.1's "the evaluate-
   generate-rank loop Foundry's optimizer documentation describes," and Table 1's "Not documented as
   evaluated" / "Not enforced by the product" cells all read as empirical claims about a real product but
   have no dated, versioned reference behind them anywhere in the References list.
8. **Section 6's placeholder tables are incomplete relative to the paper's own runbook.**
   `experiment-runbook.md` Step 10 lists five tables the paper's results are supposed to assemble,
   including "Instruction and cost growth ratio" — but Section 6 has no corresponding table (6.1–6.4 cover
   only the other four). Similarly, Section 5.4 devotes a full paragraph to how the iterative-refinement
   condition must be analyzed, but no table or column anywhere in Section 6 indicates where its numbers
   will be reported.

## Detailed comments by section

### Abstract
The abstract's central claim — "an explicit train/test split to guard against the optimizer being
credited for fitting the same data it was evaluated on" — is the paper's strongest selling point and is
well executed for the two non-iterative tracks, but is not true for the iterative-refinement condition as
specified in the runbook (Weakness 2). Either qualify this sentence or fix the design. Otherwise the
abstract is precise and appropriately scoped ("we report our experimental design... the results in this
draft are illustrative placeholders") — no overclaiming here.

### Introduction
The three-way gap argument (Section 1, paragraph 3) is the paper's best piece of writing — specific,
falsifiable, and each clause maps to a concrete related-work category addressed in Section 2. Contribution
1's phrase "300 items total, split into a 200-item optimizer-visible set and a 100-item held-out set" is
arithmetically consistent with the per-agent 20/10 split confirmed in `agent-evaluation-guide.md`. No
issues beyond what's covered in Weaknesses above.

### Related work
Section 2.1–2.5 is a genuinely well-organized literature review that places the paper against specific
prior systems rather than gesturing at a field — DSPy/MIPROv2 in particular gets a real structural
comparison (Section 2.1, last paragraph), not just a mention. The exception is the InjecAgent
characterization in Table 1 (Weakness 6), which needs to be resolved since Section 2.6 is where the
paper's comparative novelty claim is made most concretely. Section 2.6's use of "illustrative" in Table
1's caption ("illustrative summary of publicly documented capabilities") uses the same word Section 6 uses
for "known to be fake, placeholder-only" data — these are very different claims (a real if unverified
qualitative judgment vs. a fabricated stand-in number) and sharing the word risks a reader either
dismissing Table 1 as fake or over-trusting Section 6.

### Dataset / materials (Section 4)
The per-agent design (Table 2, Section 4.1) is the paper's strongest asset — ten agents each keyed to one
named, specific failure mode, cross-checked line-by-line against `agent-evaluation-guide.md` and found
accurate on baseline quality, MCP status, tool counts, and primary failure mode for every row. Section
4.2's category-gating description is inaccurate (Weakness 3) and the 17–23/roughly-half claim needs
verification (Weakness 5). Section 4.3's train/test rephrasing design is well-supported by the guide's
per-agent detail (Strengths). Section 4.4 correctly cross-references Table 1 rather than re-arguing the
gap from scratch.

### Methodology (Section 5)
5.1–5.2 are clean and match the runbook's described leakage-control procedure for the two primary tracks.
5.3's scoring description omits how `should_edit` rules (which require detecting that a specific change
was made, not just presence/absence of text) are actually scored — this is a load-bearing rule type in
several agents (01, 04, 05, 07 per the guide) and deserves its own sentence. 5.3 also never states the
composite-score formula (Weakness 4). 5.4's replicate-run design is well-motivated in its treatment of the
order-statistic bias but silent on the more basic holdout-leakage problem in the same design (Weakness 2),
and its "k ≥ 5" is inconsistent with the runbook's actual minimum (Weakness 1, 5). 5.5 is the strongest
subsection in the paper — precise, well-cited, and independently confirmed against the guide's agent 05
detail. 5.6's statistical plan is well-reasoned in its choice of test family (Wilcoxon over paired t-test,
Holm over uncorrected) but the sample-size math undermines it in practice (Weakness 1).

### Results (Section 6)
Correctly and unmissably labeled as placeholder throughout, per the skill this review is written under —
no content-level critique of the numbers themselves is offered, and none should be. The structural gap
(missing growth-ratio table, missing iterative-refinement placeholder — Weakness 8) is a completeness
issue independent of the numbers being fake, and is fixable by adding two more placeholder
tables/subsections in the same style as 6.1–6.4. Table 6 also lacks the "rows omitted, full table will
show N" note that Table 3 has, even though k=5 replicates implies C(5,2)=10 within-track pairs per
agent per track, not the single row shown.

### Limitations (Section 8)
Already a genuine strength (see Strengths). Two omissions worth adding to keep it at the standard the rest
of the section sets: the statistical-power ceiling given the stated/likely k (Weakness 1), and the
holdout-leakage risk specific to the iterative-refinement design (Weakness 2). Both are exactly the kind
of thing this section otherwise does well at naming plainly rather than softening.

### Conclusion (Section 10)
Correctly marked as a placeholder and explicitly says it draws no real conclusions — appropriate for this
draft stage, no issue.

### References
Reasonably comprehensive and, at the level checkable without primary-source access, correctly attributed
to the claims they're cited for — with the one exception flagged in Weakness 6 (InjecAgent). The paper's
own Limitations section already and appropriately flags that citations are unverified against primary
sources; that disclosure is good practice and is not itself a problem. What is missing is any citation for
Foundry's own product documentation (Weakness 7), which is not a "verify against primary source" problem
but a "no citation exists at all" gap for claims about the paper's actual subject of study.

## Questions for the authors

1. What k do you actually intend to run per agent for the submission-ready version? Given the power
   analysis in Weakness 1, is "k ≥ 5" meant as a floor that will be substantially exceeded, or is it the
   intended final number?
2. Is the iterative-refinement ("elect-and-reoptimize") condition planned for all ten agents or a subset —
   and if a subset, which, and on what basis?
3. What is the exact formula that combines instruction-level and response-level scoring into the single
   composite score reported in Table 3? Will the paper report it explicitly, or point to the exact
   function in `_tools/validate_candidate.py`?
4. When the primary/cross-judge kappa (Table 5) comes back low on a given agent, does that invalidate or
   caveat that agent's Table 3/4 numbers in the paper's reporting, or are they reported as-is with the
   kappa noted separately?
5. Can you confirm the exact venue/author details for Opsahl-Ott et al. (2024) and Panickssery et al.
   (2024) — these are the two citations in the reference list with the least standardized public citation
   form among those cited?
6. For agents whose evaluation doesn't fully meet `experiment-runbook.md`'s "Definition of done" checklist
   (e.g., fewer than 3 replicate seeds on one track) by the time of submission, will those agents be
   reported with an explicit caveat, or excluded from the reported tables entirely?

## Required changes

1. **(blocking)** Define, in Section 5.3, the exact formula that produces the single composite score
   reported in Table 3 — how instruction-level and response-level results combine, and how `must_have`/
   `should_remove`/`must_not_appear` failures affect it versus the separate binary gate in Table 4.
2. **(blocking)** Resolve the statistical power problem in Section 5.6: state the minimum achievable
   two-sided p-value at the replicate count you actually plan to run (k=5 floors at 0.0625; Holm-corrected
   across 10 agents requires k≥9–10 even in principle to reach significance at all), and either raise k
   accordingly, restrict the paired-test claim to a clearly labeled secondary/exploratory role behind the
   effect-size and CI reporting, or choose a test suited to the sample sizes this design can actually
   afford.
3. **(blocking)** Reconcile Section 5.4's "k ≥ 5" with `experiment-runbook.md`'s actual minimum ("at least
   three... preferably five"; "Definition of done" requiring only 3). The operational procedure that will
   produce the paper's real numbers must not permit a k lower than whatever the paper's statistical plan
   requires to be meaningful.
4. **(blocking)** Disclose and fix the holdout-split leakage in the iterative-refinement design (Weakness
   2): using `dataset/holdout.jsonl` scores to elect the seed for Run 3, then evaluating Run 3 on the same
   holdout split, contradicts the paper's stated train/test guarantee. Either redesign the elect-and-
   reoptimize procedure to use a third, genuinely unseen split for election, or explicitly and prominently
   scope the abstract's train/test claim to exclude this condition.
5. **(blocking)** Correct Section 4.2's description of the six contract categories: `should_edit` gates
   promotion when marked critical, the same as `must_have`/`should_remove`/`must_not_appear` — it is not
   purely advisory. Update Table 4's caption to state precisely which gating mechanism(s) it reports, or
   broaden it to reflect the guide's full "what counts as a promotable candidate" definition (critical
   contract failures, unresolved semantic rules, gating tests, and growth-ratio bounds).
6. **(blocking)** Verify the "17–23 agent_tests, roughly half `regression_blocks`" claim (Section 4.2)
   against every agent's actual `expectations.json` before any submission-ready version — agent 05 as
   currently documented in `agent-evaluation-guide.md` appears to fall outside both the stated range and
   the stated ratio.
7. **(blocking)** Verify the InjecAgent characterization in Table 1 ("user-turn injection") against the
   actual InjecAgent paper, which by its own cited title concerns indirect, tool-mediated injection. Update
   Table 1 and, if needed, re-scope the novelty claim in Section 2.3/4.4 for agent 07 accordingly.
8. **(blocking)** Add a dated, versioned citation for every direct claim about Foundry's documented
   behavior (Section 1, Section 2.1, Table 1) — Foundry's optimizer is a public preview and a moving
   target, and it is the paper's primary subject of study.
9. **(suggested)** Add a placeholder table for instruction/cost growth ratios in Section 6, matching
   `experiment-runbook.md` Step 10's list of expected paper tables, or state explicitly that it is
   deferred and why.
10. **(suggested)** Add a placeholder table or row for the iterative-refinement condition in Section 6, so
    the results-section skeleton reflects everything Section 5.4 promises to analyze.
11. **(suggested)** Use two different terms for "definitely-fake placeholder data" (Section 6) and "real
    but not independently re-verified qualitative summary" (Table 1's caption) — the shared word
    "illustrative" currently blurs a distinction that matters for how a reader should weight each.
12. **(suggested)** Add the same "rows omitted, N total in the final version" note to Tables 4–6 that
    Table 3 already has, and state how many rows the final versions will contain (e.g., Table 6 implies
    C(5,2)=10 within-track pairs per agent per track at k=5).
13. **(suggested)** Add a decision rule to Section 7's second bullet for distinguishing a genuine
    systematic preservation failure from ordinary run-to-run optimizer stochasticity when a single
    agent/track cell in Table 4 is below 1.0 — as written, any single sub-5/5 cell is treated as
    automatically confirming the paper's central claim.
14. **(suggested)** Add the statistical-power ceiling (item 2) and the iterative-refinement leakage risk
    (item 4) to Section 8's limitations list — both fit the section's otherwise unusually honest standard.
15. **(suggested)** Clarify in Section 5.3 how `should_edit` rules are scored, given they require
    detecting that a specific, targeted change was made rather than checking presence/absence of text —
    the current description (deterministic regex/string checks, or an LLM judge for `semantic` rules)
    doesn't obviously cover this rule type, which is load-bearing in agents 01, 04, 05, and 07.

## Scores

- **Soundness:** 2/4 — the individual design decisions (judge bias control, rephrased holdout patterns,
  shared scoring contract, non-parametric test family) are each well-reasoned, but the statistical plan as
  specified cannot reach its own significance threshold at the replicate counts the paper's own runbook
  permits, the iterative-refinement design leaks the holdout split it's meant to protect, and the paper
  misdescribes its own gating-category structure — all fixable, none fixed yet.
- **Contribution:** 3/4 — the "audit the optimizer, not the agent" framing is specific and, modulo the
  InjecAgent characterization needing correction, appears to be a real, underserved gap; the reproducible
  open-baseline design with a shared scoring contract is a genuine, portable contribution independent of
  continued access to Foundry.
- **Overall recommendation:** Major Revision.

## Meta-review

This is a first full draft that pairs a genuinely well-designed methodological *ambition* — leakage
control, judge self-preference control, a replicate-run design, pre-registered interpretation logic — with
several concrete places where the protocol as actually specified (checked against `agent-evaluation-
guide.md` and `experiment-runbook.md`, which the authors themselves point to as the source of truth) does
not deliver what the paper's prose claims it delivers. None of these is a placeholder-data problem — Section
6 is handled correctly and should not be penalized for being fake — they are protocol problems that would
persist even after a full, honest experimental run. If the authors fix only one thing first, it should be
the statistical power ceiling (Required change 2): as specified, the paired Wilcoxon test at the
replicate counts the runbook actually permits is mathematically incapable of reporting a significant
per-agent result regardless of what the real data shows, which would silently gut Section 7's central
promise — "if Table 4 shows X, that is the paper's central empirical claim made concrete" — without the
authors necessarily noticing why the real numbers, once collected, never confirm anything. Fix that, fix
the holdout leakage in the iterative-refinement design, correct the two internal inconsistencies against
the paper's own supporting documentation (the `should_edit` gating description and the InjecAgent
characterization), and this becomes a strong benchmark-and-baseline paper once real data replaces the
placeholders.
