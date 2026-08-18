"""
stub_lm.py — a deterministic, zero-cost, zero-network stand-in for a real LM, used ONLY to
smoke-test the MIPROv2 wiring end-to-end (dataset loading -> program construction -> few-shot
bootstrapping -> instruction proposal -> candidate evaluation -> compile() return) with no API
credentials and no cost.

It has NO language understanding. It inspects which output fields the current DSPy adapter call is
asking for (via ChatAdapter's numbered `` `fieldname` (type): `` field list, which is present for
every internal DSPy signature — the task program's, ReAct's, and MIPROv2's own instruction-proposer
and dataset-summarizer signatures alike) and returns a fixed, plausible-shaped placeholder value per
field, reusing dspy.utils.DummyLM's own adapter-aware formatting so the wire format always matches
what the calling adapter expects.

This proves the PLUMBING is correct end-to-end. It says nothing about optimization QUALITY — a run
against this stub will "compile" without crashing, but the "optimized" instructions it produces are
meaningless boilerplate. Real runs must pass --task-lm/--prompt-lm pointing at an actual model.
"""
from __future__ import annotations

import re

from dspy.utils.dummies import DummyLM, dotdict

_FIELD_HEADER_RE = re.compile(r"^\d+\.\s*`(\w+)`\s*\(", re.MULTILINE)

# Generic per-field-name placeholders for MIPROv2's OWN internal signatures (dataset summarization,
# tip generation, etc.) that aren't the task program's fields. Extend this if a future dspy version
# introduces a new internal signature this stub hasn't seen — an unrecognized field falls back to
# f"stub-{field}" rather than crashing.
_GENERIC_FIELD_VALUES = {
    "reasoning": "This request needs a clear, structured response following the given instructions.",
    "next_thought": "I have enough information to respond now.",
    "next_tool_name": "finish",
    "next_tool_args": "{}",
    "observations": "The dataset covers a range of requests typical for this agent's task.",
    "observation_summary": "The dataset covers a range of requests typical for this agent's task.",
    "summary": "The dataset covers a range of requests typical for this agent's task.",
    "tip": "Be clear, structured, and follow every explicit constraint stated in the instructions.",
    "module_description": "A single-step assistant that follows the stated instructions.",
    "program_description": "A single-step assistant that follows the stated instructions.",
    "program_code": "N/A",
    "dataset_description": "Synthetic call/support/policy requests for a single prompt agent.",
    "example_analysis": "The examples vary in phrasing but share the same task structure.",
    "language_model_role": "A helpful assistant that follows the given instructions precisely.",
}


class StubLM(DummyLM):
    """Field-adaptive stub LM. See module docstring."""

    def __init__(self, base_instructions: str, canned_response: str | None = None):
        super().__init__(answers=[])  # unused; forward() is fully overridden below
        self.base_instructions = base_instructions
        self.canned_response = canned_response or (
            "Acknowledged. Here is a response that follows the stated instructions and constraints."
        )
        self._instruction_variant_count = 0

    def _value_for(self, field: str) -> str:
        if field == "response":
            return self.canned_response
        if field == "proposed_instruction":
            self._instruction_variant_count += 1
            return (
                f"{self.base_instructions}\n\n"
                f"(stub-proposed clarification #{self._instruction_variant_count}: "
                f"follow every constraint above exactly and do not omit any stated rule.)"
            )
        return _GENERIC_FIELD_VALUES.get(field, f"stub-value-for-{field}")

    def forward(self, prompt=None, messages=None, **kwargs):
        messages = messages or [{"role": "user", "content": prompt}]
        text = "\n".join(m.get("content", "") for m in messages)
        fields = _FIELD_HEADER_RE.findall(text)
        if not fields:
            fields = list(_GENERIC_FIELD_VALUES.keys())  # best-effort fallback for an unseen format
        field_values = {f: self._value_for(f) for f in fields}
        content = self._format_answer_fields(field_values)
        choices = [dotdict(message=dotdict(content=content, tool_calls=None), finish_reason="stop")]
        return dotdict(choices=choices, usage=dotdict(prompt_tokens=0, completion_tokens=0, total_tokens=0), model="stub-lm")
