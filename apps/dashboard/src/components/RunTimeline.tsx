import { useEffect, useRef } from 'react';
import { CheckCircle2, Clock3, ShieldAlert } from 'lucide-react';
import type { Mode, RunEvent } from '../types';

type Props = {
  events: RunEvent[];
  mode: Mode;
  status: string;
};

function eventIcon(type: string) {
  if (type.includes('blocked') || type.includes('warning')) {
    return <ShieldAlert size={17} aria-hidden="true" />;
  }
  if (type.includes('passed') || type.includes('generated') || type.includes('mocked')) {
    return <CheckCircle2 size={17} aria-hidden="true" />;
  }
  return <Clock3 size={17} aria-hidden="true" />;
}

function timelineSignal(mode: Mode, status: string, events: RunEvent[]) {
  if (status === 'Waiting approval') {
    return 'Human approval required. The run is paused before remediation.';
  }
  if (status === 'Waiting closure') {
    return 'RCA is ready. Waiting for Close INC or Observe.';
  }
  if (status === 'Observing') {
    return 'Observation window is running. Recovery metrics are being rechecked.';
  }
  if (status === 'Closed') {
    return 'Incident is closed with RCA, validation, and audit evidence attached.';
  }
  if (events.length > 0) {
    return mode === 'live'
      ? 'Live agent is processing the next governed step.'
      : 'Replay is revealing the governed steps one at a time.';
  }
  return 'Start simulation to begin the governed investigation trail.';
}

function TokenizedMessage({ text }: { text: string }) {
  const words = text.split(' ');
  return (
    <p className="tokenized-message">
      {words.map((word, index) => (
        <span
          className="token-word"
          key={`${word}-${index}`}
          style={{ animationDelay: `${Math.min(index * 52, 1250)}ms` }}
        >
          {word}
          {index < words.length - 1 ? ' ' : ''}
        </span>
      ))}
    </p>
  );
}

export function RunTimeline({ events, mode, status }: Props) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;

    window.requestAnimationFrame(() => {
      if (typeof list.scrollTo === 'function') {
        list.scrollTo({
          top: list.scrollHeight,
          behavior: events.length > 1 ? 'smooth' : 'auto',
        });
        return;
      }
      list.scrollTop = list.scrollHeight;
    });
  }, [events.length]);

  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <div className="panel-heading">
        <Clock3 size={18} aria-hidden="true" />
        <h2 id="timeline-title">Agent Timeline</h2>
      </div>
      <div className="timeline-signal" data-status={status.toLowerCase().replace(' ', '-')}>
        <span className="signal-dot" aria-hidden="true" />
        <span>{timelineSignal(mode, status, events)}</span>
      </div>
      <div className="timeline-list" ref={listRef}>
        {events.map((event) => (
          <article className="timeline-event" data-type={event.type} key={event.sequence}>
            <div className="event-icon">{eventIcon(event.type)}</div>
            <div>
              <div className="event-row">
                <strong>{event.title}</strong>
                <span>#{event.sequence}</span>
              </div>
              <TokenizedMessage text={event.message} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
