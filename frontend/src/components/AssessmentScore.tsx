import type { Assessment } from '../types/assessments';

const names: Record<string, string> = { task_completion: 'Task completion', financial_correctness: 'Financial correctness',
  policy_compliance: 'Policy compliance', recovery_resilience: 'Recovery and resilience', execution_efficiency: 'Execution efficiency' };
const readable = (text: string) => text.replaceAll('_', ' ');
const number = (value: number | null) => value === null ? 'Not evaluated' : value.toFixed(2);

export function AssessmentScore({ run, requestScore, busy = false }: { run: Assessment; requestScore?: () => void; busy?: boolean }) {
  const state = run.evaluation; const result = state?.result;
  const terminal = !['created', 'running'].includes(run.status);
  return <section className="assessment-score" aria-label="Deterministic assessment scoring">
    <h3>Deterministic assessment score</h3>
    {!terminal && <p>Scoring waits for terminal execution evidence.</p>}
    {terminal && (!state || state.status === 'not_requested') && <p>No evaluation has been requested. Historical results use a retrospective rubric assignment.</p>}
    {terminal && state?.status === 'pending' && <p role="status">Evaluation pending. Recorded evidence is being scored.</p>}
    {state?.status === 'error' && <p role="alert">Evaluation could not be completed. Required inputs may be unsupported or invalid. Retry after resolving the evidence issue.</p>}
    {state?.stale && <p role="status">This evaluation covers earlier evidence. A newer result is pending or requires an explicit evaluation request.</p>}
    {terminal && requestScore && state?.status !== 'pending' && (!result || state?.stale || state?.status === 'error') &&
      <button disabled={busy} onClick={requestScore}>{busy ? 'Requesting evaluation…' : 'Evaluate recorded evidence'}</button>}
    {result && <>
      <div className="score-summary"><div><span>Performance</span><strong>{result.overall_score === null ? 'Not evaluated' : number(result.overall_score) + ' / 100'}</strong></div>
        <div><span>Certification</span><strong className={result.certification.decision === 'pass' && !state?.stale ? 'score-pass' : 'score-attention'}>{state?.stale ? 'Outdated result' : readable(result.certification.decision)}</strong></div></div>
      <p>Safety gate: <strong>{readable(result.certification.safety_gate)}</strong> · {readable(result.safety_status)}</p>
      <p className="form-help">{result.payment_mode === 'paypal_sandbox' ? 'PayPal Sandbox evidence' : 'Simulated payment evidence'} · {result.version} · {result.assignment === 'retrospective' ? 'Retrospective evaluation' : 'Rubric assigned before execution'} · Evidence through #{result.cutoff_sequence}</p>
      <div className="score-table-wrap"><table className="score-table"><thead><tr><th>Dimension</th><th>Weight</th><th>Score</th><th>Contribution</th></tr></thead><tbody>
        {result.dimensions.map(dimension => <tr key={dimension.name}><td><strong>{names[dimension.name] ?? readable(dimension.name)}</strong>
          <p>{dimension.status === 'not_exercised' ? 'Not tested / Not exercised' : readable(dimension.status)}</p><p>{dimension.explanation}</p></td>
          <td>{dimension.weight}%</td><td>{number(dimension.score)}</td><td>{number(dimension.contribution)}</td></tr>)}
      </tbody></table></div>
      <p className="form-help">Recovery opportunities: {result.coverage.recovery_opportunities}. Neutral recovery credit with zero opportunities does not demonstrate resilience. Certification covers only this observed commerce workflow.</p>
      <details><summary>Certification thresholds and decision reasons</summary><p>{result.certification.version}</p>
        <p>Overall ≥ {result.certification.thresholds.overall_min}; task ≥ {result.certification.thresholds.task_min}; financial ≥ {result.certification.thresholds.financial_min}; policy ≥ {result.certification.thresholds.policy_min}; recovery ≥ {result.certification.thresholds.recovery_min}. Complete evidence and successful execution are required. Confirmed critical unsafe financial actions always block certification.</p>
        {result.certification.reasons.length > 0 && <ul>{result.certification.reasons.map(reason => <li key={reason}>{readable(reason)}</li>)}</ul>}
      </details>
      <details><summary>Scoring findings and evidence</summary><ul className="score-findings">{result.findings.map((finding, index) => <li key={finding.rule_id + index}>
        <strong>{readable(finding.rule_id)} · {readable(finding.status)}</strong>{finding.points !== 0 && <span> · {finding.points > 0 ? '+' : ''}{finding.points} rule points</span>}
        <p>{finding.explanation}</p><div className="score-evidence">{finding.event_ids.map(id => <a key={id} href={'#event-' + id}>Event {id}</a>)}</div>
      </li>)}</ul></details>
      <details><summary>Audit identifiers</summary><p>Evaluation {result.id}</p><p>Input SHA-256: {result.input_digest}</p><p>Policy SHA-256: {result.policy_hash}</p><p>Evaluator SHA-256: {result.engine_hash ?? 'Not recorded'}</p></details>
    </>}
  </section>;
}
