import { Layers3 } from 'lucide-react';
import type { ScenarioSummary } from '../types';

type Props = {
  scenarios: ScenarioSummary[];
  selectedScenarioId: string;
  onChange: (scenarioId: string) => void;
};

export function ScenarioSelector({
  scenarios,
  selectedScenarioId,
  onChange,
}: Props) {
  return (
    <label className="scenario-selector">
      <span>
        <Layers3 size={16} aria-hidden="true" />
        Scenario
      </span>
      <select
        value={selectedScenarioId}
        onChange={(event) => onChange(event.target.value)}
      >
        {scenarios.map((scenario) => (
          <option key={scenario.scenario_id} value={scenario.scenario_id}>
            {scenario.team} - {scenario.alert_type}
          </option>
        ))}
      </select>
    </label>
  );
}
