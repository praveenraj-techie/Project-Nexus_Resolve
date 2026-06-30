from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import RemediationPlan
from .policy import policy_check, has_blocking_check


def mock_execute(plan: RemediationPlan, state: dict[str, Any]) -> dict[str, Any]:
    checks = policy_check(plan, enforce_approval=True)
    if has_blocking_check(checks):
        blocked = ", ".join(check.name for check in checks if check.status == "blocked")
        raise ValueError(f"Policy blocked mock execution: {blocked}")

    after = deepcopy(state.get("after_state", {}))
    if not after:
        raise ValueError("Scenario after-state is unavailable for mock execution.")
    after["execution_guard"] = {
        "mock_only": True,
        "source_state": state.get("snapshot_id"),
        "approved": plan.approval_granted,
    }
    return after
