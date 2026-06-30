from __future__ import annotations

from .models import PolicyCheck, RemediationPlan


PROTECTED_RESOURCES = (
    "C:\\Windows",
    "C:\\Windows\\System32",
    "C:\\Program Files",
    "C:\\Users",
    "/etc",
    "/bin",
    "/usr/bin",
    "/var/lib",
    "Domain Admins",
)

REAL_EXECUTION_MARKERS = (
    "invoke-command",
    "enter-pssession",
    "psexec",
    "remove-item -recurse -force c:\\",
    "format-volume",
    "clear-disk",
    "terminate-instances",
    "delete-user",
    "delete restore point",
    "any-any allow",
)


def normalize_path(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").casefold()


def touches_protected_resource(resource: str) -> bool:
    normalized = normalize_path(resource)
    for protected in PROTECTED_RESOURCES:
        protected_normalized = normalize_path(protected)
        if normalized == protected_normalized or normalized.startswith(
            f"{protected_normalized}\\"
        ):
            return True
    return False


def has_destructive_real_execution(script: str) -> bool:
    lowered = script.casefold()
    return any(marker in lowered for marker in REAL_EXECUTION_MARKERS)


def policy_check(
    plan: RemediationPlan, *, enforce_approval: bool = False
) -> list[PolicyCheck]:
    checks: list[PolicyCheck] = []

    protected_hits = [
        resource
        for resource in plan.target_resources
        if touches_protected_resource(resource)
    ]
    checks.append(
        PolicyCheck(
            name="Target scope",
            status="blocked" if protected_hits else "pass",
            message=(
                "Plan touches protected resources and cannot continue."
                if protected_hits
                else "Targets are limited to approved scenario resources."
            ),
            evidence={
                "protected_hits": protected_hits,
                "target_resources": plan.target_resources,
            },
        )
    )

    checks.append(
        PolicyCheck(
            name="Safeguards",
            status="pass" if plan.safeguards else "blocked",
            message=(
                "Plan includes explicit safety safeguards."
                if plan.safeguards
                else "Plan lacks explicit safety safeguards."
            ),
            evidence={"safeguards": plan.safeguards},
        )
    )

    action = plan.action_preview.casefold()
    has_dry_run = (
        "mock" in action
        or "dry-run" in action
        or "-whatif" in action
        or plan.uses_dry_run
    )
    checks.append(
        PolicyCheck(
            name="Dry-run guard",
            status="pass" if has_dry_run or plan.mock_only else "blocked",
            message=(
                "Plan uses a dry-run or mock-only action preview."
                if has_dry_run or plan.mock_only
                else "Plan lacks a dry-run guard and is blocked."
            ),
            evidence={"uses_dry_run": has_dry_run, "mock_only": plan.mock_only},
        )
    )

    if not plan.approval_required:
        approval_status = "blocked"
        approval_message = "Plan does not require human approval."
    elif enforce_approval and not plan.approval_granted:
        approval_status = "blocked"
        approval_message = "Human approval has not been granted."
    elif not plan.approval_granted:
        approval_status = "requires_approval"
        approval_message = "Human approval is required before remediation."
    else:
        approval_status = "pass"
        approval_message = "Human approval is recorded."
    checks.append(
        PolicyCheck(
            name="Human approval",
            status=approval_status,
            message=approval_message,
            evidence={
                "approval_required": plan.approval_required,
                "approval_granted": plan.approval_granted,
            },
        )
    )

    checks.append(
        PolicyCheck(
            name="Validation steps",
            status="pass" if plan.validation_steps else "blocked",
            message=(
                "Plan includes post-remediation validation."
                if plan.validation_steps
                else "Plan lacks validation steps."
            ),
            evidence={"validation_steps": plan.validation_steps},
        )
    )

    real_execution_detected = has_destructive_real_execution(plan.action_preview)
    checks.append(
        PolicyCheck(
            name="Mock-only execution",
            status="pass" if plan.mock_only and not real_execution_detected else "blocked",
            message=(
                "Plan is constrained to mock execution."
                if plan.mock_only and not real_execution_detected
                else "Plan appears capable of real local-machine execution."
            ),
            evidence={
                "mock_only": plan.mock_only,
                "real_execution_detected": real_execution_detected,
            },
        )
    )

    return checks


def has_blocking_check(checks: list[PolicyCheck]) -> bool:
    return any(check.status == "blocked" for check in checks)
