# Publication plan: responding to the external journal review of paper-v3

This plan turns the external review (pasted into this project, referred to below as **"the
journal review"** to distinguish it from our own two internal `agent-paper-reviewer` rounds) into
a scoped, sequenced set of actions.

**Status: Phase 0 complete** (greenlit 2026-08-18). Every §5 Phase 0 item is done — see
`response-letters/external-journal-review.md` for the item-by-item disposition and `paper-v4.md`
for the resulting manuscript. A follow-up internal review (`review-round-3.md`) then checked that
revision and found the protocol itself sound but its own revision-history bookkeeping inconsistent
with version control (`paper-v3.md` had been edited in place instead of preserved); see
`response-letters/round-3.md` for the correction. Phases 1-4 remain open and gated on live Foundry
access (§7).

**Framing.** The journal review's own overall assessment is the right one to anchor on: the design
is sound and unusually rigorous for this space, but the paper is *incomplete*, not *wrong* — every
substantive criticism is either (a) something that requires real experimental infrastructure we
haven't built yet, (b) a genuine, fixable methodological error (the Wilcoxon pairing issue), or
(c) a scope/positioning gap we can close with reading and writing alone. None of the feedback asks
us to abandon the design; all of it is "finish it properly."

---

## 1. Triage: every point in the review, sorted by what it actually requires

| # | Review item | Our assessment | Fix type | Owner | Priority |
|---|---|---|---|---|---|
| 1 | Paired Wilcoxon signed-rank is the wrong test for the **cross-system** (Foundry vs. DSPy) comparison — replicate seeds aren't paired by shared randomness | **Reviewer is correct.** This is a real bug, not a style note (see §2 below for the fix and why it's actually good news for our power problem). | Statistical redesign, paper text | Agent, now | **Blocking** |
| 2 | Foundry response-level holdout harness doesn't exist; the central comparison can't run | **We already knew this and disclosed it in Limitations/Future Work (paper-v3 §8/§9).** The reviewer is confirming it's the top blocker for *any* real submission, not flagging something we missed. | Infrastructure (new script), needs live Foundry access | **User** (credentials/quota) + Agent (build) | **Blocking** |
| 3 | No sensitivity analysis / ablation on composite-score weights, floors, judge-blend weight | Fair gap. We pre-registered the weights but never tested robustness to perturbing them. | New script, runs on existing eval logs — no new API calls needed | Agent, now | High |
| 4 | No human calibration of the LLM-judge layer | Fair gap. We measure judge-vs-cross-judge agreement (Section 5.5) but never judge-vs-human. | New protocol + small script; needs a human rater (or two) | Agent (tooling) + **User** (rating time) | High |
| 5 | Only one open baseline (DSPy MIPROv2) | We already scope and defend this choice narrowly (paper-v3 §3, §8). Reviewer isn't demanding a second baseline for acceptance, just noting the external-validity limit. No action required beyond keeping the existing honest scoping — already done. | None (already addressed) | — | Low |
| 6 | Benchmark breadth (10 agents, 300 items) is narrow | Same pattern: already listed in Future Work (§9). Reviewer flags it as a limitation, not a blocker. No action required for this submission cycle. | None (already addressed) | — | Low |
| 7 | Missing related work: VeRO, JTPRO, AgentDojo, AgentLure, AgentSecBench | **Real gap — and all five are real, findable papers** (verified below, §3). Must be added and positioned correctly. | Literature read + Related Work rewrite | Agent, now (research) + verification pass | **Blocking** |
| 8 | "Response to reviewers" scaffolding embedded in the manuscript body obscures the narrative | Correct and easy to fix — that scaffolding belongs in a separate rebuttal/response-letter document, not the submission PDF. | Restructure files | Agent, now | Medium |
| 9 | Table 1's product-documentation claims vs. what's empirically verified in this work should be more clearly boundaried | Fair — Table 1 already has a "qualitative, author-assessed" caveat (from round-1 fixes) but doesn't distinguish column-by-column which claims are ours to verify vs. Foundry's own documentation. | Table 1 caption/column rewrite | Agent, now | Medium |
| 10 | k=10 resource burden is high; "demonstrating feasibility across all agents/systems would be useful" | The Mann-Whitney fix (§2) actually *lowers* the mathematical floor from k=9 to k=6 per system. We should still target k=10 for power, but this gives real headroom to report partial results honestly if budget is constrained. | Folds into §2's statistical redesign | Agent, now | Medium |
| 11 | No plan for cost/latency metrics (the previously-dropped "cost growth ratio") | Reviewer explicitly asks whether we'll treat this as primary/secondary. We can wire up the *formula* now; populating it needs real token/latency logs from real runs. | Code (formula + manifest fields) now; real numbers need Phase 2 | Agent (code) + **User** (real runs) | Medium |
| 12 | Election-strategy ablation for iterative refinement (multiple validation-slice schedules/budgets) | Reasonable extension, not required for a first complete submission. Treat as an explicit Future Work item with a named design, not a blocker. | Paper text only for now | Agent, now | Low |

---

## 2. The statistical fix (worked, not just described)

**The problem.** Section 5.6 (paper-v3) runs a **paired** Wilcoxon signed-rank test between
Foundry's k=10 holdout scores and DSPy's k=10 holdout scores for each agent, treating "Foundry
seed 3" and "DSPy seed 3" as a matched pair. There is no shared randomness linking those two
runs — different systems, different search algorithms, unrelated seed semantics. Pairing them is
arbitrary, and an arbitrary pairing can inflate or deflate the test's power in an unprincipled way
(the reviewer's Mann-Whitney suggestion targets exactly this).

**The fix has two parts, because the paper actually contains two different comparisons that need
two different tests:**

1. **Within-system: "did optimization move the score relative to baseline?"** The baseline score
   is a single fixed number per agent (there's no replicate baseline — it's the unoptimized
   instructions, evaluated once). Testing whether the k replicate *optimized* scores differ from
   that one fixed reference is a legitimate **one-sample Wilcoxon signed-rank test** (against a
   constant, not against another sample) — each of the k differences `optimized_i − baseline` is
   validly "paired" with the same constant. This part of Section 5.6 was never actually broken and
   can stay as-is, just re-labeled clearly as a one-sample test so the distinction is explicit.

2. **Cross-system: "does Foundry's optimized-score distribution differ from DSPy's?"** This is
   two independent samples of size k each with no natural pairing → the reviewer is right, this
   needs the **Mann-Whitney U / Wilcoxon rank-sum test** (unpaired), with the rank-biserial (or
   common-language / A-statistic) effect size computed for two independent samples instead of for
   paired differences.

**A derived consequence worth putting in the paper.** The exact minimum achievable two-sided
p-value for a Mann-Whitney U test with equal sample sizes `n` per group (no ties) is
`2 / C(2n, n)` — the probability of the single most extreme rank arrangement, doubled for
two-sidedness. Computed directly:

| n per system | C(2n, n) | min two-sided p | clears Holm α/10 = 0.005 (10 agents)? |
|---|---|---|---|
| 3 | 20 | 0.1000 | No |
| 4 | 70 | 0.0286 | No |
| 5 | 252 | 0.0079 | No |
| **6** | 924 | **0.00216** | **Yes** |
| 7 | 3,432 | 0.00058 | Yes |
| 10 | 184,756 | 0.000011 | Yes |

This is genuinely useful news, not just a bug fix: the old paired-Wilcoxon-signed-rank floor
required **k ≥ 9** (derived in paper-v3 §5.6 from `2^(1−k)`); the statistically *correct* unpaired
test's floor drops to **k ≥ 6** per system. We should still run k = 10 as the primary design,
because the floor is about whether significance is *mathematically possible*, not about
*statistical power* at realistic effect sizes — but this gives us a documented fallback: if budget
or Foundry preview quota forces us to cut a system-agent pair short, k = 6–7 is still capable of
producing a real Holm-corrected significance claim, which k = 5 or below never was under either
test. Worth stating explicitly in the revised Section 5.6.

**Action:** rewrite Section 5.6 to (a) keep the one-sample Wilcoxon for the baseline-delta claim,
(b) switch to Mann-Whitney U for the cross-system claim, (c) replace the `2^(1−k)` derivation with
the `2/C(2n,n)` derivation for the part of the section it actually applies to now, (d) update
Table 3's "Wilcoxon p (Holm-corrected)" column header and every downstream reference to it
(§7's decision rule, §8's cost-of-k=10 limitation) accordingly.

---

## 3. Related work: verification results

Before adding anything, I checked whether the five works the review named actually exist (an
external LLM-generated review can hallucinate citations, so this isn't optional). All five are
real:

| Named work | What it actually is | Source | Status |
|---|---|---|---|
| **VeRO** (review spells it "VERO") | *VeRO: An Evaluation Harness for Agents to Optimize Agents* (Scale AI, Feb 2026) — a harness for evaluating whether coding agents can improve *other* agents' prompts/tools/workflows via edit-execute-evaluate cycles, with versioned snapshots and structured execution traces. | arXiv:2602.22480 | Exists; correct spelling is **VeRO**, not VERO — fix the review's typo when we cite it. Author list not yet confirmed — needs an `[AUTHOR ACTION]` pass. |
| **JTPRO** | *JTPRO: A Joint Tool–Prompt Reflective Optimization Framework for Language Agents* — co-optimizes global instructions and per-tool schema/argument descriptions via rollout-driven reflection. ACL Findings 2026. | arXiv:2604.19821 | Exists, published venue confirmed (ACL Findings 2026). Author list needs confirmation. |
| **AgentDojo** | Debenedetti et al., *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents*, NeurIPS 2024 Datasets & Benchmarks Track. | arXiv:2406.13352 | Exists, well-established, author list already known (Debenedetti et al.). **Not currently cited in paper-v3 at all** — this is a real omission independent of the journal review; it belongs next to InjecAgent in §2.3. |
| **AgentLure** | Not a standalone paper — it's a benchmark introduced *inside* another paper, *ARGUS: Defending LLM Agents Against Context-Aware Prompt Injection* (2026): 320 context-dependent-task / context-aware-attack samples across 4 agent environments and 8 attack vectors. | arXiv:2605.03378 | Exists, but must be cited as "AgentLure, introduced in Argus et al./[authors], 2026," not as its own independent paper. |
| **AgentSecBench** | *AgentSecBench: Measuring Prompt Injection, Privacy Leakage, and Tool-Use Integrity in LLM Agents* (2026) — frames agent security as noninterference between untrusted observations and a protected output/action predicate. | arXiv:2605.26269 | Exists — but **do not confuse with "Agent Security Bench (ASB)"** (Zhang et al., arXiv:2410.02644, 2024), a different, earlier, similarly-named paper. Both should probably be checked; the review named "AgentSecBench" specifically, which matches 2605.26269. |

**Positioning draft (for the Related Work rewrite, not final prose):**
- VeRO and JTPRO both sit in "agents/optimizers that touch tool schemas and prompts jointly" —
  closer structurally to our DSPy/MIPROv2 comparison point (§2.1/§3) than to our benchmark's
  actual contribution. The differentiator to state precisely: neither audits *preservation* of
  safety/policy properties under rewrite — both are utility-maximizing optimizers evaluated on
  task success, the same accuracy-only framing our §2.1 already critiques for APE/OPRO/EvoPrompt/
  PromptBreeder/PromptAgent/TextGrad. VeRO's "agents optimizing agents" framing is worth an
  explicit sentence since it's the closest thing to "an optimizer we didn't audit for
  preservation" that exists in 2026 literature.
- AgentDojo, AgentLure, and AgentSecBench belong in §2.3 alongside InjecAgent/AgentHarm/ToolEmu/
  R-Judge, extending Table 1's injection-related columns. AgentDojo and AgentLure both test a
  *fixed* agent's vulnerability (same category as InjecAgent) — our novelty framing ("we test an
  optimizer's *effect* on that vulnerability, not the vulnerability itself") extends cleanly to
  them with no new argument needed. AgentSecBench's noninterference framing is worth a specific
  callout: it's a more formal security property than what we currently measure, and could sharpen
  our own injection-resistance scoring in Future Work (a testable idea: define agent 07's
  preservation check as a noninterference statement rather than a pass/fail pattern match).

**Action:** confirm exact author lists/venues for all five (an `[AUTHOR ACTION]` tag, same
convention as the rest of the reference list), then write the actual §2.1/§2.3/Table 1 prose and
add AgentDojo/AgentLure/AgentSecBench columns to Table 1.

---

## 4. Presentation: separating the manuscript from its revision history

The review is right that the embedded "Response to reviewers" tables read as scaffolding once
you're evaluating the paper as a submission rather than as a working draft. Standard practice is a
clean manuscript plus a *separate* response/rebuttal letter (most venues require this format
anyway). Action:

- Move the "Response to reviewers — round 1" and "— round 2" tables out of `paper-v3.md`'s body
  into new files: `docs/paper/response-letters/round-1.md` and `round-2.md`.
- The next manuscript version (below, "paper-v4") is the clean paper only — abstract through
  references, no meta-commentary about its own revision history.
- Keep `docs/paper/README.md`'s trail table as the single place that narrates "how we got here" for
  anyone reading the repo, so that context isn't lost, just moved out of the submission artifact.

---

## 5. Phased roadmap

**Phase 0 — Protocol and manuscript fixes (no live Foundry/API access required).**
Everything in this phase is buildable and verifiable in this environment right now.
- Rewrite Section 5.6 per §2 above (Mann-Whitney for cross-system, one-sample Wilcoxon kept for
  within-system, new `2/C(2n,n)` derivation), and propagate the change through Table 3's column,
  §7's decision rule, §8.
- Build `_tools/score_sensitivity.py`: recompute `score_response` under a small grid of perturbed
  weights (severity weights ±25%, floor at 0.10/0.15/0.20, `judge_weight` at 0.2/0.4/0.6) against
  already-captured response/tool-call logs — no new LM calls needed. Report whether per-agent
  Foundry-vs-DSPy ranking and gate-pass conclusions are stable across the grid.
- Build a human-rating ingestion path: a CSV/JSON schema for human-labeled semantic-rule verdicts,
  feeding the *same* `JudgeAgreementTracker` (`cohens_kappa`/`pearson_r`) already used for
  judge-vs-cross-judge agreement, so judge-vs-human uses identical statistical machinery. No human
  data yet — just the plumbing and the sampling protocol (stratified, oversampling agent 05 and
  `should_edit`/semantic `must_have` items).
- Wire up the cost-growth-ratio formula and manifest fields (token counts × a dated, versioned
  per-model price table) for both tracks, restoring the column Table 7 dropped in paper-v3 — code
  only; real numbers wait for Phase 2.
- Literature: confirm exact citations for VeRO, JTPRO, AgentDojo, AgentLure/Argus, AgentSecBench;
  write the Related Work additions and extend Table 1.
- Split the response-letter scaffolding out per §4; produce `paper-v4.md` as a clean manuscript
  (Section 6 still explicitly placeholder — nothing here produces real numbers).
- Run our own `agent-paper-reviewer` skill against `paper-v4.md` as an internal check before
  treating any of the above as "done" — specifically asking it to verify the Mann-Whitney fix is
  self-consistent and that the five new citations are positioned correctly, the same code-level
  verification standard it applied in rounds 1–2.

**Phase 1 — Build the Foundry response-level harness (requires live Foundry access).**
This is the review's single most-repeated point and the one item nothing in Phase 0 can substitute
for.
- Research Foundry Agent Service's runtime invocation surface (SDK/REST) for calling an
  exported/deployed candidate programmatically with a holdout item and capturing its full response
  plus tool-call trace — distinct from the Optimize wizard used for search itself.
- Build a harness script analogous to `run_mipro_baseline.py`'s evaluation path, but driving a
  deployed Foundry candidate instead of a DSPy module, writing `outputs.holdout_composite_score`
  into the run manifest the way `run_manifest_template.json` already anticipates.
- Smoke-test against one exported candidate end-to-end before trusting it at scale.
- **Requires from you:** a live Foundry Agent Service resource with Optimize-wizard and deployment
  access, and whatever credentials/quota that needs — this sandbox has never had that access.

**Phase 2 — Run the real experiment (requires budget: API/optimizer usage costs).**
- Run replicate seeds for both tracks, all ten agents. Given §2's finding, a defensible plan is:
  run k = 10 as the primary design (matches the already-published power reasoning), but if cost
  forces a cut, k = 6–7 per system is the actual mathematical floor for a reportable
  Holm-corrected cross-system claim — no longer k = 9–10 across the board.
- Run the elect-and-reoptimize condition (Table 8) using the already-fixed leak-free election
  score.
- Run the real LLM-judge layer (real judge model calls, not the stub) for every semantic rule.
- Run `score_sensitivity.py` from Phase 0 against the real logs.
- Populate the real cost-growth-ratio numbers from Phase 0's wiring.

**Phase 3 — Human calibration study (requires human raters — you and/or collaborators).**
- Rate the stratified sample from Phase 0's protocol (target ~60–100 items).
- Compute judge-vs-human agreement with the same machinery as judge-vs-cross-judge.
- Report alongside Table 5, with the same low-agreement caveat rule already in §5.5.

**Phase 4 — Final write-up and submission.**
- Replace every `[PLACEHOLDER]` in Section 6 with real numbers from Phase 2–3.
- Write real Sections 7 (interpretation) and 10 (conclusion) — no more bracketed
  `[PLACEHOLDER: does/does not]` language.
- One more internal review pass (`agent-paper-reviewer`) against the fully real draft before
  external submission — this would be a new round, since round 1–2 never saw real data.
- Submit.

---

## 6. Venue: dual target — TMLR and NeurIPS Datasets & Benchmarks

**Decision (made 2026-08-18): pursue both**, not primary/alternate. They don't conflict — TMLR is
a journal with rolling review and no exclusivity requirement against submitting the same work to a
conference track before a TMLR decision is out, and NeurIPS D&B is the closest annual-deadline
venue to this paper's actual contribution shape (benchmark + harness + open baseline). Practical
sequencing implications, since the two have different rhythms:

- **NeurIPS D&B has a fixed annual deadline** (typically ~May for the following December
  conference) and a fixed, non-negotiable bar: real results, no placeholders, full harness
  (including the Foundry response-level scoring path from Phase 1) working end-to-end well before
  submission. If the Foundry harness (Phase 1) or the real experimental run (Phase 2) slips past
  that deadline for a given year, NeurIPS D&B for that cycle is off the table — there's no rolling
  fallback. Track the actual current-year deadline once Phase 1 is underway and treat it as the
  hard forcing function for Phases 1–3's timeline, not the other way around.
- **TMLR has no deadline** — submit whenever Phase 4 (real numbers, real Sections 6/7/10) is
  actually done, independent of the NeurIPS calendar. If the NeurIPS D&B deadline is missed in a
  given cycle, that costs nothing for TMLR; the same finished paper goes there instead, or first,
  with no changes needed beyond formatting (TMLR doesn't enforce a page limit or camera-ready
  conference template the way NeurIPS D&B does — the same LaTeX source largely works for both,
  minus the venue-specific style file and page-limit trimming NeurIPS demands).
- **Recommended path**: keep the same finished manuscript on both tracks — write for TMLR's
  no-page-limit norms first (all appendices/tables in the main body), then produce a NeurIPS D&B
  submission by moving overflow content to an appendix to fit its page limit, once the Foundry
  deadline for that year is confirmed reachable. Do not submit to both simultaneously (most venues
  bar concurrent submission of the same paper) — decide which one goes first once Phase 4's
  finish date is known relative to the nearest NeurIPS D&B deadline.

COLM and ACL Rolling Review (→EMNLP/ACL/NAACL) remain reasonable fallback options if either primary
target's review comes back requesting changes larger than a revision, but are a tighter content fit
for the DSPy/optimization-methods side of this paper than for its benchmark-and-audit framing.

---

## 7. Decisions made / still open

**Resolved 2026-08-18:**
- Phase 0 is greenlit, in full.
- Venue: dual target, TMLR and NeurIPS D&B (§6) — no single primary.

**Still open, gating Phase 1 onward:**
1. Do you have (or can you get) live Foundry Agent Service access for Phase 1, and on what
   timeline — that's the one dependency that gates everything downstream of it, and (per §6) the
   one that determines whether a given year's NeurIPS D&B deadline is reachable at all.
