import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import type { EvaluationFinding } from '../types/assessments';
import type { EvidenceRequest, ReportList, ReportSummary } from '../types/reports';
import { reportApi } from '../services/reports';
import { useReport } from '../hooks/useReport';
import { ReportingGrid } from '../components/ReportingGrid';
import { EvidenceGrid } from '../components/EvidenceGrid';
import { ReportOverview, money, readable, scoreNumber } from '../components/ReportOverview';
import { ReportPrint } from '../components/ReportPrint';

function ReportsIndex() {
  const [offset, setOffset] = useState(0); const [revision, setRevision] = useState(0);
  const [data, setData] = useState<ReportList | null>(null); const [error, setError] = useState('');
  useEffect(() => { const c = new AbortController(); setData(null); setError('');
    void reportApi.list(offset, c.signal).then(value => { if (!c.signal.aborted) setData(value); }).catch(err => { if (!c.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load reports.'); });
    return () => c.abort(); }, [offset, revision]);
  const columns = useMemo<ColDef<ReportSummary>[]>(() => [
    { field: 'agent_name', headerName: 'Agent', minWidth: 175, cellRenderer: (p: ICellRendererParams<ReportSummary>) => p.data ? <Link className="grid-action" to={'/reports/' + p.data.run_id}>{p.data.agent_name}</Link> : null },
    { field: 'environment_name', headerName: 'Environment', minWidth: 190 },
    { field: 'overall_score', headerName: 'Score / 100', filter: 'agNumberColumnFilter', valueFormatter: p => scoreNumber(p.value ?? null) },
    { field: 'certification', headerName: 'Certification', minWidth: 160, valueGetter: p => p.data?.stale ? 'Historical: ' + (p.data.certification ?? 'Not evaluated') : p.data?.certification ?? 'Not evaluated' },
    { field: 'status', headerName: 'Execution' }, { field: 'evaluation_status', headerName: 'Evaluation' },
    { field: 'payment_mode', headerName: 'Payment mode', minWidth: 150 }, { field: 'rubric', headerName: 'Rubric', minWidth: 210 },
    { field: 'created_at', headerName: 'Assessment created', minWidth: 175, valueFormatter: p => new Date(p.value).toLocaleString() },
  ], []);
  return <><div className="page-heading"><div><p className="eyebrow">DEVELOPER REPORTING</p><h1>Reports</h1><p className="subtitle">Understand performance. Trace every finding to recorded evidence.</p></div><button onClick={() => setRevision(n => n + 1)}>Refresh reports</button></div>
    <section className="panel report-section"><div className="report-section-heading"><h2>Assessment reports</h2><span>{data?.total ?? '…'} saved assessments</span></div>
      <p className="form-help">Scores and decisions are persisted Phase 8 evaluations. Unevaluated assessments have no final report. Column filters apply to the loaded batch.</p>
      {error && <p role="alert" className="form-error">{error}</p>}{!data && !error && <p role="status">Loading reports…</p>}
      {data && <><ReportingGrid rows={data.items} columns={columns} label="Assessment report listings" rowId={r => r.run_id} />
        {data.total === 0 && <p>No saved assessments. Create an assessment to begin.</p>}
        <div className="agent-actions screen-only"><button disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 100))}>Previous batch</button><span>Loaded {offset + (data.items.length ? 1 : 0)}–{offset + data.items.length} of {data.total}</span><button disabled={offset + data.items.length >= data.total} onClick={() => setOffset(n => n + 100)}>Next batch</button></div></>}
    </section></>;
}

function AssessmentReportPage({ runId }: { runId: string }) {
  const [search, setSearch] = useSearchParams(); const evaluationId = search.get('evaluation') ?? undefined;
  const [revision, setRevision] = useState(0); const [request, setRequest] = useState<EvidenceRequest>();
  const [actionError, setActionError] = useState(''); const [exporting, setExporting] = useState(false);
  const state = useReport(runId, evaluationId, revision); const { report, events } = state;
  const result = report?.evaluation.result;
  const evidenceReady = !state.loading && events.length > 0;
  useEffect(() => { setRequest(undefined); setActionError(''); }, [runId, evaluationId, revision]);
  const inspect = useCallback((ids: string[]) => {
    setRequest(previous => ({ ids, revision: (previous?.revision ?? 0) + 1 }));
    document.getElementById('report-evidence')?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }, []);
  const findings = useMemo(() => result?.findings.map((f, index) => ({ ...f, row_id: String(index) })) ?? [], [result]);
  const columns = useMemo<ColDef<EvaluationFinding & { row_id: string }>[]>(() => [
    { field: 'rule_id', headerName: 'Rule', minWidth: 210 }, { field: 'status', headerName: 'Finding', minWidth: 135 },
    { field: 'explanation', headerName: 'Deterministic explanation', minWidth: 350, tooltipField: 'explanation', wrapText: true, autoHeight: true },
    { field: 'points', headerName: 'Rule points', filter: 'agNumberColumnFilter', width: 120, flex: 0 },
    { colId: 'evidence', headerName: 'Evidence', minWidth: 155, sortable: false, filter: false, cellRenderer: (p: ICellRendererParams<EvaluationFinding>) => p.data ?
      <button className="grid-action" disabled={!evidenceReady || !p.data.event_ids.length} onClick={() => inspect(p.data!.event_ids)}>Inspect {p.data.event_ids.length} events</button> : null },
  ], [inspect, evidenceReady]);
  async function download() {
    if (!result || !state.complete) return;
    setExporting(true); setActionError('');
    try {
      const exported = await reportApi.export(runId, result.id);
      const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url;
      a.download = 'testah-report-' + runId + '-' + result.id + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Unable to export report.'); }
    finally { setExporting(false); }
  }
  return <div className="assessment-report"><div className="page-heading"><div><p className="eyebrow">EVIDENCE-BASED ASSESSMENT</p><h1>Assessment report</h1><p className="subtitle">Recorded performance, explained.</p></div>
      <div className="agent-actions screen-only"><Link to="/reports">All reports</Link><button onClick={() => setRevision(n => n + 1)}>Refresh</button>
        <button disabled={!state.complete || exporting} onClick={() => void download()}>{exporting ? 'Preparing JSON…' : 'Download JSON'}</button>
        <button disabled={!state.complete} onClick={() => window.print()}>Print / Save as PDF</button></div></div>
    {state.loading && <p role="status" className="form-help">Loading report evidence… {state.loaded} events loaded.</p>}
    {(state.error || actionError) && <p role="alert" className="form-error">{state.error || actionError}</p>}
    {report && <>
      <div className="report-context"><span>Run {runId}</span><span>{report.assessment.ended_at ? new Date(report.assessment.ended_at).toLocaleString() : 'Execution has not ended'}</span></div>
      <div className="report-selection screen-only"><label>Evaluation snapshot<select value={result?.id ?? ''} onChange={e => setSearch(e.target.value ? { evaluation: e.target.value } : {})}>
        {!result && <option value="">No persisted evaluation</option>}{result && !state.history.some(e => e.id === result.id) && <option value={result.id}>{result.id}</option>}
        {state.history.map(e => <option key={e.id} value={e.id}>#{e.cutoff_sequence} · {scoreNumber(e.overall_score)} · {e.created_at} · {e.id}</option>)}</select></label>
        {!report.is_latest_evaluation && <button onClick={() => setSearch({})}>View latest evaluation</button>}<Link to={'/assessments/' + runId}>Assessment details</Link><Link to={'/monitor/' + runId}>Monitor / replay</Link></div>
      <ReportOverview report={report} inspect={inspect} evidenceReady={evidenceReady} />
      {result && <>
        <p className="report-provenance">{result.version} · {result.assignment === 'retrospective' ? 'Retrospective rubric assignment' : 'Rubric assigned before execution'} · {report.evidence_total} recorded events through #{report.cutoff_sequence}</p>
        {!report.evidence_complete && <p role="alert" className="report-notice">The complete referenced evidence is unavailable. Export and print are disabled. Missing referenced events: {report.missing_event_ids.length}.</p>}
        <nav className="report-jump-nav screen-only" aria-label="Report sections">{[['findings', 'Findings'], ['recovery', 'Recovery'], ['financial', 'Financial verification'], ['improvements', 'Improvements'], ['report-evidence', 'Evidence']].map(([id, title]) => <a key={id} href={'#' + id}>{title}</a>)}</nav>
        <section className="panel report-section screen-only" id="findings"><div className="report-section-heading"><h2>Findings & evidence</h2><span>{findings.length} persisted findings</span></div>
          <p className="form-help">Rule points belong to their dimension; they are not weighted overall points. Select evidence to clear investigation filters and show supporting events.</p>
          <ReportingGrid rows={findings} columns={columns} label="Deterministic findings" rowId={row => row.row_id} /></section>
        <section className="panel report-section" id="recovery"><p className="eyebrow">RECOVERY & RESILIENCE</p><h2>Response to observed disruptions</h2>
          {report.recovery.length === 0 ? <p>Not tested / Not exercised. Neutral recovery credit does not demonstrate resilience.</p> : report.recovery.map((episode, index) => <article className="report-callout" key={index}><h3>Episode {index + 1} · {readable(episode.status)}</h3><p>{episode.explanation}</p><p>{episode.points} recovery rule points</p>
            <ol className="recovery-milestones">{events.filter(event => episode.event_ids.includes(event.id)).map(event => <li key={event.id}><span>#{event.sequence}</span> {readable(event.event_type.replaceAll('.', ' / '))}</li>)}</ol>
            <button className="screen-only" disabled={!evidenceReady} onClick={() => inspect(episode.event_ids)}>Inspect correction and capture milestones</button><p className="print-only">Events: {episode.event_ids.join(', ')}</p></article>)}</section>
        <section className="panel report-section" id="financial"><p className="eyebrow">FINANCIAL TRANSACTION VERIFICATION</p><h2>{result.payment_mode === 'paypal_sandbox' ? 'PayPal Sandbox evidence' : 'Simulated payment evidence'}</h2>
          <p className="form-help">Recorded verification at this evaluation’s cutoff. Scenario authorization, buyer approval and completed capture are distinct. No fresh provider check is performed.</p>
          {report.payments.length === 0 ? <p>No checkout evidence is available at this cutoff.</p> : report.payments.map(payment => <article className="report-payment" key={payment.checkout_id}><div><h3>{money(payment.total_minor, payment.currency)}</h3><span>{payment.provider} · {payment.status ?? 'Status not recorded'}</span></div>
            <dl className="report-audit"><dt>Checkout</dt><dd>{payment.checkout_id}</dd><dt>Order</dt><dd>{payment.order_id ?? 'Not recorded'}</dd><dt>Capture</dt><dd>{payment.capture_id ?? 'Not recorded'}</dd><dt>Exact scenario authorization</dt><dd>{payment.authorization_event_ids.length ? 'Verification recorded' : 'No separate verification event recorded'}</dd><dt>PayPal buyer approval</dt><dd>{result.payment_mode !== 'paypal_sandbox' ? 'Not applicable to simulation' : payment.buyer_approval_event_ids.length ? 'Recorded' : 'Not recorded'}</dd><dt>Recorded capture evidence</dt><dd>{payment.captured_event_ids.length ? 'Present; see deterministic financial findings' : 'Not recorded'}</dd><dt>Candidate payment inspection</dt><dd>{payment.inspection_event_ids.length ? 'Recorded' : 'Not recorded'}</dd></dl>
            <button className="screen-only" disabled={!evidenceReady} onClick={() => inspect(payment.event_ids)}>Inspect payment lifecycle</button><p className="print-only">Events: {payment.event_ids.join(', ')}</p></article>)}
        </section>
        <section className="panel report-section" id="improvements"><p className="eyebrow">DEVELOPER GUIDANCE</p><h2>What to improve</h2>
          {report.recommendations.length === 0 ? <p>No corrective action identified from evaluated findings.</p> : report.recommendations.map(item => <article className="report-callout" key={item.id}><p className="eyebrow">{item.category}</p><h3>{item.title}</h3><p>{item.action}</p><p className="form-help">Source: {item.rule_ids.join(', ')}</p>{item.event_ids.length > 0 && <button className="screen-only" disabled={!evidenceReady} onClick={() => inspect(item.event_ids)}>Inspect supporting evidence</button>}</article>)}
          <p className="form-help">Fixed guidance from persisted findings and coverage · {report.recommendations_version}. No model-generated findings or scores.</p></section>
        <div className="panel report-section screen-only"><EvidenceGrid events={events} request={request} /></div>
        <section className="panel report-section"><details className="report-audit-details"><summary>Audit & reproducibility</summary><dl className="report-audit"><dt>Report schema</dt><dd>{report.schema_version}</dd><dt>Evaluation ID</dt><dd>{result.id}</dd><dt>Evaluation created</dt><dd>{result.created_at}</dd><dt>Certification version</dt><dd>{result.certification.version}</dd><dt>Input SHA-256</dt><dd>{result.input_digest}</dd><dt>Policy SHA-256</dt><dd>{result.policy_hash}</dd><dt>Evaluator SHA-256</dt><dd>{result.engine_hash ?? 'Not recorded'}</dd></dl></details></section>
        {state.complete && <ReportPrint report={report} events={events} />}
      </>}
    </>}
  </div>;
}

export function ReportsPage() { const { runId } = useParams(); return runId ? <AssessmentReportPage key={runId} runId={runId} /> : <ReportsIndex />; }
