"""
agent_loader.py — loads one agent from the foundry-prompt-agent-optimizer-baselines pack into a
plain-Python AgentSpec, for use by the DSPy MIPROv2 baseline.

Single-sourced from the same on-disk files the Foundry track reads (agent.yaml, instructions.md,
tools.json, dataset/optimize.jsonl, dataset/holdout.jsonl, expected/expectations.json) so both
tracks are scored against literally the same contract — that comparability is the whole point of
this baseline (see ../../README.md "why an open baseline" and CHANGELOG.md finding #3).

LIMITATION (documented, not hidden): for the two MCP agents (04-hr-policy-mcp,
07-incident-response-mcp), this loader only exposes the *function-calling* tools. There is no real
MCP server in this repo to call, and simulating one well enough to be a fair test of retrieval
behaviour is out of scope for an open baseline. DSPy is therefore evaluated on those two agents on
an INSTRUCTIONS-ONLY basis, with the MCP-dependent agent_tests/rubric rows excluded from its metric
(see metric.py). Report DSPy results for 04/07 with that caveat attached — never as a like-for-like
MCP comparison against Foundry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PACK_ROOT = Path(__file__).resolve().parents[2]  # .../prompt-agent-optimizer-baselines


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    is_mcp: bool = False


@dataclass
class DatasetRow:
    id: str
    query: str
    ground_truth: str
    tags: list[str] = field(default_factory=list)


@dataclass
class AgentSpec:
    agent_id: str
    name: str
    baseline_instructions: str
    tools: list[ToolSpec]
    uses_mcp: bool
    optimize_rows: list[DatasetRow]
    holdout_rows: list[DatasetRow]
    expectations: dict

    @property
    def function_tools(self) -> list[ToolSpec]:
        return [t for t in self.tools if not t.is_mcp]

    @property
    def dspy_optimization_scope_note(self) -> str:
        if self.uses_mcp:
            return (
                f"{self.agent_id} declares MCP tools that this open baseline cannot call for real; "
                "DSPy optimizes instructions + the function-calling tools only. MCP-retrieval-policy "
                "rows are excluded from this baseline's metric — see agent_loader.py docstring."
            )
        return f"{self.agent_id}: full comparability with the Foundry track (no MCP dependency)."


def _load_tools(agent_dir: Path, agent_yaml: dict) -> list[ToolSpec]:
    tools_field = agent_yaml.get("tools")
    if not tools_field:
        return []
    tools_path = agent_dir / tools_field if isinstance(tools_field, str) else None
    if tools_path is None or not tools_path.exists():
        return []
    raw = json.loads(tools_path.read_text())
    out: list[ToolSpec] = []
    for entry in raw:
        if entry.get("type") == "mcp":
            for t in entry.get("tools", []):
                out.append(ToolSpec(name=t["name"], description=t["description"], parameters={}, is_mcp=True))
        elif entry.get("type") == "function":
            fn = entry["function"]
            out.append(ToolSpec(name=fn["name"], description=fn["description"], parameters=fn.get("parameters", {}), is_mcp=False))
    return out


def _load_rows(path: Path) -> list[DatasetRow]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        rows.append(DatasetRow(id=obj["id"], query=obj["query"], ground_truth=obj["ground_truth"], tags=obj.get("tags", [])))
    return rows


def load_agent(agent_id: str, pack_root: Path = PACK_ROOT) -> AgentSpec:
    agent_dir = pack_root / agent_id
    if not agent_dir.exists():
        raise FileNotFoundError(f"No agent directory at {agent_dir}")

    agent_yaml = yaml.safe_load((agent_dir / "agent.yaml").read_text())
    instructions = (agent_dir / "instructions.md").read_text().strip()
    tools = _load_tools(agent_dir, agent_yaml)
    optimize_rows = _load_rows(agent_dir / "dataset" / "optimize.jsonl")
    holdout_rows = _load_rows(agent_dir / "dataset" / "holdout.jsonl")
    expectations = json.loads((agent_dir / "expected" / "expectations.json").read_text())

    return AgentSpec(
        agent_id=agent_id,
        name=agent_yaml["name"],
        baseline_instructions=instructions,
        tools=tools,
        uses_mcp=bool(agent_yaml.get("metadata", {}).get("uses_mcp", False)),
        optimize_rows=optimize_rows,
        holdout_rows=holdout_rows,
        expectations=expectations,
    )


ALL_AGENT_IDS = [
    "01-travel-approval-strict",
    "02-support-triage-messy",
    "03-invoice-extractor-schema",
    "04-hr-policy-mcp",
    "05-clinical-triage-safety",
    "06-sales-brief-underspecified",
    "07-incident-response-mcp",
    "08-helpdesk-reset-multiturn",
    "09-code-review-assistant-strict",
    "10-expense-claim-boundary",
]


if __name__ == "__main__":
    for aid in ALL_AGENT_IDS:
        spec = load_agent(aid)
        print(f"{aid}: {len(spec.optimize_rows)} optimize / {len(spec.holdout_rows)} holdout rows, "
              f"{len(spec.function_tools)} function tools, mcp={spec.uses_mcp}")
