# 03 — invoice-extractor-schema

**Baseline quality:** mixed. **MCP:** no. **Tools:** 2 function tools. **Rows:** 30 (20 optimize / 10 holdout).

Tests preservation of a machine-readable output contract. The 14-key JSON schema is the mandatory
core; the surrounding prose is padding, hedging, and two instructions that directly contradict the
contract ("explain your reasoning before the JSON", "be a bit conversational"). A good candidate
keeps the schema byte-exact and deletes both contradictions.

## What this sample tests

- **Schema drift.** MN-02 guards against an optimizer "helpfully" adding a key (`notes`,
  `payment_status`, `processing_notes`) — the two schema-drift baits in the dataset (inv-014, holdout
  inv-108) are phrased completely differently on purpose, to catch a fix that only blocks the exact
  training wording.
- **Contradiction removal, not softening.** SR-01 and SR-02 each cancel the JSON-only contract.
  Removing only one still yields non-deterministic output — the validator checks both are gone.
- **No silent arithmetic correction, even under direct pressure.** inv-017 has a user explicitly
  asking the agent to "fix" a mismatched total; the holdout set adds a genuinely-consistent
  mixed-sign invoice (inv-110/T-09) as the mirror-image trap — flagging *that* as a mismatch is
  over-generalization, not safety.
- **Verbatim schema preservation.** MH-01 is the one must_have in the whole pack marked
  `verbatim_required: true` — a semantic paraphrase of the key list is a failure here, unlike
  everywhere else in the pack.

## Fixes applied in this revision

- Dataset split into optimize (20) / holdout (10); the VAT-fabrication bait (inv-104) and the
  consistent-negative-line-item near-miss (inv-110) are both held out specifically because they're
  rephrasing/mirror-image tests of training-set traps.
- `judge_config` note: schema-validity and no-prose rubrics are flagged for deterministic (JSON-parse)
  scoring rather than LLM-judge scoring wherever the harness supports it, since they don't need a
  judge at all.
- SA-03 (negative-amount/credit-note guidance) added as a should_add, closing a gap the original
  dataset didn't cover.
