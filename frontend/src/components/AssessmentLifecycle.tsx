import type { Assessment } from '../types/assessments';
const date = (value: string | null) => value ? new Date(value).toLocaleString() : 'Not recorded';
export function AssessmentLifecycle({ run }: { run: Assessment }) {
  return <section className="panel agent-form mb-5" aria-label="Assessment lifecycle">
    <div className="section-header"><h2>{run.agent_name}</h2><span className={'run-status status-' + run.status}>{run.status}</span></div>
    <dl className="monitor-facts"><dt>Assessment ID</dt><dd>{run.id}</dd><dt>Environment</dt><dd>{run.environment_name}</dd>
      <dt>Customer mode</dt><dd>{run.examiner_mode === 'deterministic' ? 'Deterministic customer' : 'RAI Examiner · ' + run.examiner_provider + (run.examiner_provider === 'mock' ? ' (MOCK)' : '') + ' / ' + run.examiner_model}</dd>
      <dt>Created</dt><dd>{date(run.created_at)}</dd><dt>Started</dt><dd>{date(run.started_at)}</dd><dt>Completed / ended</dt><dd>{date(run.ended_at)}</dd>
      <dt>Termination reason</dt><dd>{run.termination_reason ?? 'None recorded'}</dd><dt>Failure origin</dt><dd>{run.failure_origin ?? 'None recorded'}</dd></dl>
    {run.status === 'created' && <p className="form-help">This assessment has not started. Opening or refreshing the monitor never starts execution.</p>}
    <p className="form-help">Payment mode: {run.payment_mode === 'paypal_sandbox' ? 'PayPal Sandbox (no real money)' : 'simulated'}. Completion is an execution outcome; scoring is not implemented.</p>
  </section>;
}
