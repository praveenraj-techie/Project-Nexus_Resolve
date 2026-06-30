import pytest

from app.models import RemediationPlan
from app.policy import policy_check


def safe_plan(**overrides):
    payload = {
        "summary": "Adversarial safety check.",
        "target_resources": ["APP-WIN-042:C:\\App\\Logs"],
        "action_preview": "Mock PowerShell: inspect files with -WhatIf",
        "estimated_effect": "No real changes.",
        "safeguards": ["Mock-only execution.", "Human approval required."],
        "approval_required": True,
        "approval_granted": True,
        "uses_dry_run": True,
        "mock_only": True,
        "validation_steps": ["Validate scenario metrics."],
    }
    payload.update(overrides)
    return RemediationPlan(**payload)


@pytest.mark.parametrize(
    "target",
    [
        "C:\\Windows\\System32",
        "C:/Users/demo",
        "/etc/passwd",
        "Domain Admins",
    ],
)
def test_protected_resources_are_blocked(target):
    checks = policy_check(
        safe_plan(target_resources=[target]),
        enforce_approval=True,
    )

    assert any(
        check.name == "Target scope" and check.status == "blocked"
        for check in checks
    )


@pytest.mark.parametrize(
    "action",
    [
        "Invoke-Command -ComputerName prod01 -ScriptBlock { Remove-Item C:\\Temp }",
        "psexec \\\\prod01 cmd",
        "aws ec2 terminate-instances --instance-ids i-123",
        "Remove-Item -Recurse -Force C:\\",
    ],
)
def test_destructive_real_execution_markers_are_blocked(action):
    checks = policy_check(
        safe_plan(action_preview=action, mock_only=False, uses_dry_run=False),
        enforce_approval=True,
    )

    assert any(
        check.name == "Mock-only execution" and check.status == "blocked"
        for check in checks
    )


def test_missing_human_approval_is_blocked_at_execution_gate():
    checks = policy_check(
        safe_plan(approval_granted=False),
        enforce_approval=True,
    )

    assert any(
        check.name == "Human approval" and check.status == "blocked"
        for check in checks
    )


def test_missing_validation_steps_are_blocked():
    checks = policy_check(
        safe_plan(validation_steps=[]),
        enforce_approval=True,
    )

    assert any(
        check.name == "Validation steps" and check.status == "blocked"
        for check in checks
    )
