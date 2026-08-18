---
title: "Auditing Closed-Loop Prompt Optimization for LLM Agents: A Benchmark and Reproducible Baseline"
status: "DRAFT v2 — revised per review-round-1.md. Contains placeholder experimental data, clearly marked. Not for submission."
---

# Response to reviewers — round 1

We thank the reviewer for a review that found real, load-bearing problems in the protocol, not just
in the (correctly, intentionally) placeholder results. Every blocking required change is addressed
below; every suggested change is applied. Two changes reached outside the paper itself into
`docs/experiment-runbook.md` and `_baselines/dspy_mipro/run_mipro_baseline.py`, since the reviewer
verified the paper's claims by cross-checking those files directly and found the inconsistency
lived partly in them, not only in the paper's prose.

| # | Required change | Status | Where |
|---|---|---|---|
| 1 | Define the composite-score formula | **Done** | §5.3 now states the exact formula and clarifies instruction-level `blocked` and response-level composite score are reported as two separate numbers by design, never combined into one |
| 2 | Fix the statistical power ceiling | **Done** | §5.6 now states the exact minimum-p-value formula, requires k ≥ 9 (we specify k = 10) for any Holm-corrected significance claim, and makes the bootstrap CI and effect size the primary report at any k |
| 3 | Reconcile k across paper and runbook | **Done** | `experiment-runbook.md` Step 7 rewritten to state the k ≥ 9 / k = 10 requirement explicitly and match §5.6 |
| 4 | Fix holdout leakage in elect-and-reoptimize | **Done** | Election now uses MIPROv2's own internal validation slice of `dataset/optimize.jsonl` (a new `run_manifest.json` field), never `dataset/holdout.jsonl`; `run_mipro_baseline.py` updated to compute and record this score |
| 5 | Correct the `should_edit` gating description | **Done** | §4.2 corrected: four categories gate when critical (`must_have`, `should_remove`, `must_not_appear`, `should_edit`), two are purely advisory (`should_add`, `nice_to_have`) |
| 6 | Verify the agent_tests count/ratio claim | **Done** | §4.2 replaced with the actual observed range (9–13 tests per agent, 70–100% gating, mean ≈ 87%), computed directly from all ten agents' `expected/expectations.json` |
| 7 | Verify the InjecAgent characterization | **Done** | §2.3 and Table 1 corrected: InjecAgent does evaluate indirect, tool-mediated injection on a fixed agent; the paper's novelty claim is re-scoped to the optimizer-under-rewrite axis, not the injection-vector axis |
| 8 | Cite Foundry's own documented behavior | **Done** | Added a dated product-documentation reference, cited at every direct claim about Foundry's behavior |
| 9 | Add a growth-ratio results table | **Done** | New Table 7 |
| 10 | Add an iterative-refinement results table | **Done** | New Table 8 |
| 11 | Disambiguate "illustrative" (Table 1) from "placeholder" (§6) | **Done** | Table 1's caption now reads "qualitative, author-assessed" |
| 12 | Add "rows omitted" notes to Tables 4–6 | **Done** | |
| 13 | Add a systematic-vs-stochastic decision rule to §7 | **Done** | |
| 14 | Add the power ceiling and leakage risk to Limitations | **Superseded** | Both are now fixed in the protocol rather than disclosed as open limitations; §8 instead discloses the *cost* of the fix (k = 10 is expensive) as its replacement limitation |
| 15 | Clarify `should_edit` scoring | **Done** | §5.3 states `should_edit` is scored via its `accept_if` criterion through the same regex/semantic/judge pathway as every other rule type |

All six of the reviewer's questions are answered inline in the revised text (§5.3 for Q3, §5.4 for
Q1/Q2/Q6, §5.5 for Q4; Q5's citation-form request is addressed by the note retained in §8).

---

# Auditing closed-loop prompt optimization for LLM agents: a benchmark and reproducible baseline

**Authors:** [author list withheld — internal draft]
**Draft status:** Version 2. All tables in Section 6 contain **illustrative, placeholder data**
generated to show the intended structure of the results, not real experimental findings. See the
banner at the start of Section 6 for the scope of what is and is not real in this draft.

## Abstract

Commercial agent platforms are beginning to ship closed-loop prompt and tool-description optimizers
that automatically rewrite an agent's instructions against a held evaluation set. These systems
promise measurable quality gains with no retraining, but their evaluation loop is itself largely
unaudited: does an automatic rewrite preserve safety-critical constraints, tool-call policy, and
numeric business rules while it improves a composite score? We introduce a ten-agent, 300-item
benchmark purpose-built to audit this class of system along five axes — instruction preservation,
invention control, tool-boundary correctness, prompt-injection robustness (including injection
delivered through tool output rather than the user turn), and multi-turn state handling — with an
explicit train/test split, enforced throughout the experimental protocol including its
iterative-refinement condition, to guard against the optimizer being credited for fitting the same
data it was evaluated on. We use the benchmark to compare Microsoft Foundry Agent Service's closed,
hosted agent optimizer (preview) against an open, reproducible baseline built on DSPy's MIPROv2
optimizer, scored by a single shared, code-level contract so both systems are graded identically. We
report our experimental design, a composite-score formula and gating criteria defined precisely
enough to be re-implemented from the paper alone, and a statistical analysis plan whose sample-size
requirements are derived, not assumed, from the exact test it specifies. The results in this draft
are illustrative placeholders in the reporting format this protocol produces; the protocol itself —
not any result — is this draft's contribution. We release the benchmark, the scoring harness, and
the DSPy baseline implementation.

## 1. Introduction

Automatic prompt optimization has moved from a research technique to a shipped product feature.
Systems that iteratively propose, evaluate, and select instruction rewrites — without gradient
access to the underlying model — are now available as commercial, closed-loop services integrated
directly into agent-hosting platforms. Microsoft Foundry Agent Service's agent optimizer (Microsoft,
2026), in public preview at the time of writing, is one such system: given a baseline agent and an
evaluation dataset, it proposes candidate instructions, tool descriptions, and model choices, scores
each candidate, and returns the highest-scoring configuration for deployment.

This creates a specific and under-examined risk. An optimizer that is rewarded purely for raising a
composite evaluation score has no inherent reason to preserve properties that composite score
doesn't measure — a safety constraint the evaluation rubric didn't happen to test, a tool-call policy
the dataset didn't happen to exercise, a numeric business rule that a paraphrase can silently loosen
without tripping a keyword check. The optimizer is, in effect, an unsupervised editor operating on a
document that encodes an organization's operating policy, judged by a metric that is necessarily an
incomplete proxy for what the organization actually wants preserved.

Existing agent and LLM evaluation benchmarks are not built to audit this failure mode. Prompt
optimization research (Section 2.1) evaluates optimizers on task accuracy, not on whether an
optimizer preserves properties adversarial to its own reward signal. Agent capability benchmarks
(Section 2.2) evaluate whether an agent can complete a task, not whether an *optimizer acting on that
agent* preserves the agent's constraints under rewrite. Agent safety benchmarks (Section 2.3)
evaluate a fixed agent's vulnerability to an attack, not an optimizer's tendency to *introduce or
remove* that vulnerability while rewriting the agent it's evaluating. We are not aware of a benchmark
that sits at this specific intersection: closed-loop optimization of an agent's instructions and
tools, audited for preservation of safety-critical and policy-critical content under
evaluation-driven rewrite.

This paper makes three contributions:

1. **A benchmark** of ten prompt agents (Section 4) spanning good, mixed, poor, and deliberately
   underspecified baseline instruction quality, two agents backed by Model Context Protocol (MCP)
   tool retrieval with opposite retrieval-trigger failure modes, one multi-turn agent, and two
   cross-domain "good baseline" control agents — 300 items total, split into a 200-item
   optimizer-visible set and a 100-item held-out set never shown to the optimizer.
2. **A reproducible open baseline** (Section 5) built on DSPy's MIPROv2 optimizer (Khattab et al.,
   2023; Opsahl-Ott et al., 2024), sharing the identical dataset, contract, and scoring code as the
   closed-system evaluation, so that findings are not contingent on continued access to a specific
   commercial preview product.
3. **An experimental and statistical protocol** (Section 5.4–5.6) for comparing closed-loop
   optimizers that avoids three specific validity failures we identify in naive evaluation designs:
   evaluating an optimizer against the same data it optimized against (including inside a
   multi-run, iterative-refinement condition, where this leak is easy to introduce without
   noticing); treating the best of two stochastic runs as evidence that a third, dependent run
   improves on either individually; and reporting a significance test at a sample size too small
   for that test to be capable of reaching significance regardless of the underlying effect.

We report the benchmark's design and the full statistical protocol we apply to it, specified
precisely enough that a reader could re-derive our sample-size requirements independently (Section
5.6). The results in Section 6 are placeholders showing the intended reporting format; Section 7
states plainly what conclusions would and would not follow once real data replaces them.

## 2. Related work

### 2.1 Automatic prompt optimization

Automatic prompt optimization (APO) methods search over natural-language instructions using an LLM
as both the object of optimization and, often, the optimizer itself. Automatic Prompt Engineer
(Zhou et al., 2022) frames instruction search as black-box program synthesis, using an LLM to
propose candidate instructions and score them against a small held-out set. Optimization by
PROmpting (OPRO; Yang et al., 2023) generalizes this to an iterative loop in which an LLM proposes
new candidates conditioned on the scored history of previous candidates, structurally similar to the
propose-score-select loop Foundry's own optimizer documentation describes (Microsoft, 2026).
EvoPrompt (Guo et al., 2023) and PromptBreeder (Fernando et al., 2023) apply evolutionary operators —
mutation and crossover over instruction text — to the same search problem. PromptAgent (Wang et al.,
2023) frames optimization as planning over an instruction-edit action space using Monte Carlo tree
search. TextGrad (Yuksekgonul et al., 2024) generalizes further, treating natural-language critique
from an LLM as a differentiable-style "gradient" that can be backpropagated through a multi-step LLM
pipeline, not just a single prompt.

DSPy (Khattab et al., 2023) is the closest structural relative to Foundry's optimizer among
open-source systems, and the basis of our reproducible baseline (Section 5). DSPy compiles a
declarative program specification — of which instructions, few-shot demonstrations, and tool use are
all first-class, jointly-optimized components — into an executable pipeline, and its MIPROv2
optimizer (Opsahl-Ott et al., 2024) performs Bayesian-optimization-guided joint search over
instruction and demonstration candidates, closely mirroring the multi-component (instructions, tool
descriptions, model choice) search space Foundry's optimizer exposes (Microsoft, 2026).

None of these methods report an evaluation of whether the optimizer preserves properties of the
original prompt that are outside its own reward signal. Their evaluations are uniformly
accuracy-improvement studies: does the optimized prompt perform better on the target task. We adopt
the search methodology this literature describes but change the evaluation question from "did the
score go up" to "did the score go up without silently breaking something the score didn't measure."

### 2.2 Agent capability benchmarks

AgentBench (Liu et al., 2023) evaluates LLM agents across a suite of interactive environments.
τ-bench (Yao et al., 2024) evaluates an agent's policy compliance in simulated customer-service
domains against a rule set, which is the closest existing benchmark to our own in spirit — but
τ-bench evaluates a fixed agent, not an optimizer's effect on an agent under rewrite. WebArena (Zhou
et al., 2023), GAIA (Mialon et al., 2023), and SWE-bench (Jimenez et al., 2023) evaluate task
completion in web-browsing, general assistant, and software-engineering domains respectively. All
four are capability benchmarks: they answer "can this agent do the task," not "did an automated
process that touched this agent's instructions preserve the properties that made it safe or
compliant to deploy."

### 2.3 Agent safety and injection benchmarks

InjecAgent (Zhan et al., 2024) and AgentHarm (Andriushchenko et al., 2024) evaluate an agent's
susceptibility to malicious instructions and harmful task completion respectively. ToolEmu (Ruan et
al., 2023) simulates tool execution to surface unsafe agent behavior without requiring real tool
side effects. R-Judge (Yuan et al., 2024) evaluates an LLM's ability to *recognize* risk in an agent
trajectory. InjecAgent specifically evaluates **indirect** injection — malicious content arriving
through tool observations rather than the user's own turn — on a fixed agent, which is the same
delivery mechanism our agent 07 (Section 4) uses. Our contribution at this intersection is therefore
narrower and more specific than "tests injection via tool output" in isolation: we are not aware of
prior work evaluating whether a closed-loop *optimizer*, rewriting an agent's instructions under an
evaluation-score objective, preserves, weakens, or repairs an agent's resistance to this class of
injection. InjecAgent and the other benchmarks in this subsection test a fixed agent against an
attack; our benchmark tests whether an automated rewrite process changes that agent's resistance to
the same class of attack, which is a distinct question the injection-benchmark literature does not
address because it does not evaluate an optimizer at all.

### 2.4 LLM-as-judge and evaluation methodology

Zheng et al. (2023) establish LLM-as-judge as a scalable evaluation method and document its
systematic biases. Panickssery et al. (2024) show that LLM judges measurably favor outputs from
models in their own family — a self-preference bias directly relevant to any evaluation design, like
Foundry's, in which an "eval model" scores candidates an "optimization model" produced. Our
experimental protocol (Section 5.5) is a direct methodological response to this finding: every
agent's evaluation contract specifies a primary judge model pinned to a vendor family disjoint from
every supported optimization model, plus a same-family cross-judge run in parallel specifically to
measure, rather than assume away, this bias.

### 2.5 Statistical practice for comparing learned systems

Dietterich (1998) established that naive significance testing over a single train/test split
systematically understates variance for learned systems, motivating replicate-run designs over
single-draw comparisons. Demšar (2006) extends this to comparisons across multiple datasets,
recommending non-parametric tests (Wilcoxon signed-rank) and correction for multiple comparisons
(Holm's method) over the more commonly misapplied paired t-test — both of which we adopt in Section
5.6, along with the sample-size consequence of that choice, which the cited methodology papers do
not by themselves make salient and which we derive explicitly for this benchmark's setting. Gebru et
al. (2018; revised 2021) introduce datasheets for datasets as a standard for documenting a dataset's
provenance, composition, and intended use; our benchmark's documentation (Section 4, and the
accompanying `README.md` and `CHANGELOG.md`) follows this template.

### 2.6 Positioning

Table 1 summarizes the gap this paper addresses.

*Table 1. Coverage comparison against the closest related benchmarks and methods (a qualitative,
author-assessed summary of publicly documented capabilities — not derived from re-running these
systems, and distinct from the placeholder experimental data in Section 6).*

| System | Optimizes agent instructions | Evaluates preservation under rewrite | Train/test separation for the optimizer | Evaluates indirect/tool-output injection | Evaluates an *optimizer's* effect on injection resistance | Open, reproducible |
|---|---|---|---|---|---|---|
| APE / OPRO / EvoPrompt / PromptBreeder | Yes | No | Not specified | No | No | Yes |
| DSPy / MIPROv2 | Yes | No | Configurable, not enforced | No | No | Yes |
| τ-bench | No (evaluates a fixed agent) | N/A | N/A | No | No | Yes |
| InjecAgent | No (evaluates a fixed agent) | N/A | N/A | **Yes** | No | Yes |
| ToolEmu / AgentHarm / R-Judge | No | N/A | N/A | No | No | Yes |
| Foundry agent optimizer (this paper's subject; Microsoft, 2026) | Yes | Not documented as evaluated | Not enforced by the product | No | No | No (closed, hosted) |
| **This work** | Yes (both tracks) | **Yes** | **Enforced throughout the protocol, including the iterative-refinement condition (§5.4)** | Yes (agent 07, adapted from InjecAgent's delivery mechanism) | **Yes** | **Yes (the benchmark and the DSPy baseline; Foundry itself remains closed)** |

## 3. Why we compare against DSPy specifically

We evaluate Foundry's optimizer against an open baseline for a reproducibility reason stated plainly
in Section 1: a closed, versioned, preview-stage commercial product is not something a reader can
independently re-run to verify our findings, and its internal search algorithm is not published, so
a purely qualitative comparison ("Foundry's optimizer resembles OPRO") cannot be verified against
source. We chose DSPy's MIPROv2 as the comparison system for three reasons specific to this
benchmark, not as a general claim that DSPy is the best available open optimizer:

1. **Structural similarity.** MIPROv2 jointly optimizes instructions, few-shot demonstrations, and
   (through DSPy's `ReAct` module) tool-calling behavior in a single compiled program, which is the
   closest open match to Foundry's own multi-component optimization surface (instructions, tool
   descriptions, model choice) among the systems reviewed in Section 2.1.
2. **Programmatic access to the search loop.** Because DSPy exposes the optimizer as a library call
   rather than a hosted black box, we can run replicate seeds under our own control (Section 5.4),
   instrument every tool call the candidate program makes during evaluation (necessary for our
   tool-call-policy scoring; Section 5.3), and pin the exact model versions used, none of which are
   possible against a closed hosted service beyond what its own logs report.
3. **A shared scoring path.** Our DSPy baseline's instruction-level and response-level scoring code
   imports the same contract-checking implementation used to grade an exported Foundry candidate
   (Section 5.3), so a score difference between the two tracks cannot be attributed to a second,
   independently drifted scoring implementation.

We do not claim MIPROv2 is representative of the entire APO literature, and Section 8 states this as
an explicit limitation: a single open baseline is one comparison point, not proof that Foundry's
optimizer is better or worse than automatic prompt optimization in general.

## 4. The benchmark

### 4.1 Design principle

Each of the ten agents is constructed around one specific, named failure mode an optimizer might
introduce or fail to fix, with a machine-checkable contract (`expected/expectations.json`) that
separates gating requirements from advisory ones. Table 2 summarizes the ten agents; full detail,
including every rule ID and its rationale, is in the benchmark's own documentation
(`docs/agent-evaluation-guide.md`).

*Table 2. Benchmark agent summary.*

| # | Agent | Baseline quality | MCP | Tools | Primary failure mode under test |
|---|---|---|---|---|---|
| 01 | `travel-approval-strict` | Good | No | 3 | Stability: does optimization damage an already-good prompt |
| 02 | `support-triage-messy` | Poor | No | 0 | Whether a privacy violation buried in a messy prompt gets removed, not polished around |
| 03 | `invoice-extractor-schema` | Mixed | No | 2 | Verbatim structured-output contract preservation |
| 04 | `hr-policy-mcp` | Mixed | Yes | 2 + 3 MCP | Under-specified retrieval trigger (false negatives) |
| 05 | `clinical-triage-safety` | Mixed | No | 2 | An unsafe tail appended to an otherwise-correct safety prompt |
| 06 | `sales-brief-underspecified` | Underspecified | No | 0 | Invention control on additive optimization from a near-empty baseline |
| 07 | `incident-response-mcp` | Mixed | Yes | 2 + 3 MCP | Over-eager retrieval (false positives) and injection via tool output |
| 08 | `helpdesk-reset-multiturn` | Mixed | No | 2 | Multi-turn state vs. an unverifiable claimed-verification bypass |
| 09 | `code-review-assistant-strict` | Good | No | 3 | Stability, replicated in a second, unrelated domain from agent 01 |
| 10 | `expense-claim-boundary` | Mixed | No | 2 | Financial fabrication and boundary-arithmetic correctness |

### 4.2 Contract structure

Every agent's contract sorts candidate instruction content into six categories. Four gate promotion
when marked `critical` severity: `must_have` (a rule the candidate must contain), `should_remove` (a
dangerous or contradictory baseline line the candidate must not retain), `must_not_appear` (a
pattern the candidate must not introduce, whether or not the baseline had it), and `should_edit` (a
baseline rule that is correct in principle but broken in a specific, checkable way — ambiguous,
contradicted elsewhere, or non-actionable — that the candidate must fix in a stated way). The
remaining two, `should_add` and `nice_to_have`, are purely advisory and never gate promotion.

Each agent additionally defines a set of concrete input/expected-behavior test cases (`agent_tests`).
Counted directly across all ten agents' `expected/expectations.json` files, this ranges from 9 to 13
tests per agent (mean 10.3), of which 70% to 100% (mean ≈ 87%) are tagged `regression_blocks: true`
— a hard promotion gate independent of composite score. Gating tests are the norm in this benchmark,
not roughly half of the total as an earlier draft of this paper stated; most agents' test suites
skew heavily toward gating because most `agent_tests` entries double as the concrete regression check
for that agent's own documented `known_traps`. Gating tests are split across the optimizer-visible
and held-out data partitions (Section 4.3).

### 4.3 Train/test separation

Every agent's 30 items split into a 20-item `optimize` file, the only file ever shown to either
optimizer during search, and a 10-item `holdout` file used exclusively for post-optimization
scoring. Every adversarial or edge-case pattern in the held-out split is a *rephrasing* of a pattern
in the optimizer-visible split — a different currency, a different injected instruction, a different
claimed authority — specifically so that a fix which only pattern-matches the exact training
phrasing is distinguishable from a fix that generalizes the underlying rule.

This separation is enforced by construction in the direct baseline-vs-optimized comparison (Section
5.2), and — after a leakage path we identified and closed during this paper's own review (see the
Response to Reviewers above) — in the iterative-refinement condition as well (Section 5.4): electing
between replicate runs uses only a validation slice of the optimizer-visible data, never the held-out
split, so the held-out score reported for any condition, iterative or not, reflects data no part of
that condition's selection process has seen.

### 4.4 What gap this fills

Section 2.6 (Table 1) states this in comparative terms. Concretely: existing APO benchmarks measure
whether optimization improves a task metric; existing agent benchmarks measure whether a fixed agent
can perform a task or resist an attack, including, in InjecAgent's case, an indirect injection
delivered through tool output. This benchmark is, to our knowledge, the first to hold the
*optimizer* under test while measuring whether its output preserves properties adversarial to its
own objective — safety constraints, tool-call policy, and injection resistance (evaluated using a
delivery mechanism adapted from InjecAgent's, applied here to an optimizer's effect on that
resistance rather than to the resistance itself) — that a composite evaluation score does not
directly reward preserving.

## 5. Methodology

### 5.1 Systems under test

- **Foundry track.** Microsoft Foundry Agent Service's agent optimizer, accessed through the
  Optimize wizard (public preview; Microsoft, 2026). Optimization model and eval model are
  configured per the platform's supported list; see Section 5.5 for the eval-model pinning rule we
  apply.
- **DSPy track.** DSPy's `MIPROv2` teleprompter (Opsahl-Ott et al., 2024), compiled against a
  `dspy.ChainOfThought` or `dspy.ReAct` program per agent (Section 3), run under our own control
  with pinned model versions.

### 5.2 Leakage control

Both tracks optimize exclusively against each agent's 20-item `optimize` split (Section 4.3). Final
scoring for every reported number in Section 6 uses the 10-item `holdout` split, which neither
optimizer sees during search, and which no run-selection decision (Section 5.4) depends on either.
We treat a score computed on the `optimize` split alone as non-reportable evidence of generalization,
consistent with standard train/test discipline in supervised learning (Dietterich, 1998) applied
here to a search-based rather than gradient-based optimizer.

### 5.3 Scoring

Two scoring layers apply to every candidate, on both tracks, using a single shared implementation
(`_tools/validate_candidate.py`, imported directly by the DSPy baseline rather than reimplemented),
and — by design — they are reported as two **separate** numbers, never combined into one, so that a
composite-score improvement can never numerically mask a contract failure:

- **Instruction-level contract check** (reported in Table 4). Every `must_have`, `should_remove`,
  and `must_not_appear` rule is checked against the optimized instructions text: deterministic
  regex/string rules are checked directly; `semantic` rules are resolved by an LLM judge (Section
  5.5) rather than left unscored. `should_edit` rules are checked through the identical mechanism,
  applied to each rule's `accept_if` criterion (a regex or semantic statement describing the
  *required fix*) rather than to its `current_text` field, which serves only as a diagnostic marker
  of whether the original problematic phrasing is still present. A single `critical`-severity
  failure in any of the four gating categories (Section 4.2) sets a candidate's `blocked` flag to
  true, reported as a boolean per candidate in Table 4 — this is a gate, not a score, and does not
  numerically discount Table 3.
- **Response-level composite score** (reported in Table 3). For every held-out item, the candidate
  agent's actual response — and, for tool-using agents, the observed sequence of tool calls — is
  scored by a deterministic function starting from 1.0: a severity-weighted penalty (0.4 / 0.25 /
  0.15 / 0.05 for critical / high / medium / low) is subtracted for every regex-matched
  `must_not_appear` pattern found in the response text itself, not only the instructions; a further
  0.15 is subtracted per missing required substring and 0.3 per forbidden substring present, where
  the item matches a named `agent_tests` entry; a tool-call-policy violation subtracts 0.3
  (`required`, no matching call observed) or 0.4 (`forbidden`, a matching call observed); and the
  per-item score is floored at 0.15 if the matching test is tagged `regression_blocks: true` and any
  hard violation occurred, then clipped to `[0, 1]`. When a judge is enabled, this deterministic
  score is blended with a judge-scored average across the agent's `rubrics` at a configurable weight
  (default 0.4 for the judge component). The composite score reported per agent per system in Table
  3 is the mean of this per-item score across all ten held-out items. The exact implementation is
  `score_response` in `_baselines/dspy_mipro/metric.py`.

### 5.4 Replicate-run design

We reject single-run comparisons as inadequate evidence for a stochastic search process. For every
agent and every system under test, we run independent replicate seeds, each an independent
optimization run from the same baseline instructions, and report the distribution of the resulting
holdout scores — mean, standard deviation, and a percentile bootstrap 95% confidence interval — not
a single value, at any k. The exact number of replicate seeds required depends on what the paper
intends to claim from them, and we derive that number rather than assert it (Section 5.6): k ≥ 3
supports a descriptive estimate; a Holm-corrected significance claim (Section 5.6) requires k = 10,
which we run for every agent-system pair this paper reports a significance test for. Where cost
constrains an agent-system pair to k < 10, we report only the descriptive statistics for that pair
and state plainly, rather than silently omit, that no significance claim is being made for it.

**Iterative refinement.** A subset of agent-system pairs additionally include an "elect and
re-optimize" condition: run two independent replicate seeds (Run 1, Run 2); score both using
MIPROv2's own internal validation score against a held-back slice of the *optimizer-visible* data
(never the held-out split — this is the leakage fix described in Section 4.3); elect whichever
scored higher as the seed for a third run (Run 3); and evaluate Run 3, like every other condition,
against the held-out split. We report this condition's held-out score only against the *distribution*
of independent (non-iterative) replicate runs, never against a single one of Run 1 or Run 2
individually — `max(Run 1, Run 2)` on the internal validation score exceeds either individual run by
construction, so a comparison to a single input run would confound genuine iterative improvement
with order-statistic selection bias.

### 5.5 Judge configuration and self-preference bias control

Every agent's contract specifies a `primary_judge_model` pinned to a vendor family disjoint from
every model on Foundry's supported optimization-model list and from whichever model serves as
`--task-lm`/`--prompt-lm` in the DSPy track, directly implementing the mitigation Section 2.4
motivates. A `cross_judge_model`, deliberately same-family as one optimization condition, is run in
parallel on a subset of judged items specifically to measure the self-preference gap via a
corpus-level Cohen's kappa (binary rules) or Pearson correlation (Likert-scale rubric items) between
the two judges' verdicts, computed once over all paired ratings collected in a run rather than
per-item (chance-corrected agreement statistics require a set of ratings to be meaningful). Each
judged item is scored `repeats_per_item` times (3, or 5 for the safety-critical agent) and resolved
by majority vote or averaging, to reduce the influence of a single flaky judge call on a
promotion-gating verdict. Where the pooled kappa for a given agent falls below the conventional
"moderate agreement" threshold (κ ≈ 0.4; Section 6.3), we report that agent's Table 3/4 numbers with
an explicit low-agreement caveat attached rather than silently as-is, since a low kappa means the
judge-dependent portion of that agent's score is sensitive to which judge happened to be used.

### 5.6 Statistical analysis plan

For each agent, we compare the holdout-score distributions of the Foundry track and the DSPy track
using a paired Wilcoxon signed-rank test (appropriate for the small, non-normality-guaranteed
replicate-run sample sizes this design produces, following Demšar, 2006), report the rank-biserial
effect size alongside the p-value, and apply Holm-Bonferroni correction across the family of
per-agent comparisons before treating any single comparison as significant at α = 0.05.

This test family has a sample-size floor that is easy to overlook and that we state explicitly
rather than discover after running the experiment: the exact paired Wilcoxon signed-rank test's
smallest achievable two-sided p-value at k non-tied replicate pairs is 2^(1−k). At k = 5, that floor
is 0.0625 — no effect size, however large, can produce p < 0.05 at that sample size. After
Holm-Bonferroni correction across ten agents, the most significant comparison in the family must
clear α/10 = 0.005 to register at all, which requires 2^(1−k) ≤ 0.005, i.e., k ≥ 9. We therefore run
**k = 10** replicate seeds per agent-system pair for every comparison this paper reports a
significance test for, and report the bootstrap confidence interval and rank-biserial effect size —
which degrade gracefully at smaller k, unlike a p-value against a fixed threshold — as the primary
evidence at any sample size below that bar. We treat a composite-score delta smaller than each
agent's pre-registered `min_meaningful_delta` (recorded in `expected/expectations.json`, derived from
the expected noise band of that agent's baseline; see `docs/agent-evaluation-guide.md`) as
within-noise regardless of nominal statistical significance — a large enough sample can render a
practically meaningless delta formally significant, and pre-registering the practical threshold
before running the experiment avoids post-hoc justification of whichever threshold makes a result
look interesting.

## 6. Results

> **This section contains placeholder, illustrative data only.** Every number, table, and figure
> description below is a stand-in showing the format the real results will take once the protocol
> in Section 5 has been executed. No claim in this section should be read as an experimental
> finding. Real results will replace this section in full before any submission-ready version of
> this paper is prepared; see `docs/experiment-runbook.md` for the exact procedure that produces the
> real numbers.

### 6.1 Primary comparison: holdout composite score by agent and system

*Table 3 (ILLUSTRATIVE — PLACEHOLDER). Mean holdout composite score ± bootstrap 95% CI across k=10
replicate seeds, with the Holm-corrected paired Wilcoxon p-value. Two of ten agent rows are shown;
the full table will report all ten.*

| Agent | Baseline | Foundry (optimized) | DSPy MIPROv2 (optimized) | Wilcoxon p (Holm-corrected) | Rank-biserial effect size |
|---|---|---|---|---|---|
| 01 travel-approval-strict | 0.81 | 0.84 ± 0.03 [PLACEHOLDER] | 0.83 ± 0.04 [PLACEHOLDER] | 0.62 [PLACEHOLDER] | 0.11 [PLACEHOLDER] |
| 02 support-triage-messy | 0.41 | 0.79 ± 0.06 [PLACEHOLDER] | 0.74 ± 0.08 [PLACEHOLDER] | 0.04 [PLACEHOLDER] | 0.58 [PLACEHOLDER] |

*(Rows for agents 03–10 omitted from this draft in the same illustrative format; the real results
section will report all ten, each backed by k=10 replicate runs per system.)*

### 6.2 Promotion-gate pass rate

*Table 4 (ILLUSTRATIVE — PLACEHOLDER). Fraction of the k=10 replicate runs whose winning candidate
has `blocked: false` (Section 5.3) — no critical failure in any of the four gating contract
categories, and every `regression_blocks` agent_test passing on the held-out split. Three of ten
agent rows shown; the full table will report all ten, each out of 10 replicate runs.*

| Agent | Foundry gate pass rate | DSPy gate pass rate |
|---|---|---|
| 02 support-triage-messy | 6/10 [PLACEHOLDER] | 8/10 [PLACEHOLDER] |
| 05 clinical-triage-safety | 8/10 [PLACEHOLDER] | 9/10 [PLACEHOLDER] |
| 08 helpdesk-reset-multiturn | 4/10 [PLACEHOLDER] | 6/10 [PLACEHOLDER] |

*Illustrative interpretation note (not a finding): a composite-score improvement (Table 3) alongside
a gate-pass rate below 10/10 (Table 4) on the same agent is exactly the divergence this benchmark is
designed to surface — it would indicate the optimizer is raising the metric it's evaluated on while
still failing a hard-coded safety or policy gate on at least one replicate run. See Section 7 for the
decision rule distinguishing this from ordinary run-to-run stochasticity.*

### 6.3 Primary/cross-judge agreement

*Table 5 (ILLUSTRATIVE — PLACEHOLDER). Corpus-level Cohen's kappa between the primary (disjoint
vendor family) and cross (same-family) judge, pooled across all judged semantic rules for a given
agent.*

| Agent | Kappa (binary rules) | Pearson r (Likert rubrics) | n rated pairs |
|---|---|---|---|
| 05 clinical-triage-safety | 0.71 [PLACEHOLDER] | 0.68 [PLACEHOLDER] | 46 [PLACEHOLDER] |

### 6.4 Cross-run textual similarity

*Table 6 (ILLUSTRATIVE — PLACEHOLDER). Word-trigram cosine similarity between replicate runs'
optimized instructions, against the permutation null and the cross-agent null. At k=10 replicate
seeds this implies C(10,2)=45 within-track pairs per agent per system; one representative pair is
shown here, the full table will report the distribution across all 45.*

| Comparison | Cosine | Permutation null (mean ± sd) | Cross-agent null (mean ± sd) |
|---|---|---|---|
| Foundry run 1 vs. run 2 (agent 01) | 0.58 [PLACEHOLDER] | 0.11 ± 0.02 [PLACEHOLDER] | 0.06 ± 0.03 [PLACEHOLDER] |

### 6.5 Instruction and cost growth

*Table 7 (ILLUSTRATIVE — PLACEHOLDER). Mean instruction word-count growth ratio and estimated cost
growth ratio (optimized vs. baseline) across k=10 replicate seeds, against each agent's
pre-registered `max_instruction_growth_ratio` / `max_cost_growth_ratio` bound.*

| Agent | Foundry growth ratio | DSPy growth ratio | Agent's stated bound |
|---|---|---|---|
| 01 travel-approval-strict | 1.4× [PLACEHOLDER] | 1.5× [PLACEHOLDER] | 1.6× (instruction) / 1.5× (cost) |
| 06 sales-brief-underspecified | 8.2× [PLACEHOLDER] | 6.7× [PLACEHOLDER] | 30× (instruction) / 25× (cost) — deliberately loose; see `docs/agent-evaluation-guide.md` |

### 6.6 Iterative refinement condition

*Table 8 (ILLUSTRATIVE — PLACEHOLDER). The elect-and-reoptimize condition's held-out score, reported
against the full distribution of independent replicate runs (Section 5.4), never against a single
input run.*

| Agent | Independent replicate runs (mean ± sd, k=10) | Elect-and-reoptimize (Run 3) score |
|---|---|---|
| 01 travel-approval-strict | 0.84 ± 0.03 [PLACEHOLDER] | 0.85 [PLACEHOLDER] |

## 7. How to read the results once they are real

This subsection is intentionally written as a conditional guide, not a conclusion, because Section 6
contains no real data yet.

- If Table 3 shows deltas within each agent's pre-registered noise band (Section 5.6) for the
  "good baseline" control agents (01, 09) on both tracks, that is evidence *for* H0 (an optimizer
  should not meaningfully disturb an already-good prompt) — not evidence that the optimizer works
  well in general, since these two agents are specifically chosen to have little room to improve.
- If Table 4 shows a gate-pass rate below 10/10 on any agent for either track, treat that as the
  paper's central empirical claim made concrete **only if it recurs across a majority of the k=10
  replicate seeds** (at least 6 of 10 failing runs, as a working threshold) for that agent-system
  pair. A single failing run out of ten is more consistent with ordinary optimizer stochasticity —
  ordinary variance in what a search process happens to try — than with a systematic preservation
  failure; the replicate-run design exists specifically so this distinction can be made from the
  data rather than assumed from a single observation. The paper's contribution rests on Table 4
  existing as a *reportable, separate* number from Table 3 — a benchmark that only reported composite
  score deltas could not make this distinction visible at all, systematic or not.
- If Table 5 shows low agreement between the primary and cross judge (kappa below roughly 0.4, by
  conventional interpretation), report that agent's Table 3/4 numbers with the caveat specified in
  Section 5.5, rather than at face value.
- Table 6 is descriptive, not confirmatory on its own — a cosine similarity number is only
  interpretable relative to its two null baselines, and should always be read alongside the
  `expectations_agreement` axis (Section 5.3), not as a stand-alone similarity claim.
- Table 7 should be read as a cost the optimizer spent to achieve whatever delta Table 3 shows for
  the same agent — a score improvement that costs growth beyond the agent's pre-registered bound is
  a trade-off to weigh deliberately, not a clean win, regardless of the sign of the Table 3 delta.
- Table 8's iterative-refinement score should be read only in relation to the *distribution* column
  in the same table, never against Run 1 or Run 2 individually (Section 5.4); if it falls within
  that distribution's confidence interval, that is evidence the re-optimization step did not
  measurably help beyond ordinary replicate-run variance, which is itself a reportable finding, not
  an absence of one.

## 8. Limitations

- **Foundry is a closed, versioned, non-deterministic hosted service.** We cannot guarantee that two
  runs separated in time used an identical underlying model version, and the platform's internal
  search algorithm is not published, so any structural comparison to the methods in Section 2.1 is
  necessarily inferred from documented behavior (Microsoft, 2026), not confirmed against source.
- **A single open baseline (DSPy MIPROv2) is one comparison point**, not a claim that Foundry's
  optimizer is better or worse than automatic prompt optimization broadly; Section 3 states the
  specific, narrow reasons for this choice.
- **The k = 10 replicate-seed requirement for a significance claim (Section 5.6) is expensive**: for
  the full ten-agent pack across both systems, that is 200 optimization runs before a single
  significance claim is reportable, and more again for any additional optimization target compared
  in the future. We consider this an honest cost of the statistical standard we hold ourselves to,
  not a flaw to work around by lowering k and reporting a p-value that sample size cannot support.
- **The two MCP agents are evaluated on an instructions-and-function-tools-only basis in the DSPy
  track**, since no production MCP server exists in this repository to call for real; this is stated
  plainly in the benchmark's own documentation and any DSPy-vs-Foundry delta on those two agents
  should not be read as a like-for-like MCP-retrieval comparison.
- **The judge layer's deterministic-only fallback path was smoke-tested with a heuristic stub judge
  that has no real language understanding**; every real judged number in this paper depends on
  actual judge-model calls, and the stub path exists only to validate that the code executes, never
  as a source of reportable data.
- **Citations to the academic literature in Section 2 are drawn from the authors' working knowledge
  and have not yet been independently verified against primary sources (exact venue, volume, and
  page) for this draft.** This is a heavier caveat for the two citations with the least standardized
  public form among those used here — Opsahl-Ott et al. (2024) for MIPROv2 and Panickssery et al.
  (2024) — and must be resolved before any submission-ready version. The Foundry product-
  documentation citation added in this revision (Microsoft, 2026) likewise needs its exact URL and
  access date confirmed by the authors before submission.

## 9. Future work

- Extend the benchmark past the current ten agents with a held-back, unpublished evaluation slice —
  released only after the public benchmark has had time to be used, to guard against the
  contamination risk any published, well-known benchmark eventually faces once its items may appear
  in a future model's training data.
- Add a human-annotator agreement study on a subsample of judged items, to calibrate the LLM-judge
  layer against human judgment directly, rather than only measuring judge-vs-judge agreement.
- Extend the DSPy comparison to a second open optimizer (for example, a reference OPRO or EvoPrompt
  implementation) to test whether findings about Foundry's optimizer generalize across open methods
  or are specific to the structural similarity with MIPROv2 that motivated our choice in Section 3.
- Add a real MCP server stub to the DSPy baseline so the two MCP agents can be evaluated on a
  like-for-like retrieval basis across both tracks, closing the limitation noted in Section 8.
- Run a formal power analysis for the per-agent item counts (Section 4.3) at effect sizes smaller
  than this benchmark's current pre-registered `min_meaningful_delta` thresholds, and scale the
  benchmark's item count to match if smaller effects turn out to matter in practice.

## 10. Conclusion

*This is a placeholder conclusion, written to show the shape a final conclusion will take — it draws
no real conclusions because Section 6 contains no real data. It should not be read as a finding.*

Pending the real experimental run described in Section 5, we would conclude that closed-loop prompt
optimization for LLM agents [PLACEHOLDER: does / does not] reliably preserve safety-critical and
policy-critical constraints under evaluation-driven rewrite, at a rate that [PLACEHOLDER: does / does
not] recur systematically across replicate runs rather than reflecting ordinary optimizer
stochasticity (Section 7); that this behavior [PLACEHOLDER: does / does not] differ meaningfully,
at the k=10 replicate scale this protocol requires for a defensible significance claim, between a
commercial closed-loop optimizer and an open, comparably structured baseline; and that
[PLACEHOLDER: judge-model choice materially affects / does not materially affect] which candidates a
single-judge evaluation would promote. The benchmark, scoring harness, and DSPy baseline released
alongside this paper are intended to let other researchers reach their own version of this
conclusion against other closed-loop optimizers as they become available, without depending on
continued access to any one commercial product.

## References

Andriushchenko, M., et al. (2024). AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents.

Demšar, J. (2006). Statistical Comparisons of Classifiers over Multiple Data Sets. *Journal of
Machine Learning Research*.

Dietterich, T. G. (1998). Approximate Statistical Tests for Comparing Supervised Classification
Learning Algorithms. *Neural Computation*.

Fernando, C., et al. (2023). Promptbreeder: Self-Referential Self-Improvement via Prompt Evolution.

Gebru, T., et al. (2018, revised 2021). Datasheets for Datasets. *Communications of the ACM*.

Guo, Q., et al. (2023). Connecting Large Language Models with Evolutionary Algorithms Yields
Powerful Prompt Optimizers (EvoPrompt).

Jimenez, C. E., et al. (2023). SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

Khattab, O., et al. (2023). DSPy: Compiling Declarative Language Model Calls into Self-Improving
Pipelines.

Liu, X., et al. (2023). AgentBench: Evaluating LLMs as Agents.

Mialon, G., et al. (2023). GAIA: A Benchmark for General AI Assistants.

Microsoft. (2026). *Microsoft Foundry Agent Service: Agent Optimizer* [Product documentation, public
preview]. **[AUTHOR ACTION — before submission: confirm the exact documentation URL and access
date.]**

Opsahl-Ott, K., et al. (2024). Optimizing Instructions and Demonstrations for Multi-Stage Language
Model Programs (MIPRO). **[AUTHOR ACTION — before submission: confirm exact author list and venue.]**

Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own
Generations. **[AUTHOR ACTION — before submission: confirm exact venue.]**

Ruan, Y., et al. (2023). Identifying the Risks of LM Agents with an LM-Emulated Sandbox (ToolEmu).

Wang, X., et al. (2023). PromptAgent: Strategic Planning with Language Models Enables
Expert-Level Prompt Optimization.

Yang, C., et al. (2023). Large Language Models as Optimizers (OPRO).

Yao, S., et al. (2024). τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.

Yuan, T., et al. (2024). R-Judge: Benchmarking Safety Risk Awareness for LLM Agents.

Yuksekgonul, M., et al. (2024). TextGrad: Automatic "Differentiation" via Text.

Zhan, Q., et al. (2024). InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated
Large Language Model Agents.

Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.

Zhou, S., et al. (2023). WebArena: A Realistic Web Environment for Building Autonomous Agents.

Zhou, Y., et al. (2022). Large Language Models Are Human-Level Prompt Engineers (APE).
