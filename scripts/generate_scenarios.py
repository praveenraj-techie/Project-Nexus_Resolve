from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
CATALOG_PATH = DATA_ROOT / "scenarios" / "catalog.json"
REPLAY_ROOT = DATA_ROOT / "replay"
BASE_TIME = datetime(2026, 6, 25, 4, 45, tzinfo=timezone.utc)


def metric(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value}


def history(
    scenario_id: str,
    prefix: str,
    ci: str,
    safe: list[tuple[str, str]],
    unsafe: tuple[str, str],
    escalation: tuple[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (summary, notes) in enumerate(safe, start=1):
        rows.append(
            {
                "ticket_id": f"HIST-{prefix}-2026-00{index}",
                "scenario_id": scenario_id,
                "ci": ci,
                "priority": "P4",
                "summary": summary,
                "outcome": "resolved",
                "safe": True,
                "notes": notes,
            }
        )
    rows.append(
        {
            "ticket_id": f"HIST-{prefix}-2026-009",
            "scenario_id": scenario_id,
            "ci": ci,
            "priority": "P3",
            "summary": unsafe[0],
            "outcome": "caused follow-up incident",
            "safe": False,
            "notes": unsafe[1],
        }
    )
    rows.append(
        {
            "ticket_id": f"HIST-{prefix}-2026-010",
            "scenario_id": scenario_id,
            "ci": ci,
            "priority": "P3",
            "summary": escalation[0],
            "outcome": "escalated",
            "safe": True,
            "notes": escalation[1],
        }
    )
    return rows


def scenario(
    *,
    scenario_id: str,
    team: str,
    alert_type: str,
    incident_id: str,
    priority: str,
    title: str,
    service: str,
    ci: str,
    current_state: str,
    requested_outcome: str,
    sop_id: str,
    sop_title: str,
    sop_summary: str,
    controls: list[str],
    plan_summary: str,
    target_resources: list[str],
    action_preview: str,
    estimated_effect: str,
    validation_steps: list[str],
    escalation_condition: str,
    initial_metrics: list[dict[str, str]],
    after_metrics: list[dict[str, str]],
    history_rows: list[dict[str, Any]],
    unsafe_message: str,
    execution_message: str,
    validation_message: str,
    rca_root_cause: str,
    rca_actions: list[str],
    rca_follow_up: list[str],
    mttr_minutes: int,
    replay_outcome: str = "success",
    rejection_message: str | None = None,
) -> dict[str, Any]:
    unsafe_ids = [row["ticket_id"] for row in history_rows if not row["safe"]]
    escalation_ids = [
        row["ticket_id"] for row in history_rows if row["outcome"] == "escalated"
    ]
    safe_count = len(history_rows) - len(unsafe_ids) - len(escalation_ids)
    plan = {
        "summary": plan_summary,
        "target_resources": target_resources,
        "action_preview": action_preview,
        "estimated_effect": estimated_effect,
        "safeguards": [
            "Mock-only execution in this demo.",
            "Human approval is required before remediation.",
            "SOP controls override unsafe historical precedent.",
            "Post-remediation validation is mandatory.",
        ],
        "approval_required": True,
        "approval_granted": False,
        "uses_dry_run": True,
        "mock_only": True,
        "validation_steps": validation_steps,
        "escalation_condition": escalation_condition,
    }
    validation = {
        "name": "Scenario validation",
        "status": "pass",
        "message": validation_message,
        "evidence": {"before": initial_metrics, "after": after_metrics},
    }
    execution = {
        "title": "Mock remediation executed",
        "message": execution_message,
        "payload": {"mock_only": True, "metrics": after_metrics},
    }
    rca = {
        "root_cause": rca_root_cause,
        "actions_taken": rca_actions,
        "validation": validation_message,
        "business_impact": f"{service} remained protected during the synthetic workflow.",
        "follow_up": rca_follow_up,
        "metrics": {
            "MTTR Estimate": f"{mttr_minutes} min",
            "Manual Steps Avoided": "6",
            "Audit Completeness": "100%",
        },
    }
    evidence_summary = {
        "outcome": f"Proceed with SOP-governed mock remediation for {alert_type}.",
        "sop_controls": controls,
        "safe_precedent_count": safe_count,
        "unsafe_precedent_ids": unsafe_ids,
        "escalation_precedent_ids": escalation_ids,
        "governance_note": (
            f"SOP beats history: {unsafe_ids[0]} is visible as a warning, "
            "not copied into the remediation plan."
        ),
    }
    after_state = {
        "snapshot_id": f"{scenario_id}-after",
        "scenario_id": scenario_id,
        "summary": validation_message,
        "metrics": after_metrics,
        "validation": validation,
        "execution": execution,
        "rca": rca,
    }
    initial_state = {
        "snapshot_id": f"{scenario_id}-before",
        "scenario_id": scenario_id,
        "summary": current_state,
        "metrics": initial_metrics,
        "plan_template": plan,
        "evidence_summary": evidence_summary,
        "validation": validation,
        "execution": execution,
        "rca": rca,
        "after_state": after_state,
    }
    return {
        "scenario_id": scenario_id,
        "team": team,
        "alert_type": alert_type,
        "replay_file": f"{scenario_id}.events.jsonl",
        "incident": {
            "scenario_id": scenario_id,
            "team": team,
            "incident_id": incident_id,
            "priority": priority,
            "title": title,
            "business_service": service,
            "affected_ci": ci,
            "environment": "synthetic-hcl-managed-infra",
            "symptoms": [current_state],
            "metric_snapshot": {
                "current_state": current_state,
                "team": team,
                "alert_type": alert_type,
            },
            "current_state": current_state,
            "requested_outcome": requested_outcome,
        },
        "sop": {
            "id": sop_id,
            "title": sop_title,
            "summary": sop_summary,
            "controls": controls,
            "content": "\n".join([f"# {sop_id}: {sop_title}", "", sop_summary, "", *controls]),
        },
        "history": history_rows,
        "unsafe_message": unsafe_message,
        "initial_state": initial_state,
        "after_state": after_state,
        "plan": plan,
        "validation": validation,
        "execution": execution,
        "rca": rca,
        "replay_outcome": replay_outcome,
        "rejection_message": rejection_message,
    }


def policy_checks(plan: dict[str, Any], approved: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "name": "Target scope",
            "status": "pass",
            "message": "Targets are limited to approved scenario resources.",
            "evidence": {"target_resources": plan["target_resources"]},
        },
        {
            "name": "Dry-run guard",
            "status": "pass",
            "message": "Plan uses a dry-run or mock-only action preview.",
            "evidence": {"uses_dry_run": plan["uses_dry_run"], "mock_only": plan["mock_only"]},
        },
        {
            "name": "Human approval",
            "status": "pass" if approved else "requires_approval",
            "message": (
                "Human approval is recorded."
                if approved
                else "Human approval is required before remediation."
            ),
            "evidence": {
                "approval_required": plan["approval_required"],
                "approval_granted": approved,
            },
        },
        {
            "name": "Validation steps",
            "status": "pass",
            "message": "Plan includes post-remediation validation.",
            "evidence": {"validation_steps": plan["validation_steps"]},
        },
        {
            "name": "Mock-only execution",
            "status": "pass",
            "message": "Plan is constrained to mock execution.",
            "evidence": {"mock_only": plan["mock_only"], "real_execution_detected": False},
        },
    ]


def replay_events(item: dict[str, Any]) -> list[dict[str, Any]]:
    run_id = f"replay-{item['scenario_id']}"
    incident = item["incident"]
    history_rows = item["history"]
    unsafe = [row for row in history_rows if not row["safe"]]
    escalations = [row for row in history_rows if row["outcome"] == "escalated"]
    plan = item["plan"]
    event_specs = [
        (
            "ticket.received",
            f"{item['team']} alert received",
            f"{incident['incident_id']} reports {item['alert_type']} on {incident['affected_ci']}.",
            {
                "scenario_id": item["scenario_id"],
                "team": item["team"],
                "alert_type": item["alert_type"],
                "incident_id": incident["incident_id"],
                "priority": incident["priority"],
                "ci": incident["affected_ci"],
                "service": incident["business_service"],
                "current_state": incident["current_state"],
                "requested_outcome": incident["requested_outcome"],
            },
        ),
        (
            "evidence.sop",
            "SOP retrieved",
            item["sop"]["summary"],
            {
                "sop_id": item["sop"]["id"],
                "title": item["sop"]["title"],
                "controls": item["sop"]["controls"],
            },
        ),
        (
            "evidence.history",
            "Historical tickets compared",
            f"{len(history_rows)} similar tickets found; {len(unsafe)} unsafe precedent flagged.",
            {
                "safe_examples": len(history_rows) - len(unsafe) - len(escalations),
                "unsafe_examples": len(unsafe),
                "escalations": len(escalations),
                "unsafe_ticket": unsafe[0]["ticket_id"],
                "items": history_rows,
            },
        ),
        (
            "policy.warning",
            "SOP beats history",
            item["unsafe_message"],
            {"blocked_precedent": unsafe[0]},
        ),
        (
            "evidence.summary",
            "Evidence summary structured",
            item["initial_state"]["evidence_summary"]["outcome"],
            item["initial_state"]["evidence_summary"],
        ),
        (
            "plan.generated",
            "Safe remediation plan generated",
            plan["summary"],
            plan,
        ),
        (
            "policy.checked",
            "Policy gate passed with approval hold",
            "Policy allows planning but requires human approval before mock execution.",
            {"checks": policy_checks(plan, approved=False)},
        ),
        (
            "approval.summary",
            "Approval package structured",
            f"Approve mock-only remediation for {item['alert_type']}.",
            {
                "decision_required": True,
                "operator_message": f"Approve mock-only remediation for {item['alert_type']}.",
                "expected_safe_effect": plan["estimated_effect"],
                "blocked_until_approved": True,
                "replay_side_effects_disabled": True,
            },
        ),
        (
            "approval.requested",
            "Human approval required",
            "Operator review is required before mock remediation can continue.",
            {"side_effects": "Replay mode disables approval side effects."},
        ),
    ]
    if item.get("replay_outcome") == "rejected":
        event_specs.append(
            (
                "approval.rejected",
                "Operator rejected remediation",
                item.get("rejection_message")
                or "The run ended safely with no mock state change.",
                {
                    "mock_execution_started": False,
                    "exception_case": True,
                    "scenario_id": item["scenario_id"],
                    "incident_id": incident["incident_id"],
                },
            )
        )
    else:
        event_specs.extend(
            [
                (
                    "execution.mocked",
                    item["execution"]["title"],
                    item["execution"]["message"],
                    item["execution"]["payload"],
                ),
                (
                    "validation.passed",
                    "Scenario validation passed",
                    item["validation"]["message"],
                    item["validation"],
                ),
                (
                    "rca.generated",
                    "RCA and audit evidence generated",
                    item["rca"]["root_cause"],
                    item["rca"],
                ),
                (
                    "closure.requested",
                    "Closure decision required",
                    "Remediation is validated. Operator can close the incident now or keep it under observation before closure.",
                    {
                        "incident_id": incident["incident_id"],
                        "options": [
                            {
                                "id": "close",
                                "label": "Approve closure",
                                "message": "Close the incident with RCA and audit evidence attached.",
                            },
                            {
                                "id": "observe",
                                "label": "Observe first",
                                "message": "Keep the incident under observation, recheck metrics, then close.",
                            },
                        ],
                    },
                ),
                (
                    "incident.closed",
                    "Incident closed",
                    f"{incident['incident_id']} was closed with RCA, evidence, and validation attached.",
                    {
                        "incident_id": incident["incident_id"],
                        "closure_code": "Resolved by approved mock remediation",
                        "final_status": "closed",
                    },
                ),
            ]
        )
    events = []
    for index, (event_type, title, message, payload) in enumerate(event_specs, start=1):
        events.append(
            {
                "run_id": run_id,
                "sequence": index,
                "timestamp": (BASE_TIME + timedelta(seconds=(index - 1) * 4)).isoformat().replace(
                    "+00:00", "Z"
                ),
                "type": event_type,
                "title": title,
                "message": message,
                "payload": payload,
            }
        )
    return events


def build_catalog() -> list[dict[str, Any]]:
    return [
        scenario(
            scenario_id="disk-space",
            team="Windows Infra",
            alert_type="Disk utilization high",
            incident_id="INC-2026-00421",
            priority="P4",
            title="C: drive utilization is above threshold",
            service="Internal Claims Portal",
            ci="APP-WIN-042",
            current_state="C: drive is 96% used with 8 GB free.",
            requested_outcome="Reclaim space with SOP-approved cleanup.",
            sop_id="SOP-WIN-DISK-001",
            sop_title="Windows Application Log Disk Remediation",
            sop_summary="Delete only old application logs, avoid protected paths, require approval, and validate free space.",
            controls=[
                "Delete only application logs older than 7 days.",
                "Never touch protected paths or active logs.",
                "Require human approval.",
                "Validate free space after remediation.",
            ],
            plan_summary="Clean approved application logs older than 7 days from C:\\App\\Logs using a mock-only flow.",
            target_resources=["APP-WIN-042:C:\\App\\Logs"],
            action_preview="Mock PowerShell: Get-ChildItem 'C:\\App\\Logs' -File -Recurse | Where-Object age > 7 days | Remove-Item -WhatIf",
            estimated_effect="Reclaim 36 GB; C: free space improves from 8 GB to 44 GB.",
            validation_steps=[
                "Compare C: free GB before and after mock execution.",
                "Confirm free space is at least 15%.",
                "Confirm no active logs or protected paths were touched.",
            ],
            escalation_condition="Escalate if C: free space remains below 15%.",
            initial_metrics=[
                metric("Before Free", "8 GB"),
                metric("Used", "96%"),
                metric("Old Logs", "36 GB"),
            ],
            after_metrics=[
                metric("After Free", "44 GB"),
                metric("Used", "78%"),
                metric("Reclaimed", "36 GB"),
            ],
            history_rows=history(
                "disk-space",
                "DISK",
                "APP-WIN-042",
                [
                    ("Archived app logs older than 14 days; reclaimed 18 GB.", "Approval captured."),
                    ("Removed rotated traces older than 10 days.", "Validation passed."),
                    ("Cleaned compressed logs after peer review.", "No protected paths touched."),
                ],
                (
                    "Engineer deleted all logs including active files.",
                    "Unsafe precedent: no age filter and active logs were removed.",
                ),
                (
                    "Approved cleanup reclaimed only 4 GB.",
                    "Escalated for volume expansion after threshold remained breached.",
                ),
            ),
            unsafe_message="Unsafe history deleted active logs, but SOP requires age-filtered log cleanup only.",
            execution_message="Validated mock cleanup reclaimed 36 GB and did not touch active logs or protected paths.",
            validation_message="C: drive improved from 96% used to 78% used, with 44 GB free.",
            rca_root_cause="Application log retention exceeded expected synthetic volume.",
            rca_actions=[
                "Retrieved SOP-WIN-DISK-001.",
                "Excluded unsafe historical precedent that deleted active logs.",
                "Generated age-filtered mock cleanup.",
                "Captured human approval.",
                "Validated disk free space.",
            ],
            rca_follow_up=[
                "Tune application log rotation.",
                "Add pre-checks for old log accumulation.",
            ],
            mttr_minutes=8,
        ),
        scenario(
            scenario_id="db-connection-pool",
            team="Database",
            alert_type="DB connection pool saturation",
            incident_id="INC-2026-00422",
            priority="P3",
            title="Payments API database pool near exhaustion",
            service="Payments API",
            ci="PAY-APP-DBPOOL-01",
            current_state="Active DB connections are 486 of 500; checkout latency is 2.8 seconds.",
            requested_outcome="Reduce connection pressure without restarting the database.",
            sop_id="SOP-DB-POOL-002",
            sop_title="Application Connection Pool Saturation",
            sop_summary="Stabilize the app tier first, preserve DB sessions, require approval, and validate pool recovery.",
            controls=[
                "Do not kill database sessions as the first action.",
                "Drain app workers before restart.",
                "Require approval for pool setting changes.",
                "Validate active connections and checkout latency.",
            ],
            plan_summary="Reduce Payments API pool pressure and restart the app pool in mock mode.",
            target_resources=["PAY-APP-DBPOOL-01", "Payments API app pool"],
            action_preview="Mock action: drain Payments API workers, lower burst pool from 160 to 100, restart app pool.",
            estimated_effect="Active DB connections reduce from 486 to 255 and checkout latency drops below 500 ms.",
            validation_steps=[
                "Check active DB connection count.",
                "Check app checkout latency.",
                "Confirm error rate remains below 1%.",
            ],
            escalation_condition="Escalate to DBA if connections remain above 350 after app-pool remediation.",
            initial_metrics=[
                metric("Connections", "486/500"),
                metric("Latency", "2.8 sec"),
                metric("Errors", "3.4%"),
            ],
            after_metrics=[
                metric("Connections", "255/500"),
                metric("Latency", "410 ms"),
                metric("Errors", "0.3%"),
            ],
            history_rows=history(
                "db-connection-pool",
                "DBPOOL",
                "PAY-APP-DBPOOL-01",
                [
                    ("Drained app workers and reset pool safely.", "DB restart avoided."),
                    ("Lowered app burst pool after approval.", "Connections recovered."),
                    ("Restarted app pool with connection validation.", "Latency returned to normal."),
                ],
                (
                    "Engineer killed active database sessions during pool saturation.",
                    "Unsafe precedent: user transactions failed after forced session termination.",
                ),
                (
                    "Pool reset did not recover because a code leak persisted.",
                    "Escalated to application engineering after validation failed.",
                ),
            ),
            unsafe_message="Unsafe history killed DB sessions; SOP requires app-tier pressure reduction first.",
            execution_message="Mock app-pool remediation reduced active database connections and preserved sessions.",
            validation_message="Connections dropped from 486 to 255 and checkout latency recovered to 410 ms.",
            rca_root_cause="Payments API worker burst settings exhausted the shared DB connection pool.",
            rca_actions=[
                "Retrieved DB pool SOP.",
                "Excluded unsafe session-kill precedent.",
                "Prepared app-tier pool reduction.",
                "Captured approval.",
                "Validated connection and latency recovery.",
            ],
            rca_follow_up=[
                "Tune max pool and worker settings.",
                "Add alerting for pool growth rate.",
            ],
            mttr_minutes=10,
        ),
        scenario(
            scenario_id="iam-admin-role",
            team="Security / IAM",
            alert_type="Suspicious admin role assignment",
            incident_id="INC-2026-00423",
            priority="P2",
            title="Unexpected privileged role assignment detected",
            service="Identity Governance",
            ci="IAM-TENANT-PRIMARY",
            current_state="Vendor account has Global Admin role outside approved change window.",
            requested_outcome="Disable the suspicious grant while preserving audit evidence.",
            sop_id="SOP-IAM-PRIV-003",
            sop_title="Privileged Role Assignment Containment",
            sop_summary="Preserve evidence, disable only the suspicious grant, require approval, and validate privilege removal.",
            controls=[
                "Preserve audit evidence before containment.",
                "Disable only the suspicious role grant.",
                "Do not delete user identity during initial containment.",
                "Require approval for privilege changes.",
            ],
            plan_summary="Disable the suspicious admin role grant in mock mode and preserve IAM evidence.",
            target_resources=["IAM-TENANT-PRIMARY:vendor-admin-role-grant"],
            action_preview="Mock action: export role assignment evidence, disable grant GRANT-4471, leave account intact.",
            estimated_effect="Privileged assignment is removed while evidence and account state are preserved.",
            validation_steps=[
                "Confirm grant GRANT-4471 is disabled.",
                "Confirm audit evidence export exists.",
                "Confirm no unrelated roles were changed.",
            ],
            escalation_condition="Escalate to security incident response if other privileged grants are discovered.",
            initial_metrics=[
                metric("Privileged Grants", "1 suspicious"),
                metric("Change Window", "Closed"),
                metric("Evidence", "Pending"),
            ],
            after_metrics=[
                metric("Privileged Grants", "0 suspicious"),
                metric("Evidence", "Captured"),
                metric("Blast Radius", "Contained"),
            ],
            history_rows=history(
                "iam-admin-role",
                "IAM",
                "IAM-TENANT-PRIMARY",
                [
                    ("Disabled suspicious grant after audit export.", "Evidence preserved."),
                    ("Removed temporary admin role after manager approval.", "No account deletion."),
                    ("Validated no lateral privileged assignments.", "SIEM evidence linked."),
                ],
                (
                    "Operator deleted the user before evidence export.",
                    "Unsafe precedent: audit chain was broken and ownership became unclear.",
                ),
                (
                    "Multiple privileged grants were found after initial containment.",
                    "Escalated to security incident response.",
                ),
            ),
            unsafe_message="Unsafe history deleted the account before evidence capture; SOP requires evidence preservation first.",
            execution_message="Mock containment disabled the suspicious role grant and preserved evidence.",
            validation_message="Privileged grant count moved from 1 suspicious assignment to 0 with evidence captured.",
            rca_root_cause="A temporary vendor privilege grant remained active outside the approved change window.",
            rca_actions=[
                "Retrieved privileged access SOP.",
                "Preserved synthetic audit evidence.",
                "Excluded unsafe account-deletion precedent.",
                "Captured approval.",
                "Validated privilege removal.",
            ],
            rca_follow_up=[
                "Shorten privileged grant expiry.",
                "Add approval correlation to IAM alerts.",
            ],
            mttr_minutes=7,
        ),
        scenario(
            scenario_id="vpn-packet-loss",
            team="Network",
            alert_type="VPN tunnel packet loss",
            incident_id="INC-2026-00424",
            priority="P3",
            title="Primary site VPN tunnel packet loss above threshold",
            service="Branch Connectivity",
            ci="VPN-HUB-SEA-01",
            current_state="Primary VPN tunnel packet loss is 18%; latency is 220 ms.",
            requested_outcome="Fail over to a healthy tunnel and validate connectivity.",
            sop_id="SOP-NET-VPN-004",
            sop_title="VPN Tunnel Loss Failover",
            sop_summary="Validate tunnel health, fail over safely, require approval, and confirm packet loss recovery.",
            controls=[
                "Confirm peer tunnel health before failover.",
                "Do not reset both tunnels simultaneously.",
                "Require approval for routing changes.",
                "Validate packet loss and latency after failover.",
            ],
            plan_summary="Fail over traffic from primary VPN tunnel to secondary tunnel in mock mode.",
            target_resources=["VPN-HUB-SEA-01:primary-tunnel", "VPN-HUB-SEA-02:secondary-tunnel"],
            action_preview="Mock action: shift branch route preference to secondary tunnel and monitor loss for 5 minutes.",
            estimated_effect="Packet loss reduces from 18% to 0.4%; latency returns below 70 ms.",
            validation_steps=[
                "Check secondary tunnel peer status.",
                "Validate packet loss below 1%.",
                "Validate latency below 80 ms.",
            ],
            escalation_condition="Escalate to carrier if both tunnels exceed 3% packet loss.",
            initial_metrics=[
                metric("Packet Loss", "18%"),
                metric("Latency", "220 ms"),
                metric("Healthy Tunnel", "Secondary"),
            ],
            after_metrics=[
                metric("Packet Loss", "0.4%"),
                metric("Latency", "62 ms"),
                metric("Tunnel", "Secondary"),
            ],
            history_rows=history(
                "vpn-packet-loss",
                "VPN",
                "VPN-HUB-SEA-01",
                [
                    ("Failed branch traffic to secondary tunnel.", "Loss recovered."),
                    ("Adjusted route preference after approval.", "Peer health confirmed."),
                    ("Validated latency after controlled failover.", "No routing loop."),
                ],
                (
                    "Engineer reset both VPN peers at the same time.",
                    "Unsafe precedent: branch connectivity was fully interrupted.",
                ),
                (
                    "Failover did not recover because carrier loss affected both paths.",
                    "Escalated to WAN provider.",
                ),
            ),
            unsafe_message="Unsafe history reset both tunnels; SOP requires confirming and using the healthy secondary path.",
            execution_message="Mock failover moved traffic to the secondary VPN tunnel and restored loss metrics.",
            validation_message="Packet loss recovered from 18% to 0.4% and latency recovered to 62 ms.",
            rca_root_cause="Primary VPN underlay path showed sustained packet loss.",
            rca_actions=[
                "Retrieved VPN failover SOP.",
                "Excluded unsafe dual-reset precedent.",
                "Prepared route-preference failover.",
                "Captured approval.",
                "Validated loss and latency recovery.",
            ],
            rca_follow_up=[
                "Open carrier ticket for primary path.",
                "Review tunnel SLA monitoring.",
            ],
            mttr_minutes=9,
        ),
        scenario(
            scenario_id="linux-high-load",
            team="Linux",
            alert_type="Linux server high CPU / load average",
            incident_id="INC-2026-00425",
            priority="P3",
            title="Linux report worker load average above threshold",
            service="Reporting Platform",
            ci="RPT-LNX-017",
            current_state="Load average is 18.6 on an 8-vCPU host; report-renderer is consuming 92% CPU.",
            requested_outcome="Stabilize load by restarting the approved service only.",
            sop_id="SOP-LNX-LOAD-005",
            sop_title="Linux High Load Service Stabilization",
            sop_summary="Identify top process, avoid host reboot first, restart only approved service, and validate load recovery.",
            controls=[
                "Identify top CPU process before action.",
                "Do not reboot host as first response.",
                "Restart only the approved service.",
                "Validate load average and service health.",
            ],
            plan_summary="Restart the approved report-renderer service in mock mode after top-process confirmation.",
            target_resources=["RPT-LNX-017:report-renderer.service"],
            action_preview="Mock action: capture top output, drain active jobs, restart report-renderer.service, validate health.",
            estimated_effect="Load average drops from 18.6 to 3.1 and CPU utilization drops below 45%.",
            validation_steps=[
                "Confirm report-renderer is the top CPU process.",
                "Validate service active state.",
                "Validate 5-minute load average below 6.",
            ],
            escalation_condition="Escalate to application team if load rebounds above 10 within 15 minutes.",
            initial_metrics=[
                metric("Load Avg", "18.6"),
                metric("CPU", "92%"),
                metric("Top Process", "report-renderer"),
            ],
            after_metrics=[
                metric("Load Avg", "3.1"),
                metric("CPU", "41%"),
                metric("Service", "Healthy"),
            ],
            history_rows=history(
                "linux-high-load",
                "LNX",
                "RPT-LNX-017",
                [
                    ("Restarted approved renderer service after top-process check.", "Load recovered."),
                    ("Drained jobs before service restart.", "No report loss."),
                    ("Validated load and service health after restart.", "SLO restored."),
                ],
                (
                    "Engineer rebooted host before identifying top process.",
                    "Unsafe precedent: unrelated batch jobs were interrupted.",
                ),
                (
                    "Service restart did not reduce load due to runaway job queue.",
                    "Escalated to application owners.",
                ),
            ),
            unsafe_message="Unsafe history rebooted the host first; SOP requires process identification and service-scoped action.",
            execution_message="Mock service restart reduced Linux load and preserved host availability.",
            validation_message="Load average recovered from 18.6 to 3.1 and service health is green.",
            rca_root_cause="Report renderer process saturated CPU after a stuck rendering batch.",
            rca_actions=[
                "Retrieved Linux high-load SOP.",
                "Confirmed top process.",
                "Excluded unsafe reboot precedent.",
                "Captured approval.",
                "Validated load recovery.",
            ],
            rca_follow_up=[
                "Add renderer job timeout.",
                "Alert on load growth rate.",
            ],
            mttr_minutes=11,
        ),
        scenario(
            scenario_id="firewall-rule-block",
            team="Firewall",
            alert_type="Firewall rule blocking application traffic",
            incident_id="INC-2026-00426",
            priority="P3",
            title="Recent firewall deny rule blocks application API traffic",
            service="Partner API Gateway",
            ci="FW-PERIM-02",
            current_state="TCP 8443 from app subnet to partner API VIP is denied after recent rule change.",
            requested_outcome="Restore approved traffic while preserving rule-change evidence.",
            sop_id="SOP-FW-RULE-006",
            sop_title="Firewall Rule Regression Remediation",
            sop_summary="Compare recent rules, avoid broad allows, require approval, and validate specific port reachability.",
            controls=[
                "Compare the failing flow against recent rule changes.",
                "Do not create broad any-any allows.",
                "Require approval before rule rollback.",
                "Validate only the approved source, destination, and port.",
            ],
            plan_summary="Roll back the specific deny rule in mock mode and validate TCP 8443 reachability.",
            target_resources=["FW-PERIM-02:rule CHG-7782", "AppSubnet -> PartnerAPI:8443"],
            action_preview="Mock action: disable deny rule CHG-7782 and stage approved allow for AppSubnet to PartnerAPI TCP 8443.",
            estimated_effect="Port reachability changes from denied to allowed for the approved flow only.",
            validation_steps=[
                "Confirm recent rule CHG-7782 matches failed flow.",
                "Validate TCP 8443 reachability.",
                "Confirm no broad source or destination was opened.",
            ],
            escalation_condition="Escalate to firewall engineering if rule baseline cannot be reconciled.",
            initial_metrics=[
                metric("Flow", "Denied"),
                metric("Port", "8443"),
                metric("Recent Change", "CHG-7782"),
            ],
            after_metrics=[
                metric("Flow", "Allowed"),
                metric("Scope", "Specific"),
                metric("Reachability", "Passed"),
            ],
            history_rows=history(
                "firewall-rule-block",
                "FW",
                "FW-PERIM-02",
                [
                    ("Rolled back specific deny rule after flow comparison.", "Reachability restored."),
                    ("Added narrow allow for approved source and destination.", "No broad rule."),
                    ("Validated rule hit count and app port health.", "Evidence attached."),
                ],
                (
                    "Operator created temporary any-any allow during outage.",
                    "Unsafe precedent: overbroad access violated firewall policy.",
                ),
                (
                    "Rollback did not restore traffic due to upstream route issue.",
                    "Escalated to network routing team.",
                ),
            ),
            unsafe_message="Unsafe history used an any-any allow; SOP requires a narrow approved flow only.",
            execution_message="Mock firewall rollback restored the approved TCP 8443 flow without broad access.",
            validation_message="Partner API TCP 8443 reachability moved from denied to allowed for the scoped flow.",
            rca_root_cause="A recent deny rule overlapped the approved Partner API flow.",
            rca_actions=[
                "Retrieved firewall rule SOP.",
                "Compared failed flow with recent change.",
                "Excluded unsafe any-any precedent.",
                "Captured approval.",
                "Validated scoped reachability.",
            ],
            rca_follow_up=[
                "Add pre-change flow simulation.",
                "Require diff review for deny rules.",
            ],
            mttr_minutes=12,
        ),
        scenario(
            scenario_id="backup-job-failed",
            team="Backup",
            alert_type="Critical server backup failed",
            incident_id="INC-2026-00427",
            priority="P3",
            title="Critical file server backup job failed",
            service="Enterprise Backup",
            ci="BKP-JOB-FS-118",
            current_state="Last backup failed with checkpoint error; recovery point age is 31 hours.",
            requested_outcome="Rerun backup from safe checkpoint and validate recovery point freshness.",
            sop_id="SOP-BKP-JOB-007",
            sop_title="Failed Backup Job Recovery",
            sop_summary="Check last good recovery point, rerun from checkpoint, avoid deleting backup chains, and validate completion.",
            controls=[
                "Check last successful backup before rerun.",
                "Do not delete backup chains during first response.",
                "Require approval before rerun.",
                "Validate job completion and recovery point age.",
            ],
            plan_summary="Rerun the failed backup job from the last safe checkpoint in mock mode.",
            target_resources=["BKP-JOB-FS-118", "FS-118 recovery point"],
            action_preview="Mock action: verify last good checkpoint, rerun incremental backup job, validate repository chain.",
            estimated_effect="Backup status moves from failed to completed and recovery point age drops from 31 hours to 12 minutes.",
            validation_steps=[
                "Confirm last successful recovery point.",
                "Validate rerun job completion.",
                "Validate recovery point age below 4 hours.",
            ],
            escalation_condition="Escalate to backup engineering if checkpoint validation fails.",
            initial_metrics=[
                metric("Job Status", "Failed"),
                metric("RPO Age", "31 hr"),
                metric("Checkpoint", "Last good"),
            ],
            after_metrics=[
                metric("Job Status", "Completed"),
                metric("RPO Age", "12 min"),
                metric("Chain", "Healthy"),
            ],
            history_rows=history(
                "backup-job-failed",
                "BKP",
                "BKP-JOB-FS-118",
                [
                    ("Reran incremental job from safe checkpoint.", "RPO recovered."),
                    ("Validated backup chain before rerun.", "No full reseed needed."),
                    ("Cleared transient repository lock after approval.", "Job completed."),
                ],
                (
                    "Engineer deleted old restore points to force a rerun.",
                    "Unsafe precedent: backup chain was damaged.",
                ),
                (
                    "Rerun failed because repository metadata was corrupt.",
                    "Escalated to backup platform engineering.",
                ),
            ),
            unsafe_message="Unsafe history deleted restore points; SOP requires preserving the backup chain.",
            execution_message="Mock backup rerun completed from the safe checkpoint and preserved the chain.",
            validation_message="Backup job completed and recovery point age recovered from 31 hours to 12 minutes.",
            rca_root_cause="A transient checkpoint lock caused the scheduled backup to fail.",
            rca_actions=[
                "Retrieved backup job SOP.",
                "Confirmed last good checkpoint.",
                "Excluded unsafe restore-point deletion precedent.",
                "Captured approval.",
                "Validated job completion.",
            ],
            rca_follow_up=[
                "Alert earlier on checkpoint lock duration.",
                "Review repository lock cleanup.",
            ],
            mttr_minutes=14,
        ),
        scenario(
            scenario_id="servicedesk-account-lockout",
            team="Service Desk",
            alert_type="User account locked repeatedly",
            incident_id="INC-2026-00428",
            priority="P4",
            title="User account has repeated lockouts",
            service="End User Access",
            ci="AD-USER-PRIYA.R",
            current_state="User account locked 7 times in 20 minutes from workstation LAP-2217.",
            requested_outcome="Identify lockout source, unlock account after approval, and validate login.",
            sop_id="SOP-SD-LOCK-008",
            sop_title="Repeated User Account Lockout",
            sop_summary="Identify source device, avoid password reset first, unlock after approval, and validate login.",
            controls=[
                "Identify lockout source before unlock.",
                "Do not reset password unless requested by identity policy.",
                "Require approval or identity verification.",
                "Validate successful login and stop repeated lockouts.",
            ],
            plan_summary="Unlock the user account in mock mode after identifying the lockout source.",
            target_resources=["AD-USER-PRIYA.R", "LAP-2217 cached credential source"],
            action_preview="Mock action: record source LAP-2217, unlock AD-USER-PRIYA.R, advise cached credential cleanup.",
            estimated_effect="Account state changes from locked to unlocked and repeated lockouts stop.",
            validation_steps=[
                "Confirm lockout source workstation.",
                "Confirm user identity verification.",
                "Validate login succeeds without new lockout.",
            ],
            escalation_condition="Escalate to endpoint team if lockouts continue from the workstation.",
            initial_metrics=[
                metric("Lockouts", "7"),
                metric("Source", "LAP-2217"),
                metric("Account", "Locked"),
            ],
            after_metrics=[
                metric("Lockouts", "0 new"),
                metric("Login", "Successful"),
                metric("Account", "Unlocked"),
            ],
            history_rows=history(
                "servicedesk-account-lockout",
                "SD",
                "AD-USER-PRIYA.R",
                [
                    ("Identified cached credential source and unlocked account.", "Login validated."),
                    ("Resolved mobile mail stale password causing lockout.", "No password reset needed."),
                    ("Unlocked after identity verification and source tracking.", "No repeat lockout."),
                ],
                (
                    "Technician reset password without identifying source.",
                    "Unsafe precedent: lockouts continued and user impact increased.",
                ),
                (
                    "Lockouts persisted after unlock due to managed device issue.",
                    "Escalated to endpoint team.",
                ),
            ),
            unsafe_message="Unsafe history reset the password first; SOP requires source identification before unlock.",
            execution_message="Mock unlock restored account access and recorded the lockout source.",
            validation_message="Account moved from locked to unlocked and no new lockout occurred after login.",
            rca_root_cause="Cached credentials on LAP-2217 repeatedly locked the user account.",
            rca_actions=[
                "Retrieved service desk lockout SOP.",
                "Identified lockout source.",
                "Excluded unsafe reset-first precedent.",
                "Captured approval.",
                "Validated login success.",
            ],
            rca_follow_up=[
                "Notify user to clear cached credentials.",
                "Add source workstation to ticket template.",
            ],
            mttr_minutes=6,
        ),
        scenario(
            scenario_id="ad-gpo-not-applying",
            team="AD",
            alert_type="Group Policy not applying",
            incident_id="INC-2026-00429",
            priority="P3",
            title="Finance workstation group policy version mismatch",
            service="Active Directory Policy",
            ci="AD-GPO-FIN-LOCKDOWN",
            current_state="Pilot workstation reports GPO version 41 while SYSVOL has version 43.",
            requested_outcome="Validate SYSVOL/GPO version and refresh policy safely.",
            sop_id="SOP-AD-GPO-009",
            sop_title="Group Policy Application Recovery",
            sop_summary="Validate GPO version and SYSVOL health, avoid broad OU changes, refresh policy, and validate target version.",
            controls=[
                "Validate SYSVOL and GPO version before action.",
                "Do not unlink or relink broad OUs during first response.",
                "Require approval for policy refresh.",
                "Validate expected GPO version on target machines.",
            ],
            plan_summary="Force policy refresh on the affected pilot workstation in mock mode after version validation.",
            target_resources=["AD-GPO-FIN-LOCKDOWN", "FIN-LAP-044"],
            action_preview="Mock action: validate SYSVOL version 43, trigger policy refresh on FIN-LAP-044, confirm applied GPO version.",
            estimated_effect="Pilot workstation policy version updates from 41 to 43.",
            validation_steps=[
                "Confirm SYSVOL advertises GPO version 43.",
                "Validate target workstation policy refresh.",
                "Confirm no OU links were changed.",
            ],
            escalation_condition="Escalate to AD engineering if SYSVOL replication is inconsistent.",
            initial_metrics=[
                metric("Client GPO", "v41"),
                metric("SYSVOL GPO", "v43"),
                metric("Replication", "Healthy"),
            ],
            after_metrics=[
                metric("Client GPO", "v43"),
                metric("Refresh", "Passed"),
                metric("OU Links", "Unchanged"),
            ],
            history_rows=history(
                "ad-gpo-not-applying",
                "ADGPO",
                "AD-GPO-FIN-LOCKDOWN",
                [
                    ("Forced gpupdate after SYSVOL version validation.", "Policy applied."),
                    ("Cleared local policy cache on a pilot workstation.", "No OU changes."),
                    ("Validated GPO version before refresh.", "Audit evidence attached."),
                ],
                (
                    "Engineer unlinked and relinked the finance OU.",
                    "Unsafe precedent: policy scope changed for unaffected users.",
                ),
                (
                    "Policy refresh failed because SYSVOL replication was stale.",
                    "Escalated to AD replication support.",
                ),
            ),
            unsafe_message="Unsafe history changed OU links; SOP requires target validation without broad policy-scope changes.",
            execution_message="Mock GPO refresh updated the pilot workstation without changing OU links.",
            validation_message="Target workstation moved from GPO version 41 to 43 with OU links unchanged.",
            rca_root_cause="Pilot workstation held a stale local Group Policy version.",
            rca_actions=[
                "Retrieved AD GPO SOP.",
                "Validated SYSVOL version.",
                "Excluded unsafe OU relink precedent.",
                "Captured approval.",
                "Validated target GPO version.",
            ],
            rca_follow_up=[
                "Add GPO version drift monitoring.",
                "Document pilot refresh steps.",
            ],
            mttr_minutes=13,
        ),
        scenario(
            scenario_id="command-centre-alert-storm",
            team="Command Centre",
            alert_type="Major incident alert storm / duplicate alerts",
            incident_id="INC-2026-00430",
            priority="P2",
            title="Duplicate alert storm for checkout service",
            service="Enterprise Monitoring",
            ci="MON-CORR-01",
            current_state="147 duplicate alerts opened in 12 minutes for the same checkout symptom.",
            requested_outcome="Correlate duplicates, suppress child alerts, and create a parent incident.",
            sop_id="SOP-CMD-ALERT-010",
            sop_title="Alert Storm Correlation",
            sop_summary="Correlate duplicate alerts, avoid closing without parent linkage, require approval, and validate suppression.",
            controls=[
                "Group alerts only when symptom, CI, and time window match.",
                "Do not bulk-close alerts without parent incident linkage.",
                "Require approval before suppression.",
                "Validate duplicate count and parent linkage.",
            ],
            plan_summary="Correlate duplicate checkout alerts and create a parent incident in mock mode.",
            target_resources=["MON-CORR-01", "checkout-alert-group-2026-00430"],
            action_preview="Mock action: group 147 duplicate alerts, create parent MI, suppress matching child alerts for 30 minutes.",
            estimated_effect="Open duplicate alerts reduce from 147 to 1 parent incident with child links preserved.",
            validation_steps=[
                "Confirm duplicate symptom and CI match.",
                "Validate parent incident is created.",
                "Validate child alerts are linked, not deleted.",
            ],
            escalation_condition="Escalate to incident commander if non-duplicate critical alerts remain.",
            initial_metrics=[
                metric("Duplicate Alerts", "147"),
                metric("Parent MI", "Missing"),
                metric("Window", "12 min"),
            ],
            after_metrics=[
                metric("Duplicate Alerts", "0 active"),
                metric("Parent MI", "Created"),
                metric("Child Links", "147"),
            ],
            history_rows=history(
                "command-centre-alert-storm",
                "CMD",
                "MON-CORR-01",
                [
                    ("Grouped duplicate alerts into a parent MI.", "Child links preserved."),
                    ("Applied scoped suppression after correlation.", "Noise reduced."),
                    ("Validated non-duplicate alerts remained visible.", "Command centre accepted."),
                ],
                (
                    "Operator bulk-closed alerts without parent linkage.",
                    "Unsafe precedent: audit trail and impact correlation were lost.",
                ),
                (
                    "Correlation found multiple symptoms in the alert storm.",
                    "Escalated to incident commander.",
                ),
            ),
            unsafe_message="Unsafe history bulk-closed alerts; SOP requires parent linkage and scoped suppression.",
            execution_message="Mock correlation grouped duplicate alerts and preserved child alert evidence.",
            validation_message="Duplicate active alerts reduced from 147 to 0 with one parent incident and 147 child links.",
            rca_root_cause="Monitoring correlation did not group repeated checkout symptoms quickly enough.",
            rca_actions=[
                "Retrieved alert storm SOP.",
                "Matched duplicate symptom and CI.",
                "Excluded unsafe bulk-close precedent.",
                "Captured approval.",
                "Validated parent linkage.",
            ],
            rca_follow_up=[
                "Tune correlation rule for checkout symptom.",
                "Add alert storm rate guard.",
            ],
            mttr_minutes=5,
        ),
        scenario(
            scenario_id="endpoint-third-party-app-exception",
            team="Endpoint Security",
            alert_type="Third-party application detected on endpoint",
            incident_id="INC-2026-00431",
            priority="P2",
            title="Unsigned third-party remote support tool detected",
            service="End User Security",
            ci="END-LAP-233",
            current_state="EDR detected RemoteAssistX on END-LAP-233, but the asset has a time-bound vendor support exception for APP-RA-X.",
            requested_outcome="Verify the exception, reject unsafe removal, preserve evidence, and escalate only if the exception is invalid.",
            sop_id="SOP-SEC-END-012",
            sop_title="Endpoint Third-Party Application Exception Handling",
            sop_summary="Check application exception registry before containment, never remove exception-approved tools automatically, preserve EDR evidence, and require security approval.",
            controls=[
                "Query the exception registry for the detected application and endpoint.",
                "Do not uninstall an approved exception app during first response.",
                "Preserve EDR evidence and business justification.",
                "Require security approval before quarantine or removal.",
            ],
            plan_summary="Reject automatic removal and preserve evidence because APP-RA-X has an approved exception for END-LAP-233.",
            target_resources=["END-LAP-233", "APP-RA-X exception EXC-4472", "RemoteAssistX"],
            action_preview="Mock action: verify EXC-4472, attach EDR evidence, notify security approver, do not uninstall RemoteAssistX.",
            estimated_effect="No endpoint state change occurs; approved exception remains visible and the incident is escalated for security review.",
            validation_steps=[
                "Confirm exception EXC-4472 is active and scoped to END-LAP-233.",
                "Confirm RemoteAssistX hash matches the exception record.",
                "Confirm no quarantine or uninstall action was executed.",
            ],
            escalation_condition="Escalate to security incident response if the hash, user, or endpoint does not match the exception.",
            initial_metrics=[
                metric("EDR Detection", "RemoteAssistX"),
                metric("Exception", "EXC-4472 active"),
                metric("Auto Removal", "Blocked"),
            ],
            after_metrics=[
                metric("Endpoint Change", "None"),
                metric("Evidence", "Preserved"),
                metric("Decision", "Rejected"),
            ],
            history_rows=history(
                "endpoint-third-party-app-exception",
                "SECAPP",
                "END-LAP-233",
                [
                    ("Verified approved vendor tool exception and preserved EDR evidence.", "No uninstall was performed."),
                    ("Matched application hash to exception registry before action.", "False-positive containment avoided."),
                    ("Escalated exception review without endpoint mutation.", "Security approval trail remained intact."),
                ],
                (
                    "Technician uninstalled the vendor support tool before checking exception registry.",
                    "Unsafe precedent: approved vendor work stopped and the exception audit trail was broken.",
                ),
                (
                    "Exception was expired for a similar endpoint.",
                    "Escalated to security incident response for containment approval.",
                ),
            ),
            unsafe_message="Unsafe history removed the app before exception lookup; SOP requires exception verification before containment.",
            execution_message="No mock remediation was executed because the operator rejected removal after exception proof.",
            validation_message="Exception EXC-4472 matched the endpoint and app hash; no endpoint mutation occurred.",
            rca_root_cause="The EDR alert matched a sanctioned third-party support tool covered by a time-bound exception.",
            rca_actions=[
                "Retrieved endpoint app exception SOP.",
                "Verified exception EXC-4472 for END-LAP-233.",
                "Excluded unsafe uninstall-first precedent.",
                "Recorded rejection with no state change.",
                "Preserved EDR evidence for security review.",
            ],
            rca_follow_up=[
                "Review exception expiry with application owner.",
                "Tune EDR allow-list to include scoped exception metadata.",
            ],
            mttr_minutes=4,
            replay_outcome="rejected",
            rejection_message=(
                "Operator rejected automatic removal because exception EXC-4472 is active "
                "for END-LAP-233 and RemoteAssistX; evidence was preserved with no mock execution."
            ),
        ),
        scenario(
            scenario_id="cloud-vm-unhealthy",
            team="Cloud",
            alert_type="VM instance unhealthy / failed status check",
            incident_id="INC-2026-00432",
            priority="P3",
            title="Cloud VM failed health check",
            service="Customer Portal",
            ci="CLOUD-VM-WEB-03",
            current_state="VM WEB-03 failed instance health checks for 9 minutes; load balancer has 1 unhealthy backend.",
            requested_outcome="Recover VM health or fail over without deleting the instance.",
            sop_id="SOP-CLD-VM-011",
            sop_title="Cloud VM Health Recovery",
            sop_summary="Check load balancer health, avoid terminate-first response, restart or fail over safely, and validate health checks.",
            controls=[
                "Confirm load balancer has healthy capacity before action.",
                "Do not terminate the VM as first response.",
                "Require approval for restart or failover.",
                "Validate instance and service health checks.",
            ],
            plan_summary="Restart the unhealthy VM in mock mode while keeping load balancer failover active.",
            target_resources=["CLOUD-VM-WEB-03", "Customer Portal load balancer"],
            action_preview="Mock action: drain WEB-03 from load balancer, restart instance, reattach after health checks pass.",
            estimated_effect="Unhealthy backend count moves from 1 to 0 and service health checks pass.",
            validation_steps=[
                "Confirm alternate healthy backend capacity.",
                "Validate instance status checks pass.",
                "Validate load balancer backend health.",
            ],
            escalation_condition="Escalate to cloud engineering if VM fails health checks after restart.",
            initial_metrics=[
                metric("VM Health", "Failed"),
                metric("Unhealthy Backends", "1"),
                metric("Service Health", "Degraded"),
            ],
            after_metrics=[
                metric("VM Health", "Passed"),
                metric("Unhealthy Backends", "0"),
                metric("Service Health", "Healthy"),
            ],
            history_rows=history(
                "cloud-vm-unhealthy",
                "CLD",
                "CLOUD-VM-WEB-03",
                [
                    ("Drained and restarted unhealthy VM after capacity check.", "Health recovered."),
                    ("Failed traffic to healthy backend before restart.", "No user impact."),
                    ("Reattached instance after health check validation.", "LB state healthy."),
                ],
                (
                    "Engineer terminated the VM before collecting diagnostics.",
                    "Unsafe precedent: diagnostic evidence was lost and capacity dropped.",
                ),
                (
                    "Restart did not recover instance due to host degradation.",
                    "Escalated to cloud provider support.",
                ),
            ),
            unsafe_message="Unsafe history terminated the VM first; SOP requires drain, diagnostic preservation, and restart/failover.",
            execution_message="Mock cloud recovery drained, restarted, and reattached the VM after health checks passed.",
            validation_message="VM health moved from failed to passed and unhealthy load balancer backends dropped to 0.",
            rca_root_cause="The cloud VM failed instance status checks while other backend capacity remained available.",
            rca_actions=[
                "Retrieved cloud VM health SOP.",
                "Confirmed load balancer capacity.",
                "Excluded unsafe terminate-first precedent.",
                "Captured approval.",
                "Validated instance and service health.",
            ],
            rca_follow_up=[
                "Add automated drain-before-restart runbook.",
                "Review instance health trend.",
            ],
            mttr_minutes=9,
        ),
    ]


def main() -> None:
    catalog = build_catalog()
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLAY_ROOT.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    for item in catalog:
        events = replay_events(item)
        text = "\n".join(json.dumps(event, separators=(",", ":")) for event in events) + "\n"
        (REPLAY_ROOT / item["replay_file"]).write_text(text, encoding="utf-8")
        if item["scenario_id"] == "disk-space":
            (REPLAY_ROOT / "disk-space-run.events.jsonl").write_text(
                text, encoding="utf-8"
            )


if __name__ == "__main__":
    main()
