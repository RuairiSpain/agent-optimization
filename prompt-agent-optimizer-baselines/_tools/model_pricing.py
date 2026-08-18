"""
model_pricing.py — a small, dated, versioned per-model price table plus the cost-growth-ratio
formula both tracks (Foundry manifest fields, DSPy `run_mipro_baseline.py`) compute from it.

Reviewer finding (external journal review of paper-v3; see docs/paper/publication-plan.md item #11):
"No plan for cost/latency metrics (the previously-dropped 'cost growth ratio')." paper-v3.md's
Table 7 dropped its cost column in an earlier revision specifically because nothing in this pack
computed one (see docs/paper/paper-v3.md Section 8's "no cost-growth-ratio metric is implemented"
limitation, now superseded by this file). This module is the fix: the FORMULA and a PRICE TABLE now
exist and are wired into run_mipro_baseline.py's manifest output. Real cost numbers still require a
real run (Phase 2 of docs/paper/publication-plan.md) — this file makes that possible, it does not by
itself produce a real number.

WHAT THIS IS AND ISN'T:
- The token counts feeding this formula are the SAME word-count proxy already used for
  `instruction_growth_ratio_words_approx` (see run_mipro_baseline.py's `approx_token_count`) —
  this pack has no tokenizer dependency by design. A word-count proxy is fine for a RATIO (the same
  systematic bias applies to both the baseline and optimized side, so it mostly cancels), but the
  ABSOLUTE per-call USD figures this module also produces are order-of-magnitude estimates only —
  never report `*_est_cost_per_call_usd` as a precise, billable cost figure.
- PRICE_TABLE below is deliberately small (only models this pack's docs/examples actually name) and
  every entry is tagged `verified: False` with an `[AUTHOR ACTION]` note: these are illustrative,
  plausible-shaped rates, NOT confirmed against any vendor's live pricing page. Confirm each entry
  against the vendor's current pricing page — and re-date `as_of` — before reporting any cost number
  derived from it in the paper. `estimate_cost_usd` refuses to silently guess for an unpriced model:
  it returns None, and callers must propagate that as "cost unavailable," never as 0 or as a
  different model's rate.
"""
from __future__ import annotations

# usd_per_1k_input_tokens / usd_per_1k_output_tokens are placeholder-shaped, NOT verified against a
# live vendor pricing page. `verified: False` on every row is load-bearing, not decorative -- see
# the module docstring. Extend this table with the exact model strings --task-lm/--prompt-lm are
# actually run with before using it for a real cost figure.
PRICE_TABLE: dict[str, dict] = {
    "openai/gpt-4.1-mini": {
        "usd_per_1k_input_tokens": 0.0004, "usd_per_1k_output_tokens": 0.0016,
        "as_of": "2026-08-18", "verified": False,
        "source_note": "[AUTHOR ACTION] placeholder rate -- confirm against OpenAI's current pricing page.",
    },
    "openai/gpt-5": {
        "usd_per_1k_input_tokens": 0.0025, "usd_per_1k_output_tokens": 0.010,
        "as_of": "2026-08-18", "verified": False,
        "source_note": "[AUTHOR ACTION] placeholder rate -- confirm against OpenAI's current pricing page.",
    },
    "anthropic/claude-sonnet-5": {
        "usd_per_1k_input_tokens": 0.003, "usd_per_1k_output_tokens": 0.015,
        "as_of": "2026-08-18", "verified": False,
        "source_note": "[AUTHOR ACTION] placeholder rate -- confirm against Anthropic's current pricing page.",
    },
    "anthropic/claude-haiku-4-5": {
        "usd_per_1k_input_tokens": 0.0008, "usd_per_1k_output_tokens": 0.004,
        "as_of": "2026-08-18", "verified": False,
        "source_note": "[AUTHOR ACTION] placeholder rate -- confirm against Anthropic's current pricing page.",
    },
}

PRICE_TABLE_VERSION = "2026-08-18-draft-unverified"  # bump this string whenever PRICE_TABLE changes


def estimate_cost_usd(input_tokens: float, output_tokens: float, model: str,
                       pricing: dict[str, dict] = PRICE_TABLE) -> float | None:
    """Order-of-magnitude estimated USD cost of one call, from (proxy) token counts and this
    module's price table. Returns None -- never a fabricated number -- if `model` isn't in the
    table; callers must propagate that as "cost unavailable" for this model, not silently drop to
    zero or substitute a different model's rate."""
    entry = pricing.get(model)
    if entry is None:
        return None
    return (input_tokens / 1000.0) * entry["usd_per_1k_input_tokens"] + \
           (output_tokens / 1000.0) * entry["usd_per_1k_output_tokens"]


def cost_growth_ratio(baseline_cost_usd: float | None, optimized_cost_usd: float | None) -> float | None:
    """optimized / baseline, mirroring instruction_growth_ratio_words_approx's shape. None if
    either side is unavailable (unpriced model) or the baseline cost is exactly zero (undefined
    ratio) -- never silently reported as 1.0 or 0.0 in that case."""
    if baseline_cost_usd is None or optimized_cost_usd is None or baseline_cost_usd == 0:
        return None
    return optimized_cost_usd / baseline_cost_usd
