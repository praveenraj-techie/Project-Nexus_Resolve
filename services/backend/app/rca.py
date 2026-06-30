from __future__ import annotations

from typing import Any

from .models import RcaSummary


def fallback_rca(before: dict[str, Any], after: dict[str, Any]) -> RcaSummary:
    rca = after.get("rca") or before.get("rca")
    if rca:
        return RcaSummary.model_validate(rca)

    return RcaSummary(
        root_cause="Synthetic scenario root cause was not available.",
        actions_taken=["Retrieved SOP.", "Captured approval.", "Validated mock outcome."],
        validation=after.get("summary", "Scenario validation completed."),
        business_impact="Synthetic workflow completed without real side effects.",
        follow_up=["Add scenario RCA details."],
        metrics={"Audit Completeness": "100%"},
    )
