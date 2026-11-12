import { Link } from 'react-router-dom';
import type { Assessment, RunEvent } from '../types/assessments';
import { SandboxCheckout } from './SandboxCheckout';
import { AssessmentScore } from './AssessmentScore';
const date = (value: string | null) => value ? new Date(value).toLocaleString() : 'Not recorded';
export function AssessmentDetails({ run, events, requestScore, busy }: { run: Assessment; events: RunEvent[]; requestScore?: () => void; busy?: boolean }) {
  return <div className="p-6 environment-details">
    <p className="eyebrow">RECORDED EXECUTION / {run.payment_mode === 'paypal_sandbox' ? 'PAYPAL SANDBOX' : 'SIMULATED COMMERCE'}</p><h2 className="text-xl mt-3">Assessment details</h2>
    <Link className="text-sm" to={'/monitor/' + run.id}>Open live monitor / historical replay →</Link>
    <dl className="agent-facts mt-5"><dt>Run ID</dt><dd>{run.id}</dd><dt>Agent</dt><dd><Link to={'/agents/' + run.agent_id}>{run.agent_name}</Link></dd><dt>Environment</dt><dd><Link to={'/environments/' + run.environment_id}>{run.environment_name}</Link></dd><dt>Status</dt><dd>{run.status}</dd><dt>Customer mode</dt><dd>{run.examiner_mode} · {run.examiner_provider === 'mock' ? 'MOCK provider' : run.examiner_provider}{run.examiner_model ? ' / ' + run.examiner_model : ''}</dd><dt>Protocol</dt><dd>{run.protocol_version}</dd><dt>Created</dt><dd>{date(run.created_at)}</dd><dt>Started</dt><dd>{date(run.started_at)}</dd><dt>Ended</dt><dd>{date(run.ended_at)}</dd><dt>Termination</dt><dd>{run.termination_reason ?? 'None'}</dd><dt>Failure origin</dt><dd>{run.failure_origin ?? 'None'}</dd></dl>
    <p className="form-help">Payment mode: {run.payment_mode}. Completion requires a verified purchase and candidate payment inspection. The Examiner cannot approve PayPal payments.</p>
    <div className="agent-actions mt-4"><Link to={'/reports/' + run.id}>Open assessment report</Link><Link to={'/logs?run=' + run.id}>Investigate execution evidence</Link></div>
    <AssessmentScore run={run} requestScore={requestScore} busy={busy} />
    <SandboxCheckout key={run.id} run={run} />
    <section aria-label="Execution events"><h3>Ordered execution events</h3>{events.length === 0 ? <p>No execution events are available.</p> : <ol className="run-events">{events.map(event => <li key={event.id} className={event.event_type === 'policy.violation' ? 'policy-denial' : ''}>
      <details id={'event-' + event.id}><summary>#{event.sequence} · {event.event_type} <span className="muted">{date(event.created_at)}</span></summary><p className="form-help">Event {event.id}{event.correlation_id ? ' · Call ' + event.correlation_id : ''}</p><pre>{JSON.stringify(event.payload, null, 2)}</pre></details>
    </li>)}</ol>}</section>
  </div>;
}
