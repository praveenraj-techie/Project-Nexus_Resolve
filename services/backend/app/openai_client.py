from __future__ import annotations

import asyncio
import json
import os
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from .config import load_project_env
from .models import (
    AiToolCallRecord,
    AiUsageRecord,
    ApprovalSummary,
    EvidenceItem,
    EvidenceSummary,
    IncidentTicket,
    PolicyCheck,
    RemediationPlan,
    RcaSummary,
)
from .policy import policy_check
from .rca import fallback_rca


load_project_env()


class PlanOutput(BaseModel):
    summary: str
    target_resources: list[str]
    action_preview: str
    estimated_effect: str
    safeguards: list[str]
    approval_required: bool
    uses_dry_run: bool
    mock_only: bool
    validation_steps: list[str]
    escalation_condition: str


class EvidenceSummaryOutput(BaseModel):
    outcome: str
    sop_controls: list[str]
    safe_precedent_count: int
    unsafe_precedent_ids: list[str]
    escalation_precedent_ids: list[str]
    governance_note: str


class ApprovalSummaryOutput(BaseModel):
    decision_required: bool
    operator_message: str
    expected_safe_effect: str
    blocked_until_approved: bool
    replay_side_effects_disabled: bool


class RcaMetricOutput(BaseModel):
    label: str
    value: str


class RcaOutput(BaseModel):
    root_cause: str
    actions_taken: list[str]
    validation: str
    business_impact: str
    follow_up: list[str]
    metrics: list[RcaMetricOutput]


class NexusOpenAIClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        mode: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.mode = mode or os.getenv("APP_MODE", "mock")
        self.last_notice: str | None = None
        self.last_response_source = "fallback"
        self.last_usage_record: AiUsageRecord | None = None
        self.last_tool_calls: list[AiToolCallRecord] = []

    async def create_evidence_summary(
        self,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> EvidenceSummary:
        started = perf_counter()
        operation = "evidence.summary"
        if self.mode == "live" and not self.api_key:
            self.last_notice = "OpenAI API key is not configured, using validated fallback response"
        if self.mode == "live" and self.api_key:
            try:
                result, responses, tool_calls = await asyncio.to_thread(
                    self._create_evidence_summary_live, ticket, sop, history, state
                )
                self.last_response_source = "openai"
                self._record_usage(
                    operation,
                    "openai",
                    started,
                    responses=responses,
                    tool_calls=tool_calls,
                )
                return result
            except Exception:
                self.last_notice = (
                    "OpenAI unavailable, using validated fallback response"
                )
        self.last_response_source = "fallback"
        result = self._fallback_evidence_summary(ticket, sop, history, state)
        self._record_usage(operation, "fallback", started)
        return result

    async def create_plan(
        self,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> RemediationPlan:
        started = perf_counter()
        operation = "plan.generated"
        if self.mode == "live" and not self.api_key:
            self.last_notice = "OpenAI API key is not configured, using validated fallback response"
        if self.mode == "live" and self.api_key:
            try:
                result, responses, tool_calls = await asyncio.to_thread(
                    self._create_plan_live, ticket, sop, history, state
                )
                self.last_response_source = "openai"
                self._record_usage(
                    operation,
                    "openai",
                    started,
                    responses=responses,
                    tool_calls=tool_calls,
                )
                return result
            except Exception:
                self.last_notice = (
                    "OpenAI unavailable, using validated fallback response"
                )
        self.last_response_source = "fallback"
        result = self._fallback_plan(state)
        self._record_usage(operation, "fallback", started)
        return result

    async def create_approval_summary(
        self, plan: RemediationPlan, checks: list[PolicyCheck]
    ) -> ApprovalSummary:
        started = perf_counter()
        operation = "approval.summary"
        if self.mode == "live" and not self.api_key:
            self.last_notice = "OpenAI API key is not configured, using validated fallback response"
        if self.mode == "live" and self.api_key:
            try:
                result, response = await asyncio.to_thread(
                    self._create_approval_summary_live, plan, checks
                )
                self.last_response_source = "openai"
                self._record_usage(operation, "openai", started, response=response)
                return result
            except Exception:
                self.last_notice = (
                    "OpenAI unavailable, using validated fallback response"
                )
        self.last_response_source = "fallback"
        result = self._fallback_approval_summary(plan)
        self._record_usage(operation, "fallback", started)
        return result

    async def create_rca(
        self, before: dict[str, Any], after: dict[str, Any]
    ) -> RcaSummary:
        started = perf_counter()
        operation = "rca.generated"
        if self.mode == "live" and not self.api_key:
            self.last_notice = "OpenAI API key is not configured, using validated fallback response"
        if self.mode == "live" and self.api_key:
            try:
                result, response = await asyncio.to_thread(self._create_rca_live, before, after)
                self.last_response_source = "openai"
                self._record_usage(operation, "openai", started, response=response)
                return result
            except Exception:
                self.last_notice = (
                    "OpenAI unavailable, using validated fallback response"
                )
        self.last_response_source = "fallback"
        result = fallback_rca(before, after)
        self._record_usage(operation, "fallback", started)
        return result

    def _record_usage(
        self,
        operation: str,
        source: str,
        started: float,
        *,
        response: Any | None = None,
        responses: list[Any] | None = None,
        tool_calls: list[AiToolCallRecord] | None = None,
    ) -> None:
        collected_responses = responses or ([response] if response is not None else [])
        input_tokens = self._usage_sum(
            collected_responses, "input_tokens", "prompt_tokens"
        )
        output_tokens = self._usage_sum(
            collected_responses, "output_tokens", "completion_tokens"
        )
        total_tokens = self._usage_sum(collected_responses, "total_tokens")
        if total_tokens is None and (
            input_tokens is not None or output_tokens is not None
        ):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        if source == "openai":
            estimated_cost, cost_basis = self._estimate_cost(input_tokens, output_tokens)
        else:
            estimated_cost, cost_basis = 0.0, "fallback_no_api_cost"
        self.last_tool_calls = tool_calls or []
        self.last_usage_record = AiUsageRecord(
            operation=operation,
            source="openai" if source == "openai" else "fallback",
            model=self.model,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            cost_basis=cost_basis,
            tool_calls=self.last_tool_calls,
        )

    @staticmethod
    def _usage_int(usage: Any, *names: str) -> int | None:
        if usage is None:
            return None
        for name in names:
            value = getattr(usage, name, None)
            if value is None and isinstance(usage, dict):
                value = usage.get(name)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return None

    def _usage_sum(self, responses: list[Any], *names: str) -> int | None:
        total = 0
        found = False
        for item in responses:
            value = self._usage_int(getattr(item, "usage", None), *names)
            if value is None:
                continue
            total += value
            found = True
        return total if found else None

    @staticmethod
    def _cost_rate(name: str) -> float | None:
        raw = os.getenv(name)
        defaults = {
            "OPENAI_INPUT_COST_PER_1M_USD": 1.25,
            "OPENAI_OUTPUT_COST_PER_1M_USD": 10.0,
        }
        if raw in (None, ""):
            return defaults.get(name)
        try:
            return float(raw)
        except ValueError:
            return defaults.get(name)

    def _estimate_cost(
        self, input_tokens: int | None, output_tokens: int | None
    ) -> tuple[float | None, str]:
        input_rate = self._cost_rate("OPENAI_INPUT_COST_PER_1M_USD")
        output_rate = self._cost_rate("OPENAI_OUTPUT_COST_PER_1M_USD")
        if input_tokens is None and output_tokens is None:
            return None, "usage_tokens_not_returned"
        cost = ((input_tokens or 0) / 1_000_000 * input_rate) + (
            (output_tokens or 0) / 1_000_000 * output_rate
        )
        return round(cost, 6), "OPENAI_INPUT_COST_PER_1M_USD+OPENAI_OUTPUT_COST_PER_1M_USD"

    def _agent_tools(self) -> list[dict[str, Any]]:
        schema_base = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "scenario_id": {
                    "type": "string",
                    "description": "Synthetic scenario id from the current incident.",
                }
            },
            "required": ["scenario_id"],
        }
        return [
            {
                "type": "function",
                "name": "retrieve_sop",
                "description": "Retrieve the governing SOP for the synthetic incident.",
                "parameters": schema_base,
                "strict": True,
            },
            {
                "type": "function",
                "name": "retrieve_history",
                "description": "Retrieve similar synthetic historical tickets and unsafe precedent flags.",
                "parameters": schema_base,
                "strict": True,
            },
            {
                "type": "function",
                "name": "get_initial_state",
                "description": "Retrieve the synthetic before-state, metrics, and recovery target.",
                "parameters": schema_base,
                "strict": True,
            },
            {
                "type": "function",
                "name": "preview_policy_checks",
                "description": "Preview NEXUS policy checks for a candidate mock-only remediation plan.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "scenario_id": {
                            "type": "string",
                            "description": "Synthetic scenario id from the current incident.",
                        },
                        "plan": {
                            "type": "object",
                            "additionalProperties": False,
                            "description": "Candidate remediation plan to check.",
                            "properties": {
                                "summary": {"type": "string"},
                                "target_resources": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "action_preview": {"type": "string"},
                                "estimated_effect": {"type": "string"},
                                "safeguards": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "approval_required": {"type": "boolean"},
                                "uses_dry_run": {"type": "boolean"},
                                "mock_only": {"type": "boolean"},
                                "validation_steps": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "escalation_condition": {"type": "string"},
                            },
                            "required": [
                                "summary",
                                "target_resources",
                                "action_preview",
                                "estimated_effect",
                                "safeguards",
                                "approval_required",
                                "uses_dry_run",
                                "mock_only",
                                "validation_steps",
                                "escalation_condition",
                            ],
                        },
                    },
                    "required": ["scenario_id", "plan"],
                },
                "strict": True,
            },
        ]

    def _execute_agent_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        scenario_id = str(arguments.get("scenario_id") or ticket.scenario_id)
        if scenario_id != ticket.scenario_id:
            return {
                "error": "scenario_mismatch",
                "requested": scenario_id,
                "current": ticket.scenario_id,
            }
        if name == "retrieve_sop":
            return sop.model_dump(mode="json")
        if name == "retrieve_history":
            return {
                "items": [item.model_dump(mode="json") for item in history],
                "unsafe_precedent_ids": [
                    item.id for item in history if not item.metadata.get("safe")
                ],
                "escalation_precedent_ids": [
                    item.id
                    for item in history
                    if item.metadata.get("outcome") == "escalated"
                ],
            }
        if name == "get_initial_state":
            return state
        if name == "preview_policy_checks":
            plan_payload = arguments.get("plan")
            plan = RemediationPlan.model_validate(plan_payload)
            return {
                "checks": [
                    check.model_dump(mode="json")
                    for check in policy_check(plan, enforce_approval=False)
                ]
            }
        raise ValueError(f"Unknown OpenAI tool requested: {name}")

    def _run_grounded_response(
        self,
        *,
        operation: str,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
        text_format: type[BaseModel],
        system_prompt: str,
        final_prompt: str,
    ) -> tuple[BaseModel, list[Any], list[AiToolCallRecord]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        tools = self._agent_tools()
        responses: list[Any] = []
        tool_records: list[AiToolCallRecord] = []
        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are the NEXUS-RESOLVE governed remediation agent. "
                        "Use only the provided function tools and returned facts. "
                        "Do not invent infrastructure facts. Never propose real execution."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "operation": operation,
                            "ticket": ticket.model_dump(mode="json"),
                            "instructions": system_prompt,
                            "required_tools": [
                                "retrieve_sop",
                                "retrieve_history",
                                "get_initial_state",
                            ],
                        }
                    ),
                },
            ],
            tools=tools,
            tool_choice="required",
            parallel_tool_calls=False,
            max_tool_calls=6,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
        )
        responses.append(response)

        for _ in range(4):
            function_calls = [
                item
                for item in getattr(response, "output", [])
                if getattr(item, "type", None) == "function_call"
            ]
            if not function_calls:
                break

            tool_outputs = []
            for call in function_calls:
                started = perf_counter()
                try:
                    arguments = json.loads(call.arguments or "{}")
                    result = self._execute_agent_tool(
                        call.name,
                        arguments,
                        ticket=ticket,
                        sop=sop,
                        history=history,
                        state=state,
                    )
                    status = "completed"
                except Exception as exc:
                    arguments = {"raw": getattr(call, "arguments", "")}
                    result = {"error": str(exc)}
                    status = "failed"
                output = json.dumps(result, ensure_ascii=True, default=str)
                tool_records.append(
                    AiToolCallRecord(
                        operation=operation,
                        name=call.name,
                        arguments=arguments,
                        output_preview=output[:700],
                        status=status,
                        call_id=call.call_id,
                        latency_ms=max(0, round((perf_counter() - started) * 1000)),
                    )
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                )

            response = client.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                max_tool_calls=6,
                reasoning={"effort": "low"},
                text={"verbosity": "low"},
            )
            responses.append(response)

        parsed = client.responses.parse(
            model=self.model,
            previous_response_id=response.id,
            input=[
                {
                    "role": "user",
                    "content": (
                        f"{final_prompt} Return only the requested structured output. "
                        "Keep all actions mock-only and approval-gated."
                    ),
                }
            ],
            text_format=text_format,
            tool_choice="none",
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
        )
        responses.append(parsed)
        return parsed.output_parsed, responses, tool_records

    def _create_evidence_summary_live(
        self,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> tuple[EvidenceSummary, list[Any], list[AiToolCallRecord]]:
        parsed, responses, tool_calls = self._run_grounded_response(
            operation="evidence.summary",
            ticket=ticket,
            sop=sop,
            history=history,
            state=state,
            text_format=EvidenceSummaryOutput,
            system_prompt=(
                "Build an evidence summary. SOP outranks history. Mention the "
                "incident signal, unsafe precedent, and why the SOP-governed "
                "mock path is safe."
            ),
            final_prompt="Create the operator-facing evidence summary.",
        )
        return EvidenceSummary.model_validate(parsed.model_dump()), responses, tool_calls

    def _create_plan_live(
        self,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> tuple[RemediationPlan, list[Any], list[AiToolCallRecord]]:
        parsed, responses, tool_calls = self._run_grounded_response(
            operation="plan.generated",
            ticket=ticket,
            sop=sop,
            history=history,
            state=state,
            text_format=PlanOutput,
            system_prompt=(
                "Generate a safe remediation plan from tool-returned facts only. "
                "SOP outranks historical tickets. Keep the action mock-only and "
                "include measurable validation."
            ),
            final_prompt="Create the final approval-gated mock-only remediation plan.",
        )
        return (
            RemediationPlan(
                summary=parsed.summary,
                target_resources=parsed.target_resources,
                action_preview=parsed.action_preview,
                estimated_effect=parsed.estimated_effect,
                safeguards=parsed.safeguards,
                approval_required=parsed.approval_required,
                uses_dry_run=parsed.uses_dry_run,
                mock_only=parsed.mock_only,
                validation_steps=parsed.validation_steps,
                escalation_condition=parsed.escalation_condition,
            ),
            responses,
            tool_calls,
        )

    def _create_approval_summary_live(
        self, plan: RemediationPlan, checks: list[PolicyCheck]
    ) -> tuple[ApprovalSummary, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Return an approval summary as structured JSON. "
                        "Use supplied facts only. The operator must understand "
                        "that execution is blocked until approval. Explain the "
                        "specific target, expected effect, and reason approval is "
                        "safe for this incident."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "plan": plan.model_dump(),
                            "policy_checks": [check.model_dump() for check in checks],
                        }
                    ),
                },
            ],
            text_format=ApprovalSummaryOutput,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
        )
        return ApprovalSummary.model_validate(response.output_parsed.model_dump()), response

    def _create_rca_live(
        self, before: dict[str, Any], after: dict[str, Any]
    ) -> tuple[RcaSummary, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Return an RCA summary as structured JSON. Use supplied "
                        "facts only. Write a fresh audit-ready RCA for this exact "
                        "incident, with root cause, actions taken, validation, "
                        "business impact, follow-up, and measurable metrics. Do not "
                        "copy the fallback RCA wording verbatim."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"before": before, "after": after}),
                },
            ],
            text_format=RcaOutput,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
        )
        parsed = response.output_parsed
        payload = parsed.model_dump()
        payload["metrics"] = {metric.label: metric.value for metric in parsed.metrics}
        return RcaSummary.model_validate(payload), response

    def _fallback_evidence_summary(
        self,
        ticket: IncidentTicket,
        sop: EvidenceItem,
        history: list[EvidenceItem],
        state: dict[str, Any],
    ) -> EvidenceSummary:
        if "evidence_summary" in state:
            return EvidenceSummary.model_validate(state["evidence_summary"])

        unsafe = [item.id for item in history if not item.metadata.get("safe")]
        escalations = [
            item.id for item in history if item.metadata.get("outcome") == "escalated"
        ]
        safe_count = len(history) - len(unsafe) - len(escalations)
        return EvidenceSummary(
            outcome=f"Proceed with SOP-governed mock remediation for {ticket.title}.",
            sop_controls=list(sop.metadata.get("controls", [])),
            safe_precedent_count=safe_count,
            unsafe_precedent_ids=unsafe,
            escalation_precedent_ids=escalations,
            governance_note=(
                f"SOP beats history: {unsafe[0]} is visible as a warning, "
                "not copied into the remediation plan."
                if unsafe
                else "SOP controls drive the remediation plan."
            ),
        )

    def _fallback_plan(self, state: dict[str, Any]) -> RemediationPlan:
        if "plan_template" in state:
            return RemediationPlan.model_validate(state["plan_template"])

        return RemediationPlan(
            summary="Run a scenario-approved mock remediation.",
            target_resources=["synthetic-resource"],
            action_preview="Mock action only.",
            estimated_effect="Scenario validation should improve.",
            safeguards=["Mock-only execution.", "Human approval required."],
            approval_required=True,
            uses_dry_run=True,
            mock_only=True,
            validation_steps=["Validate scenario metrics after mock execution."],
        )

    def _fallback_approval_summary(self, plan: RemediationPlan) -> ApprovalSummary:
        target = ", ".join(plan.target_resources)
        return ApprovalSummary(
            decision_required=True,
            operator_message=(
                f"Approve mock-only remediation for {target}."
            ),
            expected_safe_effect=(
                f"{plan.estimated_effect} Post-remediation validation is required."
            ),
            blocked_until_approved=True,
            replay_side_effects_disabled=True,
        )
