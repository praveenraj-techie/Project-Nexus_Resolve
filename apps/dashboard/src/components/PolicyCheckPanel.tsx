import { ShieldCheck } from 'lucide-react';
import type { PolicyCheck } from '../types';

type Props = {
  checks: PolicyCheck[];
  backendOnline: boolean;
  demoChecks: PolicyCheck[];
  demoError?: string;
  demoLoading: boolean;
  simulationStarted: boolean;
  onLoadDemo: () => void;
};

export function PolicyCheckPanel({
  backendOnline,
  checks,
  demoChecks,
  demoError,
  demoLoading,
  simulationStarted,
  onLoadDemo,
}: Props) {
  const protectedBlock =
    demoChecks.find((check) => check.name === 'Target scope') ?? demoChecks[0];
  const showDemo = simulationStarted || demoChecks.length > 0 || demoLoading || Boolean(demoError);

  return (
    <section className="panel policy-panel" aria-labelledby="policy-title">
      <div className="panel-heading">
        <ShieldCheck size={18} aria-hidden="true" />
        <h2 id="policy-title">Policy Checks</h2>
      </div>
      <div className="check-list">
        {checks.length === 0 ? (
          <article className="check-row" data-status="pending">
            <span>pending</span>
            <div>
              <strong>Policy checks pending</strong>
              <p>Start the simulation to run target scope, safeguards, dry-run, approval, validation, and mock-only checks.</p>
            </div>
          </article>
        ) : null}
        {checks.map((check) => (
          <article className="check-row" data-status={check.status} key={check.name}>
            <span>{check.status.replace('_', ' ')}</span>
            <div>
              <strong>{check.name}</strong>
              <p>{check.message}</p>
            </div>
          </article>
        ))}
        {showDemo ? (
          <>
            <div className="policy-demo-card">
              <div>
                <strong>Protected-Resource Block Demo</strong>
                <p>
                  Fetches the real backend policy response for a blocked
                  C:\Windows\System32 remediation plan.
                </p>
              </div>
              <button type="button" onClick={onLoadDemo} disabled={!backendOnline || demoLoading}>
                {demoLoading ? 'Checking...' : 'Show Real Block'}
              </button>
              {!backendOnline ? <span>Backend offline: start local live mode to fetch the API.</span> : null}
              {demoError ? <span className="policy-demo-error">{demoError}</span> : null}
            </div>
            {protectedBlock ? (
              <article className="check-row policy-demo-result" data-status={protectedBlock.status}>
                <span>{protectedBlock.status.replace('_', ' ')}</span>
                <div>
                  <strong>{protectedBlock.name}</strong>
                  <p>{protectedBlock.message}</p>
                </div>
              </article>
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}
