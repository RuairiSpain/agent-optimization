"""
dspy_program.py — builds a DSPy module for one agent from the pack, seeded with the agent's
baseline instructions text as the Signature's starting instructions (this is exactly the string
MIPROv2 rewrites during optimization — the same "baseline prompt" the Foundry wizard starts from).

- No-tool agents (02, 06) -> dspy.ChainOfThought(signature)
- Tool-using agents (everyone else) -> dspy.ReAct(signature, tools=[...]) wired to the deterministic
  mocks in mock_tools.py by exact tool name

MCP tools are never wired here — see agent_loader.py's module docstring for why, and
AgentSpec.dspy_optimization_scope_note for the per-agent caveat text carried into every result file.
"""
from __future__ import annotations

import dspy

from agent_loader import AgentSpec
from mock_tools import get_mock


def build_signature(instructions_text: str) -> type:
    return dspy.Signature("query -> response: str").with_instructions(instructions_text)


def _make_dspy_tool(name: str, description: str, parameters: dict) -> dspy.Tool:
    fn = get_mock(name)
    props = (parameters or {}).get("properties", {})
    py_type_map = {"string": str, "number": float, "integer": int, "boolean": bool}
    arg_types = {k: py_type_map.get(v.get("type", "string"), str) for k, v in props.items()}
    arg_desc = {k: v.get("description", "") for k, v in props.items()}
    return dspy.Tool(fn, name=name, desc=description, arg_types=arg_types or None, arg_desc=arg_desc or None)


def build_module(agent_spec: AgentSpec) -> dspy.Module:
    signature = build_signature(agent_spec.baseline_instructions)
    function_tools = agent_spec.function_tools
    if function_tools:
        tools = [_make_dspy_tool(t.name, t.description, t.parameters) for t in function_tools]
        return dspy.ReAct(signature, tools=tools, max_iters=6)
    return dspy.ChainOfThought(signature)


def get_program_instructions(compiled_module: dspy.Module) -> str:
    """Extract the (possibly MIPROv2-rewritten) instructions text from a compiled module,
    independent of whether it's a ReAct or Predict/ChainOfThought under the hood."""
    predictor = None
    if hasattr(compiled_module, "react"):
        predictor = compiled_module.react
    elif hasattr(compiled_module, "predict"):
        predictor = compiled_module.predict
    else:
        # Fall back to the first dspy.Predict-like sub-module found.
        for _, sub in compiled_module.named_predictors() if hasattr(compiled_module, "named_predictors") else []:
            predictor = sub
            break
    if predictor is None:
        raise RuntimeError("Could not locate a predictor on the compiled module to read instructions from.")
    return predictor.signature.instructions
