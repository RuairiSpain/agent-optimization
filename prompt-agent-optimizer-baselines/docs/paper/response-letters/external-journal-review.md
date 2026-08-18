# Response to reviewers — external journal review

Responds to an external journal review of [`paper-v3.md`](../paper-v3.md), pasted into this project
outside the `agent-paper-reviewer` skill's own two-round internal cycle (see
[`round-1.md`](round-1.md), [`round-2.md`](round-2.md)). The full triage — including which items
require live Foundry access, a real experimental run, or a human rater, and are therefore not yet
resolvable — is [`../publication-plan.md`](../publication-plan.md); this letter covers only what the
manuscript itself changed as "Phase 0" of that plan. The revision produced is
[`paper-v4.md`](../paper-v4.md).

| # | Review item | Status | Where |
|---|---|---|---|
| 1 | Paired Wilcoxon signed-rank is the wrong test for the cross-system comparison (replicate seeds share no randomness across systems) | **Done** | §5.6 now uses a one-sample Wilcoxon signed-rank test for the within-system baseline-delta claim (still valid — paired against a fixed constant) and a Mann-Whitney U test for the cross-system claim, with a re-derived sample-size floor (`2 / C(2n, n)`, clearing Holm α/10 at k=6 per system, not k=9). Propagated through Table 3's column header, §7, §8, §2.5, and the References. |
| 2 | Foundry response-level holdout harness doesn't exist; the central comparison can't run | **Not resolvable in this pass** | Already disclosed in §5.3/§8/§9 before this review; requires live Foundry access (`publication-plan.md` Phase 1). No manuscript change beyond what was already there. |
| 3 | No sensitivity analysis on composite-score weights | **Done (tooling)** | `_baselines/dspy_mipro/score_sensitivity.py` (new) re-scores captured logs under a weight-perturbation grid with zero new LM calls. `metric.py`'s `score_response` weights are now a named, overridable `DEFAULT_WEIGHTS` table. Real sensitivity numbers need real run logs (Phase 2). *(Note, added after `review-round-3.md`: this row originally claimed "the manuscript itself is unchanged by this item beyond what §8 already disclosed" — that was inaccurate, §8 disclosed no such thing at the time. See [`round-3.md`](round-3.md) item 3 for the correction.)* |
| 4 | No human calibration of the judge layer | **Done (tooling)** | `_tools/human_calibration.py` (new): `--sample` builds a stratified shortlist, `--score` computes judge-vs-human (and human-vs-human) agreement via the same `JudgeAgreementTracker` used for judge-vs-cross-judge. Needs a real human rater to produce a real number (Phase 3). |
| 5 | Only one open baseline (DSPy MIPROv2) | **No change** | Already scoped narrowly and defended in §3/§8; the review itself treats this as an external-validity limitation, not a blocker. |
| 6 | Benchmark breadth (10 agents, 300 items) is narrow | **No change** | Already listed as a §9 future-work item. |
| 7 | Missing related work: VeRO, JTPRO, AgentDojo, AgentLure, AgentSecBench | **Done** | All five verified as real via a live literature search (arXiv IDs, author lists — not taken on faith from the review) before citing. Added to §2.1 (VeRO, JTPRO), §2.3 (AgentDojo, AgentLure/Argus, AgentSecBench), Table 1 (new rows), and References. |
| 8 | "Response to reviewers" scaffolding embedded in the manuscript obscures the narrative | **Done** | This letter, [`round-1.md`](round-1.md), and [`round-2.md`](round-2.md) replace the response tables that previously sat at the top of the paper file itself. `paper-v4.md` is the manuscript alone. |
| 9 | Table 1's product-documentation claims vs. what's empirically verified should be more clearly boundaried | **Done** | Table 1's caption now states explicitly that every row but one cites a peer-reviewed/preprint paper, while the "Foundry agent optimizer" row alone describes vendor-reported product documentation, not an independently verified claim. |
| 10 | k=10 resource burden is high; demonstrate feasibility at lower k | **Done** | Item 1's Mann-Whitney fix shows k=6 per system is the real mathematical floor for a Holm-corrected cross-system claim, down from k=9 under the prior (invalid) test — folded into §5.6 and §8. |
| 11 | No plan for cost/latency metrics (the previously-dropped "cost growth ratio") | **Done** | `_tools/model_pricing.py` (new): a word-count-proxy cost-growth-ratio formula against a small, dated, explicitly `verified: False` per-model price table. Wired into `run_mipro_baseline.py`, `run_manifest_template.json`, and `compare_to_foundry.py`. Table 7's cost column, dropped in an earlier revision, is restored with a caption noting the price table still needs verification against live vendor pricing. |
| 12 | Election-strategy ablation for iterative refinement | **No change** | Reasonable extension, scoped as a named future-work item rather than blocking this revision — not added to §9 in this pass; tracked in `publication-plan.md` item #12 for a later revision. |

Questions for the authors are answered by the items above: Q1 (pairing justification) by item 1; Q2
(Foundry harness timeline) — no committed timeline exists yet, it depends on the live-access
dependency `publication-plan.md` §7 tracks; Q3 (weight sensitivity ablations) by item 3; Q4 (human
spot-check) by item 4; Q5 (expansion/cost plans) by items 6 and 11; Q6 (VeRO/JTPRO comparison) by
item 7; Q7 (multiple election strategies) — not yet, tracked as item 12 above.
