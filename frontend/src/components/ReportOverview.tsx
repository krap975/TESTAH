import type { AssessmentReport } from '../types/reports';

export const dimensionNames: Record<string, string> = { task_completion: 'Task completion', financial_correctness: 'Financial correctness',
  policy_compliance: 'Policy compliance', recovery_resilience: 'Recovery & resilience', execution_efficiency: 'Execution efficiency' };
export const readable = (value: string) => value.replaceAll('_', ' ');
export const scoreNumber = (value: number | null) => value === null ? 'Not evaluated' : value.toFixed(2);
export function money(minor: number | null, currency: string | null): string {
  if (minor === null || !currency) return 'Amount not recorded';
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(minor / 100) + ' ' + currency; }
  catch { return (minor / 100).toFixed(2) + ' ' + currency + ' (unrecognized currency)'; }
}

export function ReportOverview({ report, inspect, evidenceReady = true }: { report: AssessmentReport; inspect: (ids: string[]) => void; evidenceReady?: boolean }) {
  const result = report.evaluation.result;
  if (!result) return <section className="panel report-empty"><h2>Report not available yet</h2>
    <p>{['created', 'running'].includes(report.assessment.status) ? 'Final reporting waits for terminal execution and a persisted evaluation.' :
      report.evaluation.status === 'pending' ? 'Evaluation is pending. Refresh this report after scoring completes.' : report.evaluation.status === 'error' ?
      'Evaluation could not complete. Review the assessment’s evaluation status.' : 'No persisted evaluation has been requested for this assessment.'}</p>
    <p>Opening this page does not request scoring or perform any payment operation.</p></section>;
  const recovered = report.recovery.filter(r => r.status === 'pass').length;
  return <>
    {(report.evaluation.stale || !report.is_latest_evaluation) && <p role="status" className="report-notice">Historical evaluation · {report.evaluation.stale ? 'Newer execution evidence exists.' : 'A newer evaluation is available.'} The score below describes evidence through #{result.cutoff_sequence}.</p>}
    {result.status === 'partial' && <p role="status" className="report-notice">Partial evaluation · A final overall score is unavailable. Proven findings remain visible; missing outcomes are not treated as agent failures.</p>}
    <section className="report-hero" aria-label="Assessment performance overview">
      <div className="report-score"><p className="eyebrow">OVERALL PERFORMANCE</p><div className="report-score-value">{scoreNumber(result.overall_score)}{result.overall_score !== null && <span> / 100</span>}</div>
        <p>{report.assessment.agent_name}</p><p className="muted">{report.assessment.environment_name}</p></div>
      <div className="report-verdict"><p className="eyebrow">WORKFLOW CERTIFICATION</p><h2 className={result.certification.decision === 'pass' && !report.evaluation.stale && report.is_latest_evaluation ? 'score-pass' : 'score-attention'}>
        {report.evaluation.stale || !report.is_latest_evaluation ? 'Historical decision: ' : ''}{readable(result.certification.decision)}</h2>
        <p>Safety gate: <strong>{readable(result.certification.safety_gate)}</strong></p><p>{readable(result.safety_status)}</p>
        <p className="form-help">Certification applies only to the observed supported commerce workflow.</p></div>
    </section>
    <div className="report-fact-strip"><div><span>Execution</span><strong>{readable(report.assessment.status)}</strong></div><div><span>Payment evidence</span><strong>{result.payment_mode === 'paypal_sandbox' ? 'PayPal Sandbox' : 'Simulation'}</strong></div>
      <div><span>Recovery</span><strong>{result.coverage.recovery_opportunities === 0 ? 'Not tested' : `${recovered} / ${result.coverage.recovery_opportunities} episodes passed`}</strong></div><div><span>Evidence cutoff</span><strong>#{result.cutoff_sequence}</strong></div></div>
    <section className="panel report-section" aria-label="Five scoring dimensions"><div className="report-section-heading"><div><p className="eyebrow">SCORE BREAKDOWN</p><h2>What contributed to the result</h2></div></div>
      <p className="form-help">Values come directly from the stored evaluation. Rounded contributions may differ slightly from the final overall total.</p>
      <div className="dimension-chart" role="list">{result.dimensions.map(d => <div className="dimension-row" role="listitem" key={d.name}>
        <div><strong>{dimensionNames[d.name] ?? readable(d.name)}</strong><span>{d.weight}% weight · {d.status === 'not_exercised' ? 'Not tested / Not exercised' : readable(d.status)}</span></div>
        <div className="dimension-track" aria-hidden="true">{d.score !== null && <span style={{ width: Math.max(0, Math.min(100, d.score)) + '%' }} />}</div>
        <div className="dimension-value"><strong>{scoreNumber(d.score)}</strong><span>{scoreNumber(d.contribution)} weighted points</span></div>
        <button className="screen-only" disabled={!evidenceReady || !d.event_ids.length} onClick={() => inspect(d.event_ids)}>Evidence</button><p className="dimension-explanation">{d.explanation}</p>
      </div>)}</div>
      <p className="form-help">Recovery opportunities: {result.coverage.recovery_opportunities}. Zero opportunities receive neutral credit and do not demonstrate resilience. Candidate requests: {result.coverage.candidate_requests ?? 'Not recorded'}.</p>
    </section>
    <section className="panel report-section" aria-label="Policy and safety interpretation"><p className="eyebrow">POLICY & SAFETY</p><h2>Understand the safety decision</h2>
      <p>{readable(result.safety_status)} · {result.coverage.blocked_incidents ?? 'Not recorded'} blocked incident(s). A block is not proof of an executed unsafe action.</p>
      {result.findings.filter(f => f.rule_id === 'challenge_denial').map((f, i) => <div className="report-callout" key={i}><strong>Environmental disruption</strong><p>{f.explanation}</p><button className="screen-only" disabled={!evidenceReady} onClick={() => inspect(f.event_ids)}>Inspect challenge and original denial</button></div>)}
      <details><summary>Certification thresholds and decision reasons</summary><p>{result.certification.version}</p>
        <dl className="report-thresholds">{Object.entries(result.certification.thresholds).map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>{value}</dd></div>)}</dl>
        <p>Complete evidence and successful execution are required. Confirmed critical unsafe financial actions independently block certification.</p>
        {result.certification.reasons.length > 0 && <ul>{result.certification.reasons.map(reason => <li key={reason}>{readable(reason)}</li>)}</ul>}</details>
      {result.evidence_gaps.length > 0 && <div className="report-callout"><strong>Evidence gaps</strong><ul>{result.evidence_gaps.map(gap => <li key={gap}>{readable(gap)}</li>)}</ul></div>}
    </section>
  </>;
}
