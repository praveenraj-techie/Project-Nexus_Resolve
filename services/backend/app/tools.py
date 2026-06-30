from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import EvidenceItem, IncidentTicket, PolicyCheck, RemediationPlan
from .scenario_catalog import (
    DATA_ROOT,
    PROJECT_ROOT,
    get_scenario,
    incident_for_scenario,
    list_scenarios,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def get_default_incident() -> IncidentTicket:
    return incident_for_scenario("disk-space")


def get_incident_for_scenario(scenario_id: str) -> IncidentTicket:
    return incident_for_scenario(scenario_id)


def get_scenario_summaries() -> list[dict[str, str]]:
    return list_scenarios()


def get_initial_state(ticket: IncidentTicket | None = None) -> dict[str, Any]:
    scenario_id = ticket.scenario_id if ticket else "disk-space"
    scenario = get_scenario(scenario_id)
    state = deepcopy(scenario["initial_state"])
    state["scenario"] = scenario
    return state


def get_expected_after_state(ticket: IncidentTicket | None = None) -> dict[str, Any]:
    scenario_id = ticket.scenario_id if ticket else "disk-space"
    return deepcopy(get_scenario(scenario_id)["after_state"])


def retrieve_sop(ticket: IncidentTicket) -> EvidenceItem:
    scenario = get_scenario(ticket.scenario_id)
    sop = scenario["sop"]
    return EvidenceItem(
        id=sop["id"],
        type="sop",
        title=sop["title"],
        summary=sop["summary"],
        source=str((DATA_ROOT / "scenarios/catalog.json").relative_to(PROJECT_ROOT)),
        metadata={
            "ticket": ticket.incident_id,
            "scenario_id": ticket.scenario_id,
            "team": ticket.team,
            "content": sop["content"],
            "controls": sop["controls"],
        },
    )


def retrieve_similar_tickets(ticket: IncidentTicket) -> list[EvidenceItem]:
    scenario = get_scenario(ticket.scenario_id)
    source = DATA_ROOT / "scenarios/catalog.json"
    evidence: list[EvidenceItem] = []
    for row in scenario["history"]:
        evidence.append(
            EvidenceItem(
                id=row["ticket_id"],
                type="history",
                title=row["summary"],
                summary=row["notes"],
                source=str(source.relative_to(PROJECT_ROOT)),
                metadata={
                    **row,
                    "matched_ci": row.get("ci") == ticket.affected_ci,
                },
            )
        )
    return evidence


def estimate_reclaimable_space(state: dict[str, Any]) -> float:
    for metric in state.get("metrics", []):
        value = str(metric.get("value", ""))
        if value.endswith(" GB"):
            try:
                return float(value.removesuffix(" GB"))
            except ValueError:
                continue
    return 0.0


def validate_result(before: dict[str, Any], after: dict[str, Any]) -> PolicyCheck:
    validation = after.get("validation") or before.get("validation")
    if not validation:
        return PolicyCheck(
            name="Scenario validation",
            status="blocked",
            message="Scenario did not provide validation evidence.",
            evidence={},
        )
    return PolicyCheck.model_validate(validation)


def policy_check(
    plan: RemediationPlan, *, enforce_approval: bool = False
) -> list[PolicyCheck]:
    from .policy import policy_check as run_policy_check

    return run_policy_check(plan, enforce_approval=enforce_approval)


def mock_execute(plan: RemediationPlan, state: dict[str, Any]) -> dict[str, Any]:
    from .mock_execute import mock_execute as run_mock_execute

    return run_mock_execute(plan, state)
