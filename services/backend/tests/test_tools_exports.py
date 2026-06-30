from app.models import RemediationPlan
from app.tools import get_default_incident, get_initial_state, mock_execute, policy_check


def test_tools_module_exposes_policy_check_and_mock_execute():
    plan = RemediationPlan(
        summary="Safe app log cleanup.",
        target_resources=["APP-WIN-042:C:\\App\\Logs"],
        action_preview="Mock PowerShell cleanup with -WhatIf.",
        estimated_effect="Reclaim 36 GB.",
        safeguards=["Mock-only execution.", "Human approval required."],
        approval_required=True,
        approval_granted=True,
        uses_dry_run=True,
        mock_only=True,
        validation_steps=["Check C: free space."],
    )

    checks = policy_check(plan, enforce_approval=True)
    after = mock_execute(plan, get_initial_state(get_default_incident()))

    assert all(check.status == "pass" for check in checks)
    assert after["metrics"][0]["value"] == "44 GB"
