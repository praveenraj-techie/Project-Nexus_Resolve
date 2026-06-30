from app.models import RemediationPlan
from app.policy import policy_check


def test_unsafe_action_is_blocked_without_safeguards_and_dry_run():
    plan = RemediationPlan(
        summary="Unsafe direct remediation.",
        target_resources=["APP-WIN-042:C:\\App\\Logs"],
        action_preview="Get-ChildItem 'C:\\App\\Logs' -Recurse | Remove-Item",
        estimated_effect="Unknown.",
        safeguards=[],
        approval_required=True,
        uses_dry_run=False,
        mock_only=False,
        validation_steps=[],
    )

    checks = policy_check(plan, enforce_approval=True)
    blocked = {check.name for check in checks if check.status == "blocked"}

    assert "Safeguards" in blocked
    assert "Dry-run guard" in blocked
    assert "Validation steps" in blocked
    assert "Mock-only execution" in blocked


def test_protected_resource_is_blocked():
    plan = RemediationPlan(
        summary="Unsafe protected resource.",
        target_resources=["C:\\Windows\\System32"],
        action_preview="Mock action with -WhatIf",
        estimated_effect="Unknown.",
        safeguards=["Mock-only execution."],
        approval_required=True,
        approval_granted=True,
        uses_dry_run=True,
        mock_only=True,
        validation_steps=["Check free space."],
    )

    checks = policy_check(plan, enforce_approval=True)

    assert any(
        check.name == "Target scope" and check.status == "blocked"
        for check in checks
    )
