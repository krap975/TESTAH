import type { AssessmentReport } from '../types/reports';
import type { RunEvent } from '../types/assessments';
import { dimensionNames, scoreNumber } from './ReportOverview';

/** Ordinary DOM includes every loaded row; never prints a virtualized grid. */
export function ReportPrint({ report, events }: { report: AssessmentReport; events: RunEvent[] }) {
  const result = report.evaluation.result;
  return <div className="print-only report-print" aria-hidden="true">
    <h2>Dimension values</h2><table><thead><tr><th>Dimension</th><th>Weight</th><th>Score</th><th>Weighted points</th></tr></thead><tbody>{result?.dimensions.map(d => <tr key={d.name}><td>{dimensionNames[d.name] ?? d.name}</td><td>{d.weight}%</td><td>{scoreNumber(d.score)}</td><td>{scoreNumber(d.contribution)}</td></tr>)}</tbody></table>
    <h2>All persisted findings</h2>{result?.findings.map((f, i) => <article key={i}><h3>{f.rule_id} · {f.status}</h3><p>{f.explanation} · {f.points} rule points</p><p>Events: {f.event_ids.join(', ') || 'None'}</p></article>)}
    <h2>Audit & reproducibility</h2><p>Run: {report.assessment.id}</p><p>Evaluation: {result?.id} · {result?.created_at}</p><p>Report: {report.schema_version} · Guidance: {report.recommendations_version}</p>
    <p>Rubric: {result?.version} · Certification: {result?.certification.version} · Assignment: {result?.assignment}</p><p>Input SHA-256: {result?.input_digest}</p><p>Policy SHA-256: {result?.policy_hash}</p><p>Evaluator SHA-256: {result?.engine_hash ?? 'Not recorded'}</p>
    <h2>Complete sanitized evidence · {events.length} events</h2><p>Chronological sequence through #{report.cutoff_sequence}. Grid filters and pagination do not affect this document.</p>
    {events.map(event => <article key={event.id}><h3>#{event.sequence} · {event.event_type}</h3><p>{event.created_at} · Event {event.id} · Correlation {event.correlation_id ?? 'None'}</p><pre>{JSON.stringify(event.payload, null, 2)}</pre></article>)}
  </div>;
}
