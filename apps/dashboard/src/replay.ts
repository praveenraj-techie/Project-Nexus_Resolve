import type { RunEvent } from './types';

const STATIC_BASE = import.meta.env.BASE_URL;
const REPLAY_EVENT_DELAY_MS = 1450;

export async function loadReplayEvents(scenarioId = 'disk-space'): Promise<RunEvent[]> {
  const response = await fetch(`${STATIC_BASE}data/replay/${scenarioId}.events.jsonl`);
  if (!response.ok) {
    throw new Error('Replay data is unavailable.');
  }
  const text = await response.text();
  return text
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as RunEvent);
}

export function playReplayEvents(
  events: RunEvent[],
  onEvent: (event: RunEvent) => void,
): () => void {
  let index = 0;
  const timer = window.setInterval(() => {
    const event = events[index];
    if (!event) {
      window.clearInterval(timer);
      return;
    }
    onEvent(event);
    index += 1;
  }, REPLAY_EVENT_DELAY_MS);

  return () => window.clearInterval(timer);
}
