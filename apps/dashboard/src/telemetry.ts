import type { AiTelemetrySummary, RunEvent } from './types';

type TelemetryPayload = {
  ai_telemetry?: AiTelemetrySummary | null;
};

export function latestTelemetry(events: RunEvent[]): AiTelemetrySummary | undefined {
  for (const event of [...events].reverse()) {
    const payload = event.payload as TelemetryPayload | undefined;
    if (payload?.ai_telemetry) {
      return payload.ai_telemetry;
    }
  }
  return undefined;
}

export function formatMoney(value?: number | null, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Pending';
  return `$${value.toFixed(digits)}`;
}

export function formatMinutes(value: number): string {
  if (value >= 60) {
    return `${(value / 60).toFixed(1)} hr`;
  }
  return `${Math.round(value)} min`;
}
