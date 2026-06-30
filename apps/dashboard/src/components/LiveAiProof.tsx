import { Activity, BadgeCheck, BrainCircuit, Clock3, Coins, Gauge, Server, Wrench } from 'lucide-react';
import { formatMoney, latestTelemetry } from '../telemetry';
import type { AiGeneratedPayload, Mode, RunEvent } from '../types';

type Props = {
  backendOnline: boolean;
  events: RunEvent[];
  mode: Mode;
  runId: string | null;
};

type GeneratedPayload = AiGeneratedPayload & Record<string, unknown>;

const AI_EVENT_TYPES = new Set([
  'evidence.summary',
  'plan.generated',
  'approval.summary',
  'rca.generated',
]);

function latestAiEvent(events: RunEvent[]): RunEvent | undefined {
  return [...events]
    .reverse()
    .find((event) => AI_EVENT_TYPES.has(event.type) && event.payload);
}

function sourceText(payload?: GeneratedPayload): string {
  if (!payload) return 'Awaiting generated evidence';
  if (!payload.ai_source) return 'Replay/static evidence';
  if (payload.ai_source === 'openai') return payload.generated_by ?? 'OpenAI Responses API';
  return payload.generated_by ?? 'Deterministic fallback';
}

function sourceTone(payload?: GeneratedPayload): 'openai' | 'fallback' | 'replay' | 'pending' {
  if (!payload) return 'pending';
  return payload.ai_source ?? 'replay';
}

function formatTime(value?: string): string {
  if (!value) return 'Waiting';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function LiveAiProof({ backendOnline, events, mode, runId }: Props) {
  const latest = latestAiEvent(events);
  const payload = latest?.payload as GeneratedPayload | undefined;
  const fallbackCount = events.filter((event) => event.type === 'openai.fallback').length;
  const telemetry = latestTelemetry(events);
  const tone = sourceTone(payload);
  const source = sourceText(payload);
  const replayEvidence = mode === 'replay' && Boolean(latest) && !payload?.ai_source;
  const model = payload?.model ? String(payload.model) : replayEvidence ? 'Replay' : 'Pending';
  const fallbackStatus =
    fallbackCount > 0
      ? `${fallbackCount} fallback event${fallbackCount === 1 ? '' : 's'}`
      : latest
        ? 'No fallback'
        : 'Not evaluated';
  const tokenLatency = telemetry
    ? `${telemetry.total_tokens} / ${telemetry.total_latency_ms} ms`
    : replayEvidence
      ? 'Replay only'
      : 'Pending';
  const toolTraceCount =
    [payload?.ai_tool_trace?.length, payload?.ai_usage?.tool_calls?.length, telemetry?.total_tool_calls].find(
      (count) => typeof count === 'number' && count > 0,
    ) ?? 0;
  const toolTrace = toolTraceCount > 0 ? `${toolTraceCount} local tools` : replayEvidence ? 'Replay trace' : 'Pending';
  const costComparison = telemetry
    ? `${formatMoney(telemetry.estimated_openai_cost_usd)} / $${telemetry.human_hourly_rate_usd}/hr`
    : replayEvidence
      ? 'No API cost / $30/hr'
      : 'Pending / $30/hr';

  return (
    <section className="live-ai-proof" data-state={tone} aria-label="Live AI proof">
      <div className="proof-title">
        <BrainCircuit size={18} aria-hidden="true" />
        <div>
          <strong>Live AI Proof</strong>
          <span>{mode === 'live' ? 'Local backend evidence' : 'Replay evidence'}</span>
        </div>
      </div>
      <article>
        <BadgeCheck size={16} aria-hidden="true" />
        <span>Source</span>
        <strong>{source}</strong>
      </article>
      <article>
        <Server size={16} aria-hidden="true" />
        <span>Model / Backend</span>
        <strong>{model} / {backendOnline ? 'online' : 'offline'}</strong>
      </article>
      <article>
        <Activity size={16} aria-hidden="true" />
        <span>Run / Events</span>
        <strong>{runId ?? 'not started'} / {events.length}</strong>
      </article>
      <article>
        <Clock3 size={16} aria-hidden="true" />
        <span>Timestamp / Fallback</span>
        <strong>{formatTime(latest?.timestamp)} / {fallbackStatus}</strong>
      </article>
      <article>
        <Gauge size={16} aria-hidden="true" />
        <span>Tokens / Latency</span>
        <strong>{tokenLatency}</strong>
      </article>
      <article>
        <Wrench size={16} aria-hidden="true" />
        <span>Tool Loop</span>
        <strong>{toolTrace}</strong>
      </article>
      <article>
        <Coins size={16} aria-hidden="true" />
        <span>API Cost / Human Rate</span>
        <strong>{costComparison}</strong>
      </article>
    </section>
  );
}
