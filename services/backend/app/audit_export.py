from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .orchestrator import RunSession
from .models import utc_now
from .scenario_catalog import DATA_ROOT


def build_audit_packet(session: RunSession) -> dict[str, Any]:
    snapshot = session.snapshot().model_dump(mode="json")
    return build_audit_packet_from_snapshot(session.run_id, snapshot)


def build_audit_packet_from_snapshot(run_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    audit_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return {
        "run_id": run_id,
        "generated_at": utc_now().isoformat(),
        "audit_hash": f"sha256:{audit_hash}",
        "safety": {
            "synthetic_only": True,
            "mock_only": True,
            "approval_required": True,
            "real_execution_disabled": True,
        },
        "packet": snapshot,
    }


def load_persisted_run_snapshot(run_id: str) -> dict[str, Any] | None:
    if not _SAFE_RUN_ID.fullmatch(run_id):
        return None
    path = DATA_ROOT / "generated" / "runs" / f"{run_id}.events.jsonl"
    if not path.exists():
        return None

    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not events:
        return None
    return _snapshot_from_events(run_id, events)


def load_persisted_audit_packet(run_id: str) -> dict[str, Any] | None:
    snapshot = load_persisted_run_snapshot(run_id)
    if snapshot is None:
        return None
    return build_audit_packet_from_snapshot(run_id, snapshot)


def build_audit_pdf(packet: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.52 * inch,
        leftMargin=0.52 * inch,
        topMargin=0.48 * inch,
        bottomMargin=0.48 * inch,
        title=f"NEXUS-RESOLVE Audit Report {packet['run_id']}",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#17324d"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallBody",
            parent=styles["BodyText"],
            fontSize=8.7,
            leading=11,
            textColor=colors.HexColor("#253044"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Tiny",
            parent=styles["BodyText"],
            fontSize=7.4,
            leading=9,
            textColor=colors.HexColor("#475569"),
        )
    )

    snapshot = packet["packet"]
    events = snapshot.get("events", [])
    plan = snapshot.get("plan") or {}
    rca = snapshot.get("rca") or {}
    telemetry = snapshot.get("ai_telemetry") or {}
    approval = snapshot.get("approval_record") or {}
    servicenow_incident = snapshot.get("servicenow_incident") or {}
    itsm_twin = snapshot.get("itsm_twin") or {}
    itsm_records = itsm_twin.get("records", [])
    comms_drafts = itsm_twin.get("comms", [])

    story: list[Any] = []
    story.append(Paragraph("NEXUS-RESOLVE Audit Report", styles["Title"]))
    story.append(
        Paragraph(
            "Synthetic, mock-only remediation evidence packet for judge review.",
            styles["SmallBody"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(
        _table(
            [
                ("Run ID", packet["run_id"]),
                ("Status", snapshot.get("status", "unknown")),
                ("Generated", packet.get("generated_at", "")),
                ("Audit Hash", packet.get("audit_hash", "")),
                (
                    "ServiceNow",
                    servicenow_incident.get("number")
                    or servicenow_incident.get("mode")
                    or "not attached",
                ),
                (
                    "Local ITSM Twin",
                    f"{len(itsm_records)} records, {len(comms_drafts)} approval-gated comms",
                ),
                ("Safety", "synthetic_only=true, mock_only=true, real_execution_disabled=true"),
            ],
            styles,
        )
    )

    story.append(Paragraph("Decision And Approval", styles["SectionTitle"]))
    story.append(
        _table(
            [
                ("Plan", plan.get("summary", "Plan not generated yet.")),
                ("Targets", ", ".join(plan.get("target_resources", [])) or "Not available"),
                ("Action Preview", plan.get("action_preview", "Not available")),
                ("Approval Operator", approval.get("operator", "Not approved yet")),
                ("Approval Role", approval.get("role", "Not approved yet")),
                ("Approval Reason", approval.get("reason", "Not approved yet")),
            ],
            styles,
        )
    )

    story.append(Paragraph("RCA Outcome", styles["SectionTitle"]))
    story.append(
        _table(
            [
                ("Root Cause", rca.get("root_cause", "RCA not generated yet.")),
                ("Validation", rca.get("validation", "Validation pending.")),
                ("Business Impact", rca.get("business_impact", "Not available")),
                ("Follow Up", "; ".join(rca.get("follow_up", [])) or "Not available"),
            ],
            styles,
        )
    )

    story.append(Paragraph("OpenAI Telemetry And Cost Comparison", styles["SectionTitle"]))
    story.append(
        _table(
            [
                ("AI Decision Stages", str(telemetry.get("calls", 0))),
                ("OpenAI API / Fallback", f"{telemetry.get('openai_calls', 0)} / {telemetry.get('fallback_calls', 0)}"),
                ("OpenAI Tokens", str(telemetry.get("total_tokens", 0))),
                ("Measured AI Latency", f"{telemetry.get('total_latency_ms', 0)} ms"),
                ("OpenAI API Cost", _openai_cost_label(telemetry)),
                ("Human Baseline", f"{telemetry.get('human_baseline_minutes', 0)} min at {_money(telemetry.get('human_hourly_rate_usd', 30))}/hr"),
                ("Human Cost", _money(telemetry.get("estimated_human_cost_usd", 0))),
                ("Labor Savings", _money(telemetry.get("estimated_labor_savings_usd", 0))),
            ],
            styles,
        )
    )

    story.append(Paragraph("ITSM Twin And Communications", styles["SectionTitle"]))
    sent_comms = [draft for draft in comms_drafts if draft.get("status") == "sent"]
    pending_comms = [
        draft for draft in comms_drafts if draft.get("status") == "pending_approval"
    ]
    story.append(
        _table(
            [
                (
                    "Records",
                    ", ".join(
                        f"{record.get('record_type', '').upper()} {record.get('number', '')}"
                        for record in itsm_records[:6]
                    )
                    or "No local ITSM records",
                ),
                (
                    "Comms Policy",
                    itsm_twin.get(
                        "approval_policy",
                        "Every outbound communication requires human approval.",
                    ),
                ),
                ("Sent In Simulator", str(len(sent_comms))),
                ("Pending Approval", str(len(pending_comms))),
                ("External Side Effects", itsm_twin.get("external_side_effects", "disabled")),
            ],
            styles,
        )
    )

    story.append(Paragraph("Event Evidence", styles["SectionTitle"]))
    rows = [("Seq", "Type", "Title", "Message")]
    for event in events[:18]:
        rows.append(
            (
                str(event.get("sequence", "")),
                event.get("type", ""),
                event.get("title", ""),
                event.get("message", ""),
            )
        )
    story.append(_event_table(rows, styles))

    doc.build(story)
    return buffer.getvalue()


def _money(value: Any) -> str:
    try:
        return f"${float(value):.4f}"
    except (TypeError, ValueError):
        return "$0.0000"


def _openai_cost_label(telemetry: dict[str, Any]) -> str:
    openai_cost = telemetry.get("estimated_openai_cost_usd")
    if openai_cost is None:
        return "Pricing env not configured"
    label = _money(openai_cost)
    if (
        int(telemetry.get("openai_calls") or 0) == 0
        and int(telemetry.get("fallback_calls") or 0) > 0
    ):
        return f"{label} (fallback mode; no OpenAI API charge)"
    return label


def _table(rows: list[tuple[str, str]], styles: Any) -> KeepTogether:
    table = Table(
        [
            [
                Paragraph(str(label), styles["Tiny"]),
                Paragraph(str(value), styles["SmallBody"]),
            ]
            for label, value in rows
        ],
        colWidths=[1.55 * inch, 5.55 * inch],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf2f7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbe3ed")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return KeepTogether([table, Spacer(1, 8)])


def _event_table(rows: list[tuple[str, str, str, str]], styles: Any) -> Table:
    table = Table(
        [
            [
                Paragraph(str(seq), styles["Tiny"]),
                Paragraph(event_type, styles["Tiny"]),
                Paragraph(title, styles["Tiny"]),
                Paragraph(message, styles["Tiny"]),
            ]
            for seq, event_type, title, message in rows
        ],
        colWidths=[0.35 * inch, 1.45 * inch, 1.85 * inch, 3.45 * inch],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dbe3ed")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


_SAFE_RUN_ID = re.compile(r"run-[A-Za-z0-9_-]+")


def _snapshot_from_events(run_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "run_id": run_id,
        "status": _status_from_events(events),
        "events": events,
        "approval_record": None,
        "plan": None,
        "evidence_summary": None,
        "approval_summary": None,
        "policy_checks": [],
        "rca": None,
        "ai_telemetry": _default_telemetry(),
        "servicenow_incident": None,
        "itsm_twin": None,
    }

    for event in events:
        event_type = event.get("type")
        payload = event.get("payload") or {}
        if event_type == "evidence.summary":
            snapshot["evidence_summary"] = _without_runtime_ai_fields(payload)
        elif event_type == "plan.generated":
            snapshot["plan"] = _without_runtime_ai_fields(payload)
        elif event_type == "approval.summary":
            snapshot["approval_summary"] = _without_runtime_ai_fields(payload)
        elif event_type == "approval.requested":
            snapshot["plan"] = snapshot["plan"] or payload.get("plan")
            snapshot["approval_summary"] = (
                snapshot["approval_summary"] or payload.get("approval_summary")
            )
        elif event_type == "policy.checked":
            snapshot["policy_checks"] = payload.get("checks", snapshot["policy_checks"])
        elif event_type == "approval.granted":
            snapshot["approval_record"] = payload.get("approval_record")
            snapshot["policy_checks"] = payload.get("checks", snapshot["policy_checks"])
        elif event_type == "rca.generated":
            snapshot["rca"] = _without_runtime_ai_fields(payload)

        servicenow_incident = payload.get("servicenow_incident")
        if servicenow_incident:
            snapshot["servicenow_incident"] = servicenow_incident

        itsm_twin = payload.get("itsm_twin")
        if itsm_twin:
            snapshot["itsm_twin"] = itsm_twin

        telemetry = payload.get("ai_telemetry")
        if telemetry:
            snapshot["ai_telemetry"] = telemetry

    return snapshot


def _without_runtime_ai_fields(payload: dict[str, Any]) -> dict[str, Any]:
    ignored = {"ai_source", "model", "generated_by", "ai_usage", "ai_telemetry"}
    return {key: value for key, value in payload.items() if key not in ignored}


def _status_from_events(events: list[dict[str, Any]]) -> str:
    event_types = [str(event.get("type", "")) for event in events]
    if "incident.closed" in event_types:
        return "closed"
    if "approval.rejected" in event_types:
        return "rejected"
    if "policy.blocked" in event_types:
        return "blocked"
    if "closure.requested" in event_types:
        return "waiting_closure"
    if "approval.requested" in event_types:
        return "waiting_approval"
    return "running"


def _default_telemetry() -> dict[str, Any]:
    return {
        "calls": 0,
        "openai_calls": 0,
        "fallback_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_tool_calls": 0,
        "total_latency_ms": 0,
        "estimated_openai_cost_usd": None,
        "human_hourly_rate_usd": 30.0,
        "human_baseline_minutes": 45.0,
        "nexus_mttr_minutes": 0.0,
        "estimated_human_cost_usd": 22.5,
        "estimated_nexus_labor_cost_usd": 0.0,
        "estimated_labor_savings_usd": 22.5,
        "estimated_net_savings_usd": None,
        "records": [],
    }
