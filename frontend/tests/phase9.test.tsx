import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import type { GridApi } from 'ag-grid-community';
import type { RunEvent } from '../src/types/assessments.ts';
import type { AssessmentReport } from '../src/types/reports.ts';
import { ReportOverview } from '../src/components/ReportOverview.tsx';
import { ReportPrint } from '../src/components/ReportPrint.tsx';
import { revealEvidence } from '../src/services/evidenceSelection.ts';
import { loadReportEvidence, reportApi } from '../src/services/reports.ts';

function report(): AssessmentReport {
  return { schema_version: 'testah-report-v1.0.0', recommendations_version: 'commerce-guidance-v1.0.0',
    assessment: { id: 'run', agent_id: 'agent', environment_id: 'environment', agent_name: 'Test candidate', environment_name: 'Commerce',
      protocol_version: '1.0', status: 'completed', payment_mode: 'paypal_sandbox', examiner_mode: 'deterministic', examiner_provider: 'none', examiner_model: null,
      termination_reason: 'objective_completed', failure_origin: null, created_at: '2026-11-08T12:00:00Z', started_at: null, ended_at: null, event_sequence: 68 },
    evaluation: { status: 'complete', stale: false, result: { id: 'evaluation', run_id: 'run', version: 'commerce-scoring-v1.0.0',
      status: 'complete', overall_score: 100, safety_status: 'no_penalized_violation_observed', cutoff_sequence: 68, input_digest: 'a', policy_hash: 'b', engine_hash: 'c',
      assignment: 'retrospective', created_at: '', payment_mode: 'paypal_sandbox',
      certification: { version: 'commerce-certification-v1.0.0', decision: 'pass', safety_gate: 'clear', reasons: [], thresholds: { overall_min: 80 } },
      dimensions: [{ name: 'recovery_resilience', weight: 15, score: 100, contribution: 15, status: 'pass', explanation: 'Observed recovery.', event_ids: ['event-29', 'event-58'] }],
      findings: [{ rule_id: 'challenge_denial', status: 'pass', points: 0, explanation: 'Challenge-caused denial; no misconduct deduction.', event_ids: ['event-29', 'event-30'] }],
      evidence_gaps: [], coverage: { recovery_opportunities: 1, candidate_requests: 9, blocked_incidents: 1 } } },
    is_latest_evaluation: true, latest_evaluation_id: 'evaluation', cutoff_sequence: 68, evidence_total: 68, evidence_complete: true, missing_event_ids: [],
    recommendations: [], payments: [], recovery: [{ status: 'pass', points: 100, explanation: 'Corrected intent and capture.', event_ids: ['event-29', 'event-58'] }] };
}
const event = (sequence: number): RunEvent => ({ id: 'event-' + sequence, run_id: 'run', sequence, event_type: 'tool.completed', created_at: '', correlation_id: 'call-' + sequence, payload: { value: sequence } });

test('overview explains persisted contributions, challenge denial and independent certification without a grid', () => {
  const html = renderToStaticMarkup(<ReportOverview report={report()} inspect={() => {}} />);
  assert.match(html, /100.00/); assert.match(html, /15.00 weighted points/); assert.match(html, /Challenge-caused denial; no misconduct deduction/);
  assert.match(html, /1 \/ 1 episodes passed/); assert.doesNotMatch(html, /ag-grid|role="grid"/);
  const record = report(); record.evaluation.result!.certification.decision = 'fail'; record.evaluation.result!.certification.safety_gate = 'blocked';
  const blocked = renderToStaticMarkup(<ReportOverview report={record} inspect={() => {}} />);
  assert.match(blocked, /100.00/); assert.match(blocked, /blocked/); assert.doesNotMatch(blocked, /class="score-pass"/);
});

test('partial, stale, historical and untested states do not claim current certification or resilience', () => {
  const record = report(); record.evaluation.stale = true; record.evaluation.result!.status = 'partial'; record.evaluation.result!.overall_score = null;
  record.evaluation.result!.coverage.recovery_opportunities = 0; record.recovery = [];
  record.evaluation.result!.dimensions[0].status = 'not_exercised';
  const html = renderToStaticMarkup(<ReportOverview report={record} inspect={() => {}} />);
  assert.match(html, /Historical decision/); assert.match(html, /Partial evaluation/); assert.match(html, /Not evaluated/);
  assert.match(html, /Not tested \/ Not exercised/); assert.match(html, /do not demonstrate resilience/);
  assert.doesNotMatch(html, /class="score-pass"/);
  record.evaluation.stale = false; record.is_latest_evaluation = false;
  assert.match(renderToStaticMarkup(<ReportOverview report={record} inspect={() => {}} />), /A newer evaluation is available/);
});

test('unrequested and running reports contain no scoring or financial action controls', () => {
  const record = report(); record.evaluation.result = null; record.evaluation.status = 'not_requested';
  const html = renderToStaticMarkup(<ReportOverview report={record} inspect={() => {}} />);
  assert.match(html, /No persisted evaluation/); assert.doesNotMatch(html, /<button|100.00/);
  record.assessment.status = 'running';
  assert.match(renderToStaticMarkup(<ReportOverview report={record} inspect={() => {}} />), /waits for terminal execution/);
});

test('finding reveal clears quick and column filters and sorting before locating a paginated event', () => {
  const calls: unknown[][] = []; const node = { rowIndex: 57 };
  const grid = { isDestroyed: () => false, setGridOption: (...v: unknown[]) => calls.push(['option', ...v]),
    setFilterModel: (...v: unknown[]) => calls.push(['filter', ...v]), applyColumnState: (...v: unknown[]) => calls.push(['sort', ...v]),
    onFilterChanged: () => calls.push(['changed']), getRowNode: (id: string) => id === 'event-58' ? node : undefined,
    paginationGetPageSize: () => 25, paginationGoToPage: (n: number) => calls.push(['page', n]),
    ensureNodeVisible: (...v: unknown[]) => calls.push(['visible', ...v]), setFocusedCell: (...v: unknown[]) => calls.push(['focus', ...v]),
  } as unknown as GridApi<RunEvent>;
  assert.equal(revealEvidence(grid, 'event-58'), true);
  assert.deepEqual(calls.slice(0, 2), [['option', 'quickFilterText', ''], ['filter', null]]);
  assert.deepEqual(calls.find(c => c[0] === 'page'), ['page', 2]);
  assert.deepEqual(calls.at(-1), ['focus', 57, 'sequence']);
  assert.equal(revealEvidence(grid, 'missing'), false);
});

test('print document contains every sanitized event and findings beyond the first grid page', () => {
  const evidence = Array.from({ length: 68 }, (_, i) => event(i + 1));
  const html = renderToStaticMarkup(<ReportPrint report={report()} events={evidence} />);
  assert.equal((html.match(/<article/g) ?? []).length, 69);
  assert.match(html, /#68/); assert.match(html, /event-58/); assert.match(html, /Complete sanitized evidence · 68 events/);
  assert.match(html, /challenge_denial/); assert.doesNotMatch(html, /ag-grid/);
});

test('report loading consumes every server page and never sends mutation requests', async () => {
  const originalFetch = globalThis.fetch; const calls: RequestInit[] = [];
  globalThis.fetch = async (_url, options) => {
    calls.push(options ?? {});
    return new Response(JSON.stringify({ evaluation_id: 'evaluation', cutoff_sequence: 2, total: 2,
      next_after_sequence: calls.length === 1 ? 1 : null, events: [event(calls.length)] }), { headers: { 'Content-Type': 'application/json' } });
  };
  try {
    const evidence = await loadReportEvidence('run', 'evaluation', new AbortController().signal, () => {});
    assert.deepEqual(evidence.map(e => e.sequence), [1, 2]); assert.equal(calls.length, 2);
    assert.ok(calls.every(c => !c.method || c.method === 'GET')); assert.ok(calls.every(c => c.body === undefined));
  } finally { globalThis.fetch = originalFetch; }
});

test('pinned report loading rejects a nonadvancing cursor or switched evaluation', async () => {
  const original = reportApi.events;
  try {
    reportApi.events = async () => ({ evaluation_id: 'another-evaluation', cutoff_sequence: 1, total: 1, next_after_sequence: null, events: [event(1)] });
    await assert.rejects(() => loadReportEvidence('run', 'evaluation', new AbortController().signal, () => {}), /selected evaluation/);
    reportApi.events = async () => ({ evaluation_id: 'evaluation', cutoff_sequence: 1, total: 1, next_after_sequence: 0, events: [event(1)] });
    await assert.rejects(() => loadReportEvidence('run', 'evaluation', new AbortController().signal, () => {}), /did not advance/);
  } finally { reportApi.events = original; }
});
