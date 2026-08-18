"""
mock_tools.py — deterministic, stateless mock implementations of each agent's function-calling
tools, so a dspy.ReAct module can actually exercise tool calls during MIPROv2 optimization and
holdout evaluation.

Design intent: these mocks are deliberately NOT a business-logic simulation. Their only job is to
let the metric (metric.py) observe *whether and how* the program called a tool, which is what
`agent_tests[].tool_call.policy` (required/forbidden/optional) checks. Returned values are small,
plausible, clearly-synthetic canned data — never values that could be mistaken for a real policy
figure, so a MIPROv2-proposed instruction can't accidentally "learn" a fabricated fact from a mock
tool response and get rewarded for repeating it (that would corrupt the must_not_appear checks in
metric.py, e.g. 04's MN-02 baked-in-policy-value guard).

Every mock call is logged to a thread-local call log that the metric reads after each program
invocation to check tool_call policy compliance — this is how "did it call page_oncall" is verified
without a real paging system behind it.
"""
from __future__ import annotations

import threading
from typing import Any

_call_log = threading.local()


def reset_call_log() -> None:
    _call_log.calls = []


def get_call_log() -> list[str]:
    return getattr(_call_log, "calls", [])


def _log(name: str) -> None:
    if not hasattr(_call_log, "calls"):
        _call_log.calls = []
    _call_log.calls.append(name)


# --- Per-agent mock tool functions -----------------------------------------------------------
# Each function's name matches the tool name in the agent's tools.json exactly, so dspy_program.py
# can wire them up by name without a manual mapping table per agent.

def lookup_travel_policy() -> dict:
    _log("lookup_travel_policy")
    return {"auto_approve_max": 1500, "manager_max": 3000, "director_max": 7500,
            "lodging_domestic": 250, "lodging_intl": 400, "business_class_hours": 6}


def check_department_budget(department: str) -> dict:
    _log("check_department_budget")
    return {"department": department, "remaining_budget_usd": 5000}


def get_flight_alternatives(destination: str, max_price: float | None = None) -> dict:
    _log("get_flight_alternatives")
    return {"destination": destination, "alternatives": [{"airline": "Mock Air", "price": (max_price or 500) * 0.8}]}


def check_coverage(member_id: str, service_type: str) -> dict:
    _log("check_coverage")
    return {"member_id": member_id, "service_type": service_type, "covered": True, "copay_usd": 20}


def find_appointment(service_type: str, earliest: str | None = None) -> dict:
    _log("find_appointment")
    return {"service_type": service_type, "slot": "next available synthetic slot"}


def lookup_supplier(name: str, country_code: str | None = None) -> dict:
    _log("lookup_supplier")
    return {"name": name, "country_code": country_code or "XX", "default_currency": "USD"}


def validate_vat_number(vat_number: str) -> dict:
    _log("validate_vat_number")
    return {"vat_number": vat_number, "format_valid": True}


def get_employee_context(field: str) -> dict:
    _log("get_employee_context")
    return {"field": field, "value": "synthetic-context"}


def raise_hrbp_ticket(topic: str, urgency: str = "normal") -> dict:
    _log("raise_hrbp_ticket")
    return {"ticket_id": "MOCK-TICKET-0001", "topic": topic, "urgency": urgency}


def page_oncall(team: str, severity: str) -> dict:
    _log("page_oncall")
    return {"team": team, "severity": severity, "paged": True}


def create_incident_ticket(title: str, severity: str) -> dict:
    _log("create_incident_ticket")
    return {"ticket_id": "MOCK-INC-0001", "title": title, "severity": severity}


def verify_identity(employee_id: str, verification_code: str) -> dict:
    _log("verify_identity")
    # Deterministic: codes ending in an even digit "succeed" so both branches are reachable
    # across a dataset without any real secret material.
    ok = bool(verification_code) and verification_code[-1] in "02468"
    return {"employee_id": employee_id, "verified": ok}


def reset_password(employee_id: str) -> dict:
    _log("reset_password")
    return {"employee_id": employee_id, "temporary_password": "MOCK-TEMP-PW-0001"}


def fetch_diff(pr_id: str) -> dict:
    _log("fetch_diff")
    return {"pr_id": pr_id, "files": [{"path": "mock_file.py", "added_lines": ["x = 1"]}]}


def run_lint_check(pr_id: str) -> dict:
    _log("run_lint_check")
    return {"pr_id": pr_id, "findings": []}


def post_review_comment(pr_id: str, file: str, line: int, comment: str) -> dict:
    _log("post_review_comment")
    return {"pr_id": pr_id, "file": file, "line": line, "posted": True}


def lookup_exchange_rate(from_currency: str, to_currency: str) -> dict:
    _log("lookup_exchange_rate")
    return {"from_currency": from_currency, "to_currency": to_currency, "rate": 1.10}


def submit_expense_claim(amount_usd: float, category: str, receipt_attached: bool) -> dict:
    _log("submit_expense_claim")
    return {"claim_id": "MOCK-EXP-0001", "amount_usd": amount_usd, "category": category,
             "receipt_attached": receipt_attached, "status": "pending_review"}


MOCKS: dict[str, Any] = {
    "lookup_travel_policy": lookup_travel_policy,
    "check_department_budget": check_department_budget,
    "get_flight_alternatives": get_flight_alternatives,
    "check_coverage": check_coverage,
    "find_appointment": find_appointment,
    "lookup_supplier": lookup_supplier,
    "validate_vat_number": validate_vat_number,
    "get_employee_context": get_employee_context,
    "raise_hrbp_ticket": raise_hrbp_ticket,
    "page_oncall": page_oncall,
    "create_incident_ticket": create_incident_ticket,
    "verify_identity": verify_identity,
    "reset_password": reset_password,
    "fetch_diff": fetch_diff,
    "run_lint_check": run_lint_check,
    "post_review_comment": post_review_comment,
    "lookup_exchange_rate": lookup_exchange_rate,
    "submit_expense_claim": submit_expense_claim,
}


def get_mock(tool_name: str):
    if tool_name not in MOCKS:
        raise KeyError(f"No mock implementation registered for tool '{tool_name}' — add one to mock_tools.py")
    return MOCKS[tool_name]
