from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import IncidentTicket


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"
CATALOG_PATH = DATA_ROOT / "scenarios" / "catalog.json"
DEFAULT_SCENARIO_ID = "disk-space"


def _load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def list_scenarios() -> list[dict[str, str]]:
    scenarios = []
    for item in _load_catalog():
        incident = item["incident"]
        scenarios.append(
            {
                "scenario_id": item["scenario_id"],
                "team": item["team"],
                "alert_type": item["alert_type"],
                "incident_id": incident["incident_id"],
                "priority": incident["priority"],
                "title": incident["title"],
                "business_service": incident["business_service"],
                "affected_ci": incident["affected_ci"],
                "current_state": incident["current_state"],
                "requested_outcome": incident["requested_outcome"],
            }
        )
    return scenarios


def get_scenario(scenario_id: str = DEFAULT_SCENARIO_ID) -> dict[str, Any]:
    for item in _load_catalog():
        if item["scenario_id"] == scenario_id:
            return deepcopy(item)
    raise KeyError(f"Unknown scenario_id: {scenario_id}")


def get_default_scenario() -> dict[str, Any]:
    return get_scenario(DEFAULT_SCENARIO_ID)


def incident_for_scenario(scenario_id: str = DEFAULT_SCENARIO_ID) -> IncidentTicket:
    return IncidentTicket.model_validate(get_scenario(scenario_id)["incident"])


def get_replay_path(scenario_id: str) -> Path:
    scenario = get_scenario(scenario_id)
    return DATA_ROOT / "replay" / scenario["replay_file"]
