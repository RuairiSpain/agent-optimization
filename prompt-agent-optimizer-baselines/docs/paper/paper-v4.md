---
title: "Auditing Closed-Loop Prompt Optimization for LLM Agents: A Benchmark and Reproducible Baseline"
status: "DRAFT v4 — responds to an external journal review of paper-v3.md (see response-letters/external-journal-review.md); the two earlier internal review-cycle responses are response-letters/round-1.md and round-2.md. Contains placeholder experimental data, clearly marked. Not for submission."
---

# Auditing closed-loop prompt optimization for LLM agents: a benchmark and reproducible baseline

**Authors:** [author list withheld — internal draft]
**Draft status:** Version 4. Responds to an external journal review of `paper-v3.md`; the response
letter is at `response-letters/external-journal-review.md` (and, for the two earlier internal
review rounds, `response-letters/round-1.md` / `round-2.md`) — kept separate from this manuscript so
the paper itself reads as a paper, not a revision log. All tables in Section 6 contain
**illustrative, placeholder data** generated to show the intended structure of the results, not real
experimental findings. See the banner at the start of Section 6 for the scope of what is and is not
real in this draft.

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
optimizer. Both tracks are checked against every candidate's instructions by a single shared,
code-level contract, so instruction-level pass/fail gating is identical for both systems; the
response-level composite score uses the same scoring function on both tracks in principle, but as
this pack currently stands that function is exercised end-to-end for the DSPy track only, since
scoring the Foundry track's response-level layer requires a harness — one that runs an exported
Foundry candidate against the held-out split and captures its real responses — that this draft does
not yet build (Section 5.3, Section 8). We report our experimental design, a composite-score formula
and gating criteria defined precisely enough to be re-implemented from the paper alone, and a
statistical analysis plan whose sample-size requirements are derived, not assumed, from the exact
test it specifies. The results in this draft are illustrative placeholders in the reporting format
this protocol produces; the protocol itself — not any result — is this draft's contribution. We
release the benchmark, the scoring harness, and the DSPy baseline implementation.

## 1. Introduction

Automatic prompt optimization has moved from a research technique to a shipped product feature.
Systems that iteratively propose, evaluate, and select instruction rewrites — without gradient
access to the underlying model — are now available as commercial, closed-loop services integrated
directly into agent-hosting platforms, from at least two major cloud vendors as of this writing.
Microsoft Foundry Agent Service's agent optimizer (Microsoft, 2026), in public preview at the time
of writing, is this paper's subject: given a baseline agent and an evaluation dataset, it proposes
candidate instructions, tool descriptions, and model choices, scores each candidate, and returns the
highest-scoring configuration for deployment. Amazon Bedrock AgentCore's Optimization capability
(Amazon, 2026) ships a structurally similar recommend-evaluate-deploy loop — its own documentation
states that batch evaluation tests each recommended change "against a defined test dataset" before a
separate live-traffic A/B test — which is a second, independent instance of the same product
category and the same evaluation-loop shape this paper audits, not evidence specific to one vendor.

This creates a specific and under-examined risk, one recent work has started to name but not yet
audit empirically in a deployed, closed-loop product. An optimizer that is rewarded purely for
raising a composite evaluation score has no inherent reason to preserve properties that composite
score doesn't measure — a safety constraint the evaluation rubric didn't happen to test, a tool-call
policy the dataset didn't happen to exercise, a numeric business rule that a paraphrase can silently
loosen without tripping a keyword check. Wan et al. (2026) call the general version of this pattern
*in-context reward hacking* (ICRH) — an LLM iteratively optimizing against a proxy objective in a
way that produces side effects the objective doesn't penalize — and propose a runtime constraint
framework to reduce it during a single agent's execution; Li et al. (2026) argue, as a position
paper rather than an empirical study, that safety-critical constraints in LLM-based systems must be
*maintained*, not merely asserted once, and name optimization explicitly as one of the mechanisms
("constraint drift") through which a constraint can silently stop being operative. Both give this
paper's concern a name and a broader research context; neither audits whether it actually occurs in
a deployed, closed-loop instruction optimizer a paying customer can use today. The optimizer is, in
effect, an unsupervised editor operating on a document that encodes an organization's operating
policy, judged by a metric that is necessarily an incomplete proxy for what the organization
actually wants preserved.

Existing agent and LLM evaluation benchmarks are not built to audit this failure mode. Prompt
optimization research (Section 2.1) evaluates optimizers on task accuracy, not on whether an
optimizer preserves properties adversarial to its own reward signal — including very recent evidence
that optimization itself is not even reliably an accuracy *improvement*: Bai & Shi (2026) find
prompt optimization in multi-agent systems can drop task performance by as much as 16 points, not
only raise it, which is a different axis from ours (accuracy variance, not preservation of properties
the accuracy metric doesn't measure) but the same underlying warning against treating "the optimizer
ran" as evidence of "the optimizer helped." Agent capability benchmarks (Section 2.2) evaluate
whether an agent can complete a task, not whether an *optimizer acting on that agent* preserves the
agent's constraints under rewrite. Agent safety benchmarks (Section 2.3) evaluate a fixed agent's
vulnerability to an attack, not an optimizer's tendency to *introduce or remove* that vulnerability
while rewriting the agent it's evaluating. We are not aware of a benchmark that sits at this specific
intersection: closed-loop optimization of an agent's instructions and tools, audited for preservation
of safety-critical and policy-critical content under evaluation-driven rewrite.

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

Two very recent (2026) systems sit closer to Foundry's own framing of an agent-optimizing-agent loop
than the methods above. VeRO (Ursekar et al., 2026) evaluates coding agents that iteratively edit and
re-evaluate a target agent's *harness* — not only its prompt — under versioned snapshots and
budget-controlled evaluation; its headline empirical finding is that current optimizers, even when
free to edit code, default to prompt-only modifications with limited diversity and impact, which is
directly relevant context for interpreting whatever a closed, prompt-focused optimizer like
Foundry's produces. JTPRO (Ghoshal et al., 2026) jointly optimizes an agent's global instructions and
its per-tool schema/argument descriptions via rollout-driven reflection — the same two-part
optimization surface (instructions plus tool descriptions) Foundry's optimizer exposes — and reports
that joint optimization outperforms optimizing either component alone on tool-selection and
slot-filling accuracy. Neither VeRO nor JTPRO evaluates whether its optimization preserves properties
adversarial to its own objective; both are, like the rest of this section, accuracy- or
success-rate-improvement studies. MAS-PromptBench (Bai & Shi, 2026) evaluates prompt optimizers for
multi-agent systems across workflow topologies and communication protocols and reports that gains are
inconsistent — optimization can improve performance by up to 24 points or reduce it by up to 16,
depending on configuration; this is evidence against assuming optimization helps at all, which is a
useful caution but, like the systems above, measured entirely on task-performance metrics, with no
axis for whether a given change preserved a property outside those metrics.

Two 2026 papers name, without empirically auditing, the specific concern this benchmark targets.
Wan et al. (2026) introduce LLM-based Constraint Optimization (LCO) to reduce *in-context reward
hacking* (ICRH) — their term for an LLM iteratively optimizing its own behavior against a proxy
objective in a way that produces side effects the objective doesn't penalize — via a runtime
self-thought module and evolutionary constraint sampling, reporting reductions in toxicity growth and
ICRH occurrence rate on two tasks. LCO is a *mitigation* applied at a single agent's execution time,
not an audit of any closed-loop, cross-run optimizer; we adopt ICRH as a precise name for the risk
this paper's Introduction motivates and cite it for that reason, not as prior empirical work on the
same system. Li et al. (2026), in a position paper rather than a benchmark, argue that safety-critical
constraints in LLM-based multi-agent systems must be *maintained* continuously rather than asserted
once, coining *constraint drift* for the loss, distortion, or weakening of a constraint as it passes
through memory, delegation, communication, tool use, audit, or — explicitly named as one of their six
mechanisms — optimization, and call for "Constraint State Governance" as a research paradigm without
instantiating it as a measurable protocol. Their framing and ours describe the same underlying concern
from different scopes: theirs is about a constraint's state persisting *within* a single multi-agent
trajectory at run time, across delegation and tool use; ours is about a constraint's presence
persisting *across* an optimizer's rewrite, between deployments, for a single agent. Read together,
this paper is a step toward the kind of empirical instrument their call for governance implies is
missing, scoped narrowly to the rewrite-time case and a single, real, closed-loop product rather than
the fuller runtime-governance paradigm they propose.

None of these methods report an evaluation of whether the optimizer preserves properties of the
original prompt that are outside its own reward signal. Their evaluations are uniformly
accuracy-improvement (or, for LCO and the constraint-drift position paper, single-agent-execution or
conceptual) studies, not an audit of a deployed, closed-loop, cross-run optimizer: does the optimized
prompt perform better on the target task, does an optimizer help at all, or does a proxy objective
get gamed during a single run. We adopt the search methodology the APO literature describes and the
ICRH/constraint-drift vocabulary the two position-adjacent works above supply, but change the
evaluation question from "did the score go up" to "did the score go up without silently breaking
something the score didn't measure" — asked specifically of a real, closed-loop, cross-run optimizer
a customer can deploy today, which none of the systems in this section ask.

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
delivery mechanism our agent 07 (Section 4) uses. AgentDojo (Debenedetti et al., 2024) extends this
line with a dynamic environment for evaluating prompt-injection attacks *and* defenses together
against tool-integrated agents across realistic task suites, again on a fixed agent under test.
AgentLure (introduced within Argus; Weng et al., 2026) sharpens the threat model further: it
specifically targets *context-dependent* tasks and *context-aware* attacks, arguing that
context-insensitive injection benchmarks understate risk because a real adversary adapts its attack
to the agent's current context rather than injecting a fixed payload — a distinction relevant to how
representative agent 07's fixed injection patterns are of an adaptive attacker, which we note as a
limitation (Section 8). AgentSecBench (Alpay & Alpay, 2026) reframes this family of concerns more
formally, as noninterference between untrusted observations and a protected output or action
predicate under three "games" (instruction-integrity, retrieval-confidentiality,
capability-integrity) — a stricter, more general property than the pattern-match checks our own
`must_not_appear`/tool-call-policy scoring uses, and a plausible direction for tightening agent 07's
injection-resistance check in future work (Section 9). Our contribution at this intersection is
therefore narrower and more specific than "tests injection via tool output" in isolation: we are not
aware of prior work evaluating whether a closed-loop *optimizer*, rewriting an agent's instructions
under an evaluation-score objective, preserves, weakens, or repairs an agent's resistance to this
class of injection. InjecAgent, AgentDojo, AgentLure/Argus, AgentSecBench, and the other benchmarks
in this subsection test a fixed agent (or a fixed agent plus a fixed defense) against an attack; our
benchmark tests whether an automated rewrite process changes that agent's resistance to the same
class of attack, which is a distinct question the injection-benchmark literature does not address
because it does not evaluate an optimizer at all.

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
recommending non-parametric tests (Wilcoxon signed-rank for paired comparisons, Mann-Whitney U for
independent samples) and correction for multiple comparisons (Holm's method) over the more commonly
misapplied paired t-test — we adopt this test family in Section 5.6, applying the paired variant only
where the compared samples are genuinely paired and the independent-samples variant where they are
not, along with the sample-size consequence of that choice for each, which the cited methodology
papers do not by themselves make salient and which we derive explicitly for this benchmark's setting.
Gebru et
al. (2018; revised 2021) introduce datasheets for datasets as a standard for documenting a dataset's
provenance, composition, and intended use; our benchmark's documentation (Section 4, and the
accompanying `README.md` and `CHANGELOG.md`) follows this template.

### 2.6 Positioning

Table 1 summarizes the gap this paper addresses.

*Table 1. Coverage comparison against the closest related benchmarks, methods, and products (a
qualitative, author-assessed summary of publicly documented capabilities — not derived from
re-running these systems, and distinct from the placeholder experimental data in Section 6). Rows
describe a peer-reviewed or preprint academic paper, cited in References, with two exceptions: the
"Foundry agent optimizer" and "Bedrock AgentCore Optimization" rows describe commercial products'
own documentation (Microsoft, 2026; Amazon, 2026) rather than an independently reviewed or
reproducible source — their cells should be read as "what the vendor states," not as an
independently verified capability claim, which is exactly the asymmetry this paper's benchmark
exists to let a third party check empirically instead of taking on trust, for either vendor.*

| System | Optimizes agent instructions | Evaluates preservation under rewrite | Train/test separation for the optimizer | Evaluates indirect/tool-output injection | Evaluates an *optimizer's* effect on injection resistance | Open, reproducible |
|---|---|---|---|---|---|---|
| APE / OPRO / EvoPrompt / PromptBreeder | Yes | No | Not specified | No | No | Yes |
| DSPy / MIPROv2 | Yes | No | Configurable, not enforced | No | No | Yes |
| VeRO (Ursekar et al., 2026) | Yes (harness/code, not only prompt) | No | Versioned snapshots; not an adversarial-preservation split | No | No | Yes (ICML 2026) |
| JTPRO (Ghoshal et al., 2026) | Yes (instructions + tool schemas jointly) | No | Not specified | No | No | Not confirmed |
| MAS-PromptBench (Bai & Shi, 2026) | No (benchmarks optimizers, doesn't optimize itself) | No (measures accuracy variance, not property preservation) | N/A | No | No | Yes |
| LCO (Wan et al., 2026) | No (a runtime constraint framework, not an instruction optimizer) | N/A (mitigates within one execution, not across an optimizer's rewrite) | N/A | No | No | Not confirmed |
| Constraint Drift (Li et al., 2026) | N/A (position paper; no benchmark or method released) | Argues for it, does not measure it | N/A | No | No | N/A (position paper) |
| τ-bench | No (evaluates a fixed agent) | N/A | N/A | No | No | Yes |
| InjecAgent | No (evaluates a fixed agent) | N/A | N/A | **Yes** | No | Yes |
| AgentDojo (Debenedetti et al., 2024) | No (evaluates a fixed agent + defenses) | N/A | N/A | **Yes** | No | Yes |
| AgentLure / Argus (Weng et al., 2026) | No (evaluates a fixed agent + a defense) | N/A | N/A | **Yes (context-aware, not fixed-payload)** | No | Not confirmed |
| AgentSecBench (Alpay & Alpay, 2026) | No (evaluates a fixed agent) | N/A | N/A | **Yes, via a noninterference framing broader than injection alone** | No | Not confirmed |
| ToolEmu / AgentHarm / R-Judge | No | N/A | N/A | No | No | Yes |
| Foundry agent optimizer (this paper's subject; Microsoft, 2026) | Yes | Not documented as evaluated | Not enforced by the product | No | No | No (closed, hosted) |
| Bedrock AgentCore Optimization (Amazon, 2026) | Yes (system prompts + tool descriptions) | Not documented as evaluated | Batch evaluation runs against "a defined test dataset"; a separate live-traffic A/B test follows, which is not the same as an enforced held-out adversarial split | No | No | No (closed, hosted) |
| **This work** | Yes (both tracks) | **Yes** | **Enforced throughout the protocol, including the iterative-refinement condition (§5.4)** | Yes (agent 07, adapted from InjecAgent's delivery mechanism) | **Yes** | **Yes (the benchmark and the DSPy baseline; Foundry itself remains closed)** |

"Not confirmed" in the rightmost column means we did not verify a code/data release for that system
as part of this literature pass (Section 8) — it is not a claim that the work is closed.

### 2.7 Detailed comparison against the closest related harnesses

Table 1 states the gap in one row each; this subsection makes the comparison concrete for the five
systems closest to this paper's design (Sections 2.1, 2.3), stating specifically what each system's
own evaluation would and would not have caught if it had been pointed at the same failure modes this
benchmark targets, and vice versa. The point of doing this per-system rather than only in aggregate
is that "evaluates a fixed agent, not an optimizer" (our recurring claim against four of the five)
is easy to state and easy to under-argue; a reader should be able to check it against each system's
actual evaluation design, not just our summary of it.

**Against VeRO (Ursekar et al., 2026).** VeRO's harness would catch something ours does not: whether
an optimizer, given the freedom to edit an agent's full harness rather than only its prompt text,
actually uses that freedom, and how much its edits vary across independent attempts. Our benchmark
never gives either optimizer under test that freedom — both Foundry's optimizer and our DSPy
baseline operate at the instructions/tool-description text layer only (Section 5.1), so a question
like "does the optimizer default to safe, low-diversity prompt-only edits when code edits were
available" is out of scope for us by construction, not by oversight. Conversely, VeRO's own
evaluation — comparing edit diversity and impact across versioned snapshots — has no place in its
design to ask whether a given edit, however diverse or impactful, preserved a property adversarial to
the objective the edit was scored against. If VeRO's harness were pointed at the same ten agents this
benchmark uses, it could tell you whether a code-editing optimizer touched agent 05's safety
instructions at all and how much; it could not tell you, without adopting something like our gating
categories (Section 4.2), whether the touched version still refuses to name a medical condition.

**Against JTPRO (Ghoshal et al., 2026).** JTPRO's evaluation would catch something ours is not
designed to measure: whether jointly optimizing instructions and tool schemas together beats
optimizing either one alone on tool-selection and slot-filling accuracy. Our benchmark has no
isolated-vs-joint optimization arm — both systems under test always optimize instructions and tool
descriptions together (Section 5.1), so we cannot speak to JTPRO's headline finding one way or the
other; we adopt the same joint optimization surface rather than test whether jointness itself helps.
Conversely, on JTPRO's own reported evaluation (accuracy on tool-selection and slot-filling tasks),
a tool-schema edit that loosens a required parameter's enum or drops a disambiguating description —
exactly the kind of change our `tool_rules` axis (immutable names/types/enums, Section 4.1) exists
to catch — could plausibly *improve* the accuracy metric JTPRO reports (a looser schema can make it
easier for the agent to pick a plausible tool) while simultaneously widening what a `forbidden`
tool-call policy would let through. Nothing in an accuracy-only evaluation of joint optimization
would surface that trade-off; it is the same "score went up, something the score didn't measure
degraded" pattern Section 1 frames as this paper's subject, applied specifically to the tool-schema
half of JTPRO's own optimization surface.

**Against AgentDojo (Debenedetti et al., 2024).** AgentDojo would catch something ours does not
attempt: breadth and realism of attack surface. Its task suites, multiple environments, and paired
attacks-and-defenses give a far more thorough picture of a fixed agent's injection resistance than
our single agent 07 with its two rephrasing-linked splits (Section 4.3) does or is meant to. What
AgentDojo's design does not do — because it evaluates a fixed agent, with or without a fixed defense,
not an agent under an automated rewrite process — is notice a *regression*: if an optimizer rewrote
the system prompt of an AgentDojo-evaluated agent, AgentDojo's own harness would need to be re-run
before and after the rewrite for a human to even think to compare the two scores, and nothing in its
design flags that comparison as the one to make. Our benchmark's contribution at this intersection is
exactly that comparison, made structural rather than incidental: agent 07's baseline-vs-optimized
delta on the injection-resistance axis is a first-class, always-computed number (Table 3/4), not
something a user of the harness would have to think to construct.

**Against AgentLure / Argus (Weng et al., 2026).** AgentLure would catch something agent 07 is
already documented (Section 8) as unable to: whether an agent resists an attacker that adapts its
payload to the specific task context, rather than one of a fixed, pre-authored family of injection
patterns rephrased across our optimize/holdout split (Section 4.3). This is a real gap in agent 07's
design, not a strength we're claiming — the rephrasing-across-splits design tests generalization
across *phrasing*, not adaptation to *context*, and AgentLure's threat model is strictly the harder
and more realistic of the two. What AgentLure does not do, sharing this with AgentDojo, is evaluate
an optimizer's effect on the property it measures: its unit of evaluation is a fixed agent (optionally
with a fixed defense) against a context-aware attack, not a before/after comparison across an
automated instruction rewrite. A context-aware attack suite and an optimizer-under-rewrite protocol
are complementary, not competing, designs — Section 9 already lists tightening agent 07 toward a
harder threat model as future work; doing so would still need this paper's before/after structure
layered on top to ask the question AgentLure itself does not ask.

**Against AgentSecBench (Alpay & Alpay, 2026).** AgentSecBench would catch something our deterministic
scoring (Section 5.3) structurally cannot: a noninterference violation that never manifests as a
matched string or a flagged tool call — for instance, a response whose *tone* or *emphasis* shifts in
a way that is causally downstream of untrusted content, without ever producing text that trips a
`must_not_appear` pattern or a `tool_call.policy` check. Our `must_not_appear`/tool-call-policy axis
is a pattern-match proxy for the property AgentSecBench formalizes directly as noninterference between
an untrusted observation and a protected output/action predicate; a sufficiently subtle dependence
could satisfy every pattern-match check in our contract while still failing AgentSecBench's stricter
test. Conversely, AgentSecBench's three "games" evaluate a fixed agent's standing on a noninterference
property at a point in time; they do not, as documented, ask whether that standing changes after an
automated instruction rewrite — the same gap as AgentDojo and AgentLure, for a formally stronger
property. Section 9 already names adopting a noninterference-style check as a direction for agent 07;
the point worth making explicitly here is that doing so would upgrade *what* our before/after
comparison measures, not add the before/after structure itself, which AgentSecBench's own design does
not have a place for.

**What is common across all five.** None of these five systems' own evaluations include a replicate-seed
design or a statistical test for run-to-run stochasticity (Section 5.4, 5.6) — VeRO's versioned
snapshots come closest, but its own reported evaluation compares snapshots for edit diversity and
impact, not for whether a given snapshot's score improvement clears a derived significance floor
against independent replicate attempts. This is not a claim that any of the five should have included
one for their own research questions; it is the specific methodological gap this paper's protocol
(Section 5) closes for the question this paper asks, which none of the five ask.

### 2.8 Distinction from commercial prompt-regression-testing tooling

A reader familiar with LLM-application infrastructure could reasonably ask whether this paper's
contribution already exists as a product. Five platforms' own public claims about themselves, cited
individually because each documents a materially different mechanism rather than one generic
"regression testing" feature, converge on this same broad pattern: Braintrust (2026) turns a
production failure a human flagged into a reusable test that runs on every future deployment;
PromptLayer (2026) runs scheduled regression tests against a versioned prompt history and supports
A/B testing between versions; LangChain's LangSmith (2026), paired with the separate, experimental
Promptim library (LangChain, 2026) released in 2026, provides dataset management and tracking for an
external optimization loop rather than a first-class, integrated optimizer of its own; Langfuse
(2026) is a tracing and observability platform that other tools' evaluators, including DeepEval's,
can read sampled production traffic from; and Confident AI's DeepEval (2026) is explicit that its
regression-testing mechanism is a CI/CD quality gate in the literal sense — it runs a golden dataset
against a changed prompt and fails the pipeline if a metric drops below a configured threshold. We
rely here on these five vendors' own public claims about their products, not an independent
evaluation of them, the same evidentiary standard Table 1 applies to Foundry's and Bedrock
AgentCore's own documentation. Two distinctions separate this category of tooling from this paper's
contribution, and both are about what fills the test suite, not whether a test suite or a gate
exists:

1. **General-purpose regression testing checks whatever the user already put in the suite.** These
   platforms are infrastructure: they execute a user-authored set of test cases and compare scores
   across versions. They do not ship an adversarial dataset purpose-built to expose the specific
   failure mode this paper targets — a baseline that already contains a subtle policy violation
   (Section 4, agent 02), a safety rule an optimizer could plausibly extend past its intended
   boundary (agent 05), an injection payload delivered through tool output rather than the user turn
   (agent 07) — nor a taxonomy distinguishing what must survive a rewrite from what may legitimately
   change (Section 4.2). A team using any of these platforms to regression-test a Foundry- or
   Bedrock-optimized agent would still need to author that adversarial content themselves; this
   paper's benchmark is exactly that content, designed specifically to be hard for a
   score-maximizing optimizer to pass by accident.
2. **General-purpose regression testing does not, by itself, enforce that the optimizer never saw
   the test suite.** Nothing in how these platforms are marketed prevents a user from running an
   optimizer against the same dataset the regression suite draws from — precisely the leakage this
   paper's train/test separation (Section 4.3, 5.2) exists to rule out by construction, and precisely
   the ambiguity in Bedrock AgentCore's own documented design (Table 1): its batch evaluation runs
   against "a defined test dataset," and nothing in the public description states whether that
   dataset is disjoint from whatever data informed the recommendation being tested.

In short: the infrastructure pattern this paper's protocol could run on top of — a held-out suite, a
gate before deployment — is commercially mature. What is not commercially or academically available,
to our knowledge, is the specific adversarial dataset, gating taxonomy, and enforced-separation
protocol needed to make that infrastructure pattern actually catch the failure mode this paper
targets, applied to a real, closed-loop, vendor-hosted optimizer.

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
3. **A shared scoring path.** Our DSPy baseline's instruction-level scoring code imports the same
   contract-checking implementation used to grade an exported Foundry candidate's instructions
   (Section 5.3), so an instruction-level pass/fail difference between the two tracks cannot be
   attributed to a second, independently drifted scoring implementation. The response-level scoring
   function (also Section 5.3) is written once and intended for both tracks, but currently runs
   end-to-end only for the DSPy track, because scoring the Foundry track's response-level layer
   additionally requires a harness that exercises an exported candidate against real held-out queries
   — a piece of infrastructure this draft does not yet build (Section 8).

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
Counted directly across all ten agents' `expected/expectations.json` files (totals of 9, 10, 9, 10,
13, 10, 10, 10, 10, 10), this ranges from 9 to 13 tests per agent (mean 10.1), of which 70% to 100%
(mean ≈ 87%) are tagged `regression_blocks: true`
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
5.2), and — after a leakage path identified during this paper's review process (see `response-letters/round-1.md`) — in the iterative-refinement condition as well (Section 5.4): electing
between replicate runs uses only a validation slice of the optimizer-visible data, never the held-out
split, so the held-out score reported for any condition, iterative or not, reflects data no part of
that condition's selection process has seen.

### 4.4 What gap this fills

Section 2.6 (Table 1) states this in comparative terms; Section 2.7 makes it concrete system by
system. Concretely: existing APO benchmarks measure
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
scoring for every reported number in Section 6 that this pack can currently produce uses the 10-item
`holdout` split, which neither optimizer sees during search, and which no run-selection decision
(Section 5.4) depends on either. We treat a score computed on the `optimize` split alone as
non-reportable evidence of generalization, consistent with standard train/test discipline in
supervised learning (Dietterich, 1998) applied here to a search-based rather than gradient-based
optimizer — which is why, as Section 5.3 states plainly, we do not report Foundry's own in-sample
`composite_score` as a substitute for a holdout number it was never computed on: doing so would
violate this section's own discipline for the one column of Table 3 it would be easiest to backfill
incorrectly.

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
  the item matches a named `agent_tests` entry; a `forbidden` tool-call-policy violation subtracts
  0.4 (a matching call observed); a `required` tool-call-policy violation subtracts 0.3 if no
  required tool was called at all, or 0.1 per still-missing tool if only some, but not all, of a
  required set was called (a distinct, smaller partial-overlap penalty from the full-miss case, and
  the one term that does **not** by itself count as a "hard violation" below — only a full miss, a
  `forbidden`-policy violation, or a present `must_not_contain` match does); and the per-item score
  is floored at 0.15 if the matching test is tagged `regression_blocks: true` and any hard violation
  occurred, then clipped to `[0, 1]`. When a judge is enabled, this deterministic
  score is blended with a judge-scored average across the agent's `rubrics` at a configurable weight
  (default 0.4 for the judge component). The composite score reported per agent per system in Table
  3 is the mean of this per-item score across all ten held-out items. The exact implementation is
  `score_response` in `_baselines/dspy_mipro/metric.py`, written once and intended to score both
  tracks identically. **In the current pipeline it is exercised end-to-end for the DSPy track only.**
  Producing a Foundry response-level score requires a harness that invokes the exported/deployed
  Foundry candidate against `dataset/holdout.jsonl`, captures its real responses and tool calls, and
  passes them to this same function — no such harness exists yet in this pack (Section 8, Section 9).
  Until it does, `compare_to_foundry.py` reports Foundry's response-level holdout score as
  unavailable rather than substituting `outputs.composite_score`, the Optimize wizard's own reported
  number: that field is computed in-sample against whatever was uploaded to the wizard
  (`dataset/optimize.jsonl`, per `experiment-runbook.md` Step 3), not against the held-out split, so
  treating it as a holdout number would silently violate the leakage discipline Section 5.2 states.
  Table 3's "Foundry (optimized)" column and every number derived from it (the Wilcoxon test and
  effect size in the same table) depend on this harness being built before they can be reported as
  real.

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

This benchmark's replicate-run design (Section 5.4) supports two distinct comparisons, and — unlike
an earlier draft of this paper — we now use a different test for each, because they differ in
whether the compared samples are meaningfully paired.

**Within-system: did optimization move the score relative to baseline?** Each agent's baseline
score is a single fixed value (the unoptimized instructions, evaluated once — there is no replicate
baseline). Testing whether the k replicate *optimized* holdout scores differ from that one fixed
reference is a **one-sample Wilcoxon signed-rank test** applied to the k differences
`optimized_i − baseline`: each difference is validly paired against the same constant, so the usual
non-normality-tolerant properties of the signed-rank test (Demšar, 2006) apply cleanly here. The
exact smallest achievable two-sided p-value for this test at k non-tied observations is 2^(1−k); at
k = 5 that floor is 0.0625, so no effect size can reach p < 0.05 below that sample size, and after
Holm-Bonferroni correction across ten agents the strictest comparison in the family must clear
α/10 = 0.005, which requires 2^(1−k) ≤ 0.005, i.e., k ≥ 9.

**Cross-system: does Foundry's optimized-score distribution differ from DSPy's?** This compares two
*independent* samples of k replicate holdout scores each — one system's replicate seeds share no
randomness with the other's, so there is no principled way to pair "Foundry seed 3" with "DSPy seed
3." An earlier draft of this paper used a paired Wilcoxon signed-rank test for this comparison
anyway, pairing runs by seed index; an external review correctly identified this as invalid, since
an arbitrary pairing can distort the test's power in either direction. We instead use the
**Mann-Whitney U test** (equivalently, the unpaired Wilcoxon rank-sum test), the standard
non-parametric test for two independent samples, and report the common-language effect size (the
probability that a randomly drawn Foundry run outscores a randomly drawn DSPy run) alongside the
p-value. This test family has its own exact sample-size floor, which we derive the same way: for two
independent samples of equal size n with no ties, the single most extreme rank arrangement (every
observation in one sample outranking every observation in the other) has probability `1 / C(2n, n)`
under the null, so the smallest achievable two-sided p-value is `2 / C(2n, n)`. Concretely:

| n per system | C(2n, n) | Min. two-sided p | Clears Holm α/10 = 0.005 (10 agents)? |
|---|---|---|---|
| 5 | 252 | 0.0079 | No |
| **6** | 924 | **0.0022** | **Yes** |
| 7 | 3,432 | 0.0006 | Yes |
| 10 | 184,756 | 0.000011 | Yes |

This is a direct, favorable consequence of using the correct test: the mathematical floor for a
reportable Holm-corrected cross-system claim drops from k ≥ 9 (under the invalid paired test) to
**k ≥ 6** per system. We nonetheless run **k = 10** replicate seeds per agent-system pair as the
primary design, since the floor above only establishes that significance is *possible*, not that a
given real effect size will be *powered* to reach it — k = 10 gives real headroom beyond the bare
minimum. Where cost genuinely constrains a pair to fewer replicate seeds, k = 6 remains the reportable
floor for this test (unlike k < 9 under the old, invalid design, which could never have reported
significance at all regardless of the true effect), and we report only descriptive statistics,
stating plainly that no significance claim is made, for any pair below that floor. In every case we
report the bootstrap confidence interval and effect size — which degrade gracefully at any k, unlike
a p-value against a fixed threshold — as the primary evidence, with the significance test as a
secondary, correction-aware summary on top of it. We treat a composite-score delta smaller than each
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
replicate seeds, with the Holm-corrected Mann-Whitney U p-value for the cross-system (Foundry vs.
DSPy) comparison (Section 5.6). Two of ten agent rows are shown; the full table will report all ten.
The "Foundry (optimized)" column shown here is illustrative of the intended format only: as of this
draft, no harness exists that scores an exported Foundry candidate's real holdout responses with the
shared `score_response` function (Section 5.3), so this column cannot yet be populated with a real,
holdout-only, shared-code number — building that harness is this paper's most important open
prerequisite for reporting real results (Section 8, Section 9).*

| Agent | Baseline | Foundry (optimized) | DSPy MIPROv2 (optimized) | Mann-Whitney p (Holm-corrected) | Common-language effect size |
|---|---|---|---|---|---|
| 01 travel-approval-strict | 0.81 | 0.84 ± 0.03 [PLACEHOLDER] | 0.83 ± 0.04 [PLACEHOLDER] | 0.62 [PLACEHOLDER] | 0.54 [PLACEHOLDER] |
| 02 support-triage-messy | 0.41 | 0.79 ± 0.06 [PLACEHOLDER] | 0.74 ± 0.08 [PLACEHOLDER] | 0.04 [PLACEHOLDER] | 0.71 [PLACEHOLDER] |

*(Rows for agents 03–10 omitted from this draft in the same illustrative format; the real results
section will report all ten, each backed by k=10 replicate runs per system.)*

### 6.2 Promotion-gate pass rate

*Table 4 (ILLUSTRATIVE — PLACEHOLDER). Fraction of the k=10 replicate runs whose winning candidate
has `blocked: false` (Section 5.3) — no critical failure in any of the four gating contract
categories. (An earlier draft of this caption also promised a per-test `regression_blocks`
pass/fail signal on the held-out split; the pipeline only records that signal implicitly, as a
0.15-floor effect inside the continuous response-level score, not as a reportable boolean, so that
clause is removed here rather than left unreportable — see Section 9 for the field this would
require.) Three of ten agent rows shown; the full table will report all ten, each out of 10 replicate
runs.*

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
agent. One of ten agent rows shown; rows omitted here, 10 total in the final version.*

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

*Table 7 (ILLUSTRATIVE — PLACEHOLDER). Mean instruction word-count growth ratio
(`instruction_growth_ratio_words_approx`) and estimated cost growth ratio (`est_cost_growth_ratio`,
optimized vs. baseline) across k=10 replicate seeds, against each agent's pre-registered
`max_instruction_growth_ratio` bound. A prior revision of this paper dropped the cost column because
nothing in this pack computed a cost-growth-ratio for either track; `_tools/model_pricing.py` now
implements that formula (a word-count-proxy token estimate, the same proxy the instruction-growth
column already uses, priced against a small, dated, explicitly **unverified** per-model rate table —
see the module's own `[AUTHOR ACTION]` notes). `run_mipro_baseline.py` computes and writes a real
`est_cost_growth_ratio` into every DSPy run's manifest today; `run_manifest_template.json` defines
the same field, null by default, for a future Foundry-side harness to populate the same way once one
exists (Section 8) — it does not compute or write a value itself. The column is restored here as a
matter of what the pipeline can now compute for at least one track; the numbers below remain
placeholders like everything else in this section, and the underlying price table still needs
verifying against
each vendor's live pricing page before a real cost figure is reported (Section 8).*

| Agent | Foundry instr. growth | DSPy instr. growth | Foundry est. cost growth | DSPy est. cost growth | Agent's stated bound |
|---|---|---|---|---|---|
| 01 travel-approval-strict | 1.4× [PLACEHOLDER] | 1.5× [PLACEHOLDER] | 1.3× [PLACEHOLDER] | 1.4× [PLACEHOLDER] | 1.6× (instr.) / 1.5× (cost) |
| 06 sales-brief-underspecified | 8.2× [PLACEHOLDER] | 6.7× [PLACEHOLDER] | 7.1× [PLACEHOLDER] | 5.9× [PLACEHOLDER] | 30× (instr.) / 25× (cost) — deliberately loose; see `docs/agent-evaluation-guide.md` |

### 6.6 Iterative refinement condition

*Table 8 (ILLUSTRATIVE — PLACEHOLDER). The elect-and-reoptimize condition's held-out score, reported
against the full distribution of independent replicate runs (Section 5.4), never against a single
input run. The bootstrap 95% CI column is what Section 7's own interpretive guidance asks the reader
to check the Run 3 score against.*

| Agent | Independent replicate runs (mean ± sd, k=10) | Bootstrap 95% CI | Elect-and-reoptimize (Run 3) score |
|---|---|---|---|
| 01 travel-approval-strict | 0.84 ± 0.03 [PLACEHOLDER] | [0.82, 0.86] [PLACEHOLDER] | 0.85 [PLACEHOLDER] |

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
- Table 7 should be read as the instruction-length and estimated-dollar cost the optimizer spent to
  achieve whatever delta Table 3 shows for the same agent — a score improvement that costs growth
  beyond either of the agent's two pre-registered bounds (`max_instruction_growth_ratio`,
  `max_cost_growth_ratio`) is a trade-off to weigh deliberately, not a clean win, regardless of the
  sign of the Table 3 delta. Both growth-ratio columns are word-count-proxy estimates, not precise
  measurements (Section 8) — read the ratio as directionally informative, and treat the underlying
  absolute dollar figures as order-of-magnitude only until the price table they're computed from is
  verified against each vendor's live pricing page.
- Table 8's iterative-refinement score should be read only in relation to the *distribution* column
  in the same table, never against Run 1 or Run 2 individually (Section 5.4); if it falls within
  that distribution's confidence interval, that is evidence the re-optimization step did not
  measurably help beyond ordinary replicate-run variance, which is itself a reportable finding, not
  an absence of one.

## 8. Limitations

- **The response-level composite score (Table 3) currently has no code path for the Foundry track.**
  `score_response` (Section 5.3) is written once for both tracks but is exercised end-to-end for
  DSPy only; producing a genuinely comparable Foundry number requires a harness that runs an
  exported/deployed candidate against `dataset/holdout.jsonl` and scores its real responses and tool
  calls, which this pack does not yet build. Until it exists, Table 3's Foundry column — and the
  cross-system Mann-Whitney test and effect size computed from it (Section 5.6) — cannot be reported
  as real data; `Section 9` lists this as the paper's single highest-priority remaining
  infrastructure gap.
- **Foundry is a closed, versioned, non-deterministic hosted service.** We cannot guarantee that two
  runs separated in time used an identical underlying model version, and the platform's internal
  search algorithm is not published, so any structural comparison to the methods in Section 2.1 is
  necessarily inferred from documented behavior (Microsoft, 2026), not confirmed against source.
- **A single open baseline (DSPy MIPROv2) is one comparison point**, not a claim that Foundry's
  optimizer is better or worse than automatic prompt optimization broadly; Section 3 states the
  specific, narrow reasons for this choice.
- **The k = 10 replicate-seed target (Section 5.6) is expensive**: for the full ten-agent pack across
  both systems, that is 200 optimization runs at full scale, and more again for any additional
  optimization target compared in the future. The cross-system Mann-Whitney test's mathematical floor
  is actually k ≥ 6 per system, not k ≥ 10 (Section 5.6) — so a budget-constrained run can fall back
  to k = 6–7 for a specific agent-system pair and still, in principle, report a real Holm-corrected
  significance claim for it, unlike under the paired test an earlier draft of this paper used, which
  could never reach significance below k = 9 regardless of the effect size. We still target k = 10
  as the primary design for the statistical power this floor alone does not guarantee, and consider
  the cost of doing so an honest cost of the standard we hold ourselves to, not a flaw to work around
  by lowering k and reporting a p-value that sample size cannot support.
- **The two MCP agents are evaluated on an instructions-and-function-tools-only basis in the DSPy
  track**, since no production MCP server exists in this repository to call for real; this is stated
  plainly in the benchmark's own documentation and any DSPy-vs-Foundry delta on those two agents
  should not be read as a like-for-like MCP-retrieval comparison.
- **Agent 07's injection patterns are fixed, not context-aware.** AgentLure (Section 2.3) argues that
  a context-insensitive injection benchmark understates real risk because a genuine adversary adapts
  its attack to the agent's current context rather than injecting a fixed payload. Agent 07's
  tool-output injection tests (Section 4) are fixed patterns, rephrased between the optimizer-visible
  and held-out splits (Section 4.3) but not adaptive to the candidate instructions under test; a
  sufficiently context-aware attacker could plausibly evade them in a way an optimizer's rewrite would
  not be credited or penalized for. Section 9 lists tightening this toward AgentSecBench's
  noninterference framing as a direction for closing this gap.
- **The cost-growth-ratio metric (`_tools/model_pricing.py`, Table 7) is a word-count-proxy estimate
  priced against an explicitly unverified rate table**, not a measurement against real billed usage.
  Every entry in `model_pricing.PRICE_TABLE` is tagged `verified: False` and must be checked against
  each vendor's current pricing page before a real cost figure from it is reported; the *ratio* is
  more defensible than the *absolute dollar figure* it's derived from, since the same word-count
  proxy applies to both the baseline and optimized side and much of its bias cancels, but neither
  should be read as a precise, billable cost. Both manifest formats now record per-call cost
  estimates and the growth ratio computed from them; verifying the underlying rates is the remaining
  gap, not the wiring itself.
- **The judge layer's deterministic-only fallback path was smoke-tested with a heuristic stub judge
  that has no real language understanding**; every real judged number in this paper depends on
  actual judge-model calls, and the stub path exists only to validate that the code executes, never
  as a source of reportable data.
- **The composite-score weights (`score_response`, Section 5.3) have not been checked for
  robustness on real data.** `_baselines/dspy_mipro/score_sensitivity.py` exists and can re-score
  already-captured logs under a perturbation grid at zero additional cost, but it has only been run
  against dry-run stub-LM output so far — a real sensitivity number, showing whether this paper's
  Table 3/4 conclusions would survive a different reasonable choice of penalty weights, requires the
  real experimental logs Phase 2 produces (Section 9).
- **Citations to the academic literature in Section 2 are drawn from the authors' working knowledge
  and have not yet been independently verified against primary sources (exact venue, volume, and
  page) for this draft**, with one exception: Debenedetti et al. (2024, AgentDojo), Ursekar et al.
  (2026, VeRO), Ghoshal et al. (2026, JTPRO), Weng et al. (2026, AgentLure/Argus), Alpay & Alpay
  (2026, AgentSecBench), Bai & Shi (2026, MAS-PromptBench), Wan et al. (2026, LCO), and Li et al.
  (2026, Constraint Drift) were added in this revision after a live literature search that confirmed
  each paper's existence, arXiv identifier, and author list directly (see
  `docs/paper/publication-plan.md` §3) — specifically because an external review's citation
  suggestions, and, in this pass, our own novelty-check search, are exactly the kind of claim that
  can be hallucinated and should never be taken on faith. The rest of Section 2, including the two
  citations with the least standardized public form — Opsahl-Ott et al. (2024) for MIPROv2 and
  Panickssery et al. (2024) — still needs this same verification pass before any submission-ready
  version. The Foundry (Microsoft, 2026) and Bedrock AgentCore (Amazon, 2026) product-documentation
  citations, and the six commercial regression-testing tooling citations added in Section 2.8
  (Braintrust, PromptLayer, LangSmith and Promptim, Langfuse, and DeepEval, all 2026), likewise need
  their exact URLs and access dates confirmed by the authors before submission — each was described
  from public search results summarizing the vendor's own claims, not from a directly fetched page,
  since this pack's network access could not reach any of these domains at the time of this literature
  pass.

## 9. Future work

- **Build the missing Foundry-side response-level scoring harness** (Section 5.3, Section 8): a
  script that takes an exported/deployed Foundry candidate, runs it against every item in
  `dataset/holdout.jsonl`, captures its real responses and tool calls, and scores them with the same
  `score_response` function the DSPy track already uses end-to-end. This is the single prerequisite
  every other number in Table 3 — including the cross-system Mann-Whitney test and effect size —
  depends on before it
  can be reported as real rather than illustrative.
- Implement a per-test, recorded pass/fail signal for `regression_blocks` agent_tests on the
  held-out split (rather than only the implicit 0.15-floor effect inside the continuous
  response-level score), so Table 4 can report the full gating definition an earlier draft of its
  caption promised, not only `blocked: false`.
- **Run `_tools/score_sensitivity.py`'s weight-perturbation grid against real experimental logs**
  once Phase 2 produces them, and report whether Table 3/4's conclusions are stable across the
  grid or weight-sensitive on any agent (Section 8).
- Verify `_tools/model_pricing.PRICE_TABLE`'s rates against each vendor's live pricing page (every
  entry is currently tagged `verified: False`), and replace the word-count token proxy with a real
  tokenizer count, so Table 7's cost-growth-ratio column can be reported as a measured figure rather
  than an order-of-magnitude estimate — a latency-growth-ratio metric alongside it (using each
  manifest's already-present but still-unused `est_latency_ms` field) is a natural extension once
  real runs produce a real latency number to record there.
- **Tighten agent 07's injection-resistance check toward a noninterference property**, in the spirit
  of AgentSecBench's (Section 2.3) instruction-integrity/retrieval-confidentiality/
  capability-integrity games: instead of pattern-matching whether a specific injected instruction's
  effect appears in the response, test whether the candidate's protected output changes when an
  untrusted observation changes while the trusted instruction and authorized content are held fixed
  — a stricter, more general property than the current `must_not_appear`/tool-call-policy checks, and
  one that would also partly address the fixed-vs-context-aware attack gap noted in Section 8.
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

Alpay, F., & Alpay, T. (2026). AgentSecBench: Measuring Prompt Injection, Privacy Leakage, and
Tool-Use Integrity in LLM Agents. *arXiv:2605.26269*. [Confirmed via literature search, 2026-08-18 —
see Section 8.]

Amazon. (2026). *Amazon Bedrock AgentCore: Optimization* [Product documentation, preview/general
availability]. **[AUTHOR ACTION — before submission: confirm the exact documentation URL and access
date; note in the surrounding text (Section 1, Table 1) that availability status may have changed
since this literature pass.]**

Andriushchenko, M., et al. (2024). AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents.

Bai, J., & Shi, L. (2026). MAS-PromptBench: When Does Prompt Optimization Improve Multi-Agent LLM
Systems? *arXiv:2606.23664*. [Confirmed via literature search, 2026-08-18 — see Section 8.]

Braintrust. (2026). *Braintrust* [Product documentation]. **[AUTHOR ACTION — before submission:
confirm the exact documentation URL and access date.]**

Confident AI. (2026). *DeepEval* [Open-source library documentation]. **[AUTHOR ACTION — before
submission: confirm the exact documentation URL and access date.]**

Debenedetti, E., Zhang, J., Balunović, M., Beurer-Kellner, L., Fischer, M., & Tramèr, F. (2024).
AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.
*NeurIPS Datasets and Benchmarks Track*. [Confirmed via literature search, 2026-08-18 — see Section
8.]

Demšar, J. (2006). Statistical Comparisons of Classifiers over Multiple Data Sets. *Journal of
Machine Learning Research*.

Dietterich, T. G. (1998). Approximate Statistical Tests for Comparing Supervised Classification
Learning Algorithms. *Neural Computation*.

Fernando, C., et al. (2023). Promptbreeder: Self-Referential Self-Improvement via Prompt Evolution.

Gebru, T., et al. (2018, revised 2021). Datasheets for Datasets. *Communications of the ACM*.

Ghoshal, S., Mittal, A., Singh, J., Ballesteros, M., Sun, W., Tu, F., Singh, S., Benajiba, Y., Shah,
F., Bharadwaj, S., Ravi, S., & Roth, D. (2026). JTPRO: A Joint Tool–Prompt Reflective Optimization
Framework for Language Agents. *arXiv:2604.19821*, Findings of ACL 2026. [Confirmed via literature
search, 2026-08-18 — see Section 8.]

Guo, Q., et al. (2023). Connecting Large Language Models with Evolutionary Algorithms Yields
Powerful Prompt Optimizers (EvoPrompt).

Jimenez, C. E., et al. (2023). SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

Khattab, O., et al. (2023). DSPy: Compiling Declarative Language Model Calls into Self-Improving
Pipelines.

LangChain. (2026). *LangSmith* [Product documentation]. **[AUTHOR ACTION — before submission:
confirm the exact documentation URL and access date.]**

LangChain. (2026). *Promptim* [Open-source library documentation, experimental]. **[AUTHOR ACTION —
before submission: confirm the exact documentation URL and access date; note its status may have
changed from "experimental" since this literature pass.]**

Langfuse. (2026). *Langfuse* [Product documentation]. **[AUTHOR ACTION — before submission: confirm
the exact documentation URL and access date.]**

Li, T., Ma, Y., Wen, H., Huang, Z., Zhou, Q., Fu, Z., & Cheng, G. (2026). Safe Multi-Agent Behavior
Must Be Maintained, Not Merely Asserted: Constraint Drift in LLM-Based Multi-Agent Systems.
*arXiv:2605.10481*. [Confirmed via literature search, 2026-08-18 — see Section 8.]

Liu, X., et al. (2023). AgentBench: Evaluating LLMs as Agents.

Mialon, G., et al. (2023). GAIA: A Benchmark for General AI Assistants.

Microsoft. (2026). *Microsoft Foundry Agent Service: Agent Optimizer* [Product documentation, public
preview]. **[AUTHOR ACTION — before submission: confirm the exact documentation URL and access
date.]**

Opsahl-Ott, K., et al. (2024). Optimizing Instructions and Demonstrations for Multi-Stage Language
Model Programs (MIPRO). **[AUTHOR ACTION — before submission: confirm exact author list and venue.]**

Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own
Generations. **[AUTHOR ACTION — before submission: confirm exact venue.]**

PromptLayer. (2026). *PromptLayer* [Product documentation]. **[AUTHOR ACTION — before submission:
confirm the exact documentation URL and access date.]**

Ruan, Y., et al. (2023). Identifying the Risks of LM Agents with an LM-Emulated Sandbox (ToolEmu).

Ursekar, V., Shanker, A., Chatrath, V., Xue, Y., & Denton, S. (2026). VeRO: An Evaluation Harness for
Agents to Optimize Agents. *arXiv:2602.22480*, ICML 2026. [Confirmed via literature search,
2026-08-18 — see Section 8.]

Wan, J., Chen, J., Yin, Z., Shuyuan, L., & Su, H. (2026). LCO: LLM-based Constraint Optimization for
Safer Agentic LLMs in Real-world Tasks. *arXiv:2605.27375*. [Confirmed via literature search,
2026-08-18 — see Section 8.]

Wang, X., et al. (2023). PromptAgent: Strategic Planning with Language Models Enables
Expert-Level Prompt Optimization.

Weng, S., Feng, Y., Zhang, J., Xie, X., Yu, J., & Liu, J. (2026). ARGUS: Defending LLM Agents Against
Context-Aware Prompt Injection. *arXiv:2605.03378*. [Introduces the AgentLure benchmark. Confirmed
via literature search, 2026-08-18 — see Section 8.]

Yang, C., et al. (2023). Large Language Models as Optimizers (OPRO).

Yao, S., et al. (2024). τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.

Yuan, T., et al. (2024). R-Judge: Benchmarking Safety Risk Awareness for LLM Agents.

Yuksekgonul, M., et al. (2024). TextGrad: Automatic "Differentiation" via Text.

Zhan, Q., et al. (2024). InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated
Large Language Model Agents.

Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.

Zhou, S., et al. (2023). WebArena: A Realistic Web Environment for Building Autonomous Agents.

Zhou, Y., et al. (2022). Large Language Models Are Human-Level Prompt Engineers (APE).
