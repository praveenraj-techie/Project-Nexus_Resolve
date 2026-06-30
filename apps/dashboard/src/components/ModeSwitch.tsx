import { Activity, PlayCircle, Radio } from 'lucide-react';
import type { Mode } from '../types';

type Props = {
  mode: Mode;
  backendOnline: boolean;
  onModeChange: (mode: Mode) => void;
  onStartLive: () => void;
};

export function ModeSwitch({
  mode,
  backendOnline,
  onModeChange,
  onStartLive,
}: Props) {
  return (
    <div className="mode-switch" aria-label="Mode switch">
      <button
        className={mode === 'replay' ? 'active' : ''}
        type="button"
        onClick={() => onModeChange('replay')}
      >
        <PlayCircle size={16} aria-hidden="true" />
        Replay
      </button>
      <button
        className={mode === 'live' ? 'active' : ''}
        type="button"
        onClick={() => onModeChange('live')}
      >
        <Radio size={16} aria-hidden="true" />
        Live
      </button>
      <button
        className="start-run"
        type="button"
        onClick={onStartLive}
        disabled={mode !== 'live' || !backendOnline}
      >
        <Activity size={16} aria-hidden="true" />
        Start
      </button>
    </div>
  );
}

