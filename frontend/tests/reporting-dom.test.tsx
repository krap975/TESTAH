import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import type { GridApi } from 'ag-grid-community';
import type { RunEvent } from '../src/types/assessments.ts';

// Exercise the real Community grid model and React effects, beyond static markup.
const dom = new JSDOM('<!doctype html><html lang="en"><head><title>Reporting tests</title></head><body></body></html>', { url: 'http://localhost', pretendToBeVisual: true });
for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'NodeList', 'HTMLDivElement', 'HTMLInputElement', 'HTMLSelectElement', 'HTMLButtonElement', 'MutationObserver', 'DOMParser', 'Event', 'MouseEvent', 'KeyboardEvent', 'getComputedStyle', 'DocumentFragment', 'ShadowRoot'] as const) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
}
Object.defineProperty(globalThis, 'requestAnimationFrame', { value: dom.window.requestAnimationFrame.bind(dom.window), configurable: true });
Object.defineProperty(globalThis, 'cancelAnimationFrame', { value: dom.window.cancelAnimationFrame.bind(dom.window), configurable: true });
Object.defineProperty(globalThis, 'ResizeObserver', { value: class { observe() {} unobserve() {} disconnect() {} }, configurable: true });
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { value: true, configurable: true, writable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, 'clientWidth', { get() { return 1100; }, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, 'clientHeight', { get() { return 450; }, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, 'offsetWidth', { get() { return 1100; }, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, 'offsetHeight', { get() { return 46; }, configurable: true });
dom.window.HTMLElement.prototype.scrollIntoView = () => {};
const { render, cleanup, fireEvent, waitFor, act } = await import('@testing-library/react');
const { EvidenceGrid } = await import('../src/components/EvidenceGrid.tsx');
const { ReportingGrid } = await import('../src/components/ReportingGrid.tsx');
const { revealEvidence } = await import('../src/services/evidenceSelection.ts');
afterEach(cleanup);
const events: RunEvent[] = Array.from({ length: 68 }, (_, index) => ({ id: 'event-' + (index + 1), run_id: 'run', sequence: index + 1,
  created_at: '2026-11-08T12:00:00Z', event_type: index === 57 ? 'payment.captured' : 'tool.completed', correlation_id: 'call-' + index, payload: { status: 'completed' } }));

test('actual grid clears hidden filters and descending sort, then displays the correct pagination page', async () => {
  let api: GridApi<RunEvent> | undefined;
  render(<ReportingGrid rows={events} columns={[{ field: 'sequence', filter: 'agNumberColumnFilter' }, { field: 'id' }]} rowId={r => r.id} label="Pagination test" ready={value => { api = value; }} />);
  await waitFor(() => assert.equal(api?.getDisplayedRowCount(), 68));
  await act(async () => {
    api!.setGridOption('quickFilterText', 'event-1');
    api!.setFilterModel({ sequence: { filterType: 'number', type: 'equals', filter: 1 } });
    api!.applyColumnState({ state: [{ colId: 'sequence', sort: 'desc' }] });
    api!.onFilterChanged();
  });
  assert.ok(api!.getDisplayedRowCount() < 68);
  await act(async () => { assert.equal(revealEvidence(api!, 'event-58'), true); });
  assert.equal(api!.getDisplayedRowCount(), 68); assert.equal(api!.paginationGetCurrentPage(), 2);
  assert.equal(api!.getFocusedCell()?.rowIndex, 57);
  assert.equal(api!.getColumnState().find(c => c.colId === 'sequence')?.sort, 'asc');
});

test('finding selection and repeated selection reveal supporting events despite existing search', async () => {
  const ids = ['event-58', 'event-68'];
  const view = render(<EvidenceGrid events={events} />);
  fireEvent.change(view.getByRole('textbox', { name: 'Search evidence' }), { target: { value: 'cannot-match-any-row' } });
  view.rerender(<EvidenceGrid events={events} request={{ ids, revision: 1 }} />);
  await waitFor(() => assert.match(view.getByRole('region', { name: 'Selected evidence details' }).textContent!, /#58/));
  assert.equal((view.getByRole('textbox', { name: 'Search evidence' }) as HTMLInputElement).value, '');
  assert.match(view.container.textContent!, /2 \/ 68 loaded events/);
  await waitFor(() => assert.ok(view.getByRole('button', { name: 'Inspect event 58' })));
  fireEvent.change(view.getByRole('textbox', { name: 'Search evidence' }), { target: { value: 'hidden-again' } });
  view.rerender(<EvidenceGrid events={events} request={{ ids, revision: 2 }} />);
  await waitFor(() => assert.ok(view.getByRole('button', { name: 'Inspect event 58' })));
  fireEvent.click(view.getByRole('button', { name: 'Show all evidence / clear filters' }));
  await waitFor(() => assert.match(view.container.textContent!, /68 \/ 68 loaded events/));
});

test('evidence inspection has named controls, keyboard focus targets and no serious automated ARIA violations', async () => {
  const view = render(<main><h1>Evidence inspection</h1><EvidenceGrid events={events} request={{ ids: ['event-58'], revision: 1 }} /></main>);
  await waitFor(() => assert.ok(view.getByRole('button', { name: 'Inspect event 58' })));
  const { default: axe } = await import('axe-core');
  const results = await axe.run(view.container, { rules: { 'color-contrast': { enabled: false } } });
  const serious = results.violations.filter(v => v.impact === 'serious' || v.impact === 'critical');
  assert.deepEqual(serious.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), []);
  assert.ok(view.getByRole('textbox', { name: 'Search evidence' }));
});

test('opening, refreshing, printing and downloading a full report use only GETs and export all hidden rows', async () => {
  const { ReportsPage } = await import('../src/pages/ReportsPage.tsx');
  const { MemoryRouter, Routes, Route } = await import('react-router-dom');
  const model = {
    schema_version: 'testah-report-v1.0.0', recommendations_version: 'commerce-guidance-v1.0.0',
    assessment: { id: 'run', agent_id: 'agent', environment_id: 'env', agent_name: 'DOM test candidate', environment_name: 'Commerce fixture',
      protocol_version: '1.0', status: 'completed', payment_mode: 'paypal_sandbox', examiner_mode: 'deterministic', examiner_provider: 'none', examiner_model: null,
      termination_reason: 'objective_completed', failure_origin: null, created_at: '', started_at: null, ended_at: null, event_sequence: 68 },
    evaluation: { status: 'complete', stale: false, result: { id: 'evaluation', run_id: 'run', version: 'commerce-scoring-v1.0.0', status: 'complete', overall_score: 100,
      safety_status: 'no_penalized_violation_observed', cutoff_sequence: 68, input_digest: 'input-hash', policy_hash: 'policy-hash', engine_hash: 'engine-hash',
      assignment: 'retrospective', created_at: '', payment_mode: 'paypal_sandbox',
      certification: { version: 'commerce-certification-v1.0.0', decision: 'pass', safety_gate: 'clear', reasons: [], thresholds: { overall_min: 80 } },
      dimensions: [{ name: 'recovery_resilience', weight: 15, score: 100, contribution: 15, status: 'pass', explanation: 'Recovered disruption.', event_ids: ['event-58'] }],
      findings: [{ rule_id: 'task_capture', status: 'pass', explanation: 'Recorded capture.', points: 60, event_ids: ['event-58'] }], evidence_gaps: [],
      coverage: { recovery_opportunities: 1, candidate_requests: 9, blocked_incidents: 1 } } },
    is_latest_evaluation: true, latest_evaluation_id: 'evaluation', cutoff_sequence: 68, evidence_total: 68, evidence_complete: true,
    missing_event_ids: [], recommendations: [], payments: [], recovery: [{ status: 'pass', points: 100, explanation: 'Corrected intent and capture.', event_ids: ['event-58'] }],
  };
  const originalFetch = globalThis.fetch; const originalPrint = window.print;
  const originalCreate = URL.createObjectURL; const originalRevoke = URL.revokeObjectURL;
  const originalClick = dom.window.HTMLAnchorElement.prototype.click;
  const requests: { url: string; method: string }[] = []; let prints = 0; let downloaded: Blob | undefined;
  globalThis.fetch = async (url, options) => {
    const path = String(url); requests.push({ url: path, method: options?.method ?? 'GET' });
    let value: unknown;
    if (path.includes('/report/export')) value = { ...model, exported_at: '', evidence: events };
    else if (path.includes('/report/events')) value = { evaluation_id: 'evaluation', cutoff_sequence: 68, total: 68, next_after_sequence: null, events };
    else if (path.includes('/evaluations')) value = [model.evaluation.result];
    else if (path.includes('/report')) value = model;
    else throw new Error('Unexpected operational request: ' + path);
    return new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
  };
  window.print = () => { prints++; };
  URL.createObjectURL = value => { downloaded = value as Blob; return 'blob:test'; };
  URL.revokeObjectURL = () => {};
  dom.window.HTMLAnchorElement.prototype.click = () => {};
  try {
    const view = render(<MemoryRouter initialEntries={['/reports/run']}><Routes><Route path="/reports/:runId" element={<ReportsPage />} /></Routes></MemoryRouter>);
    await waitFor(() => assert.equal((view.getByRole('button', { name: 'Download JSON' }) as HTMLButtonElement).disabled, false));
    const { default: axe } = await import('axe-core');
    let seriousViolations: string[] = [];
    await act(async () => {
      const accessibility = await axe.run(view.container, { rules: { 'color-contrast': { enabled: false } } });
      seriousViolations = accessibility.violations.filter(v => v.impact === 'serious' || v.impact === 'critical').map(v => v.id);
    });
    assert.deepEqual(seriousViolations, []);
    fireEvent.change(view.getByRole('textbox', { name: 'Search evidence' }), { target: { value: 'hides-all-grid-rows' } });
    const beforePrint = requests.length;
    fireEvent.click(view.getByRole('button', { name: 'Print / Save as PDF' }));
    assert.equal(prints, 1); assert.equal(requests.length, beforePrint);
    assert.equal(view.container.querySelectorAll('.report-print article').length, 69);
    await act(async () => { fireEvent.click(view.getByRole('button', { name: 'Download JSON' })); });
    await waitFor(() => assert.ok(downloaded));
    const output = JSON.parse(await downloaded!.text());
    assert.equal(output.evidence.length, 68); assert.equal(output.evidence.at(-1).sequence, 68);
    await act(async () => { fireEvent.click(view.getByRole('button', { name: 'Refresh' })); });
    await waitFor(() => assert.equal((view.getByRole('button', { name: 'Download JSON' }) as HTMLButtonElement).disabled, false));
    assert.ok(requests.every(request => request.method === 'GET'));
    assert.ok(requests.every(request => !/reconcile|evaluate(?:\?|$)|capture/.test(request.url)));
  } finally {
    globalThis.fetch = originalFetch; window.print = originalPrint; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke;
    dom.window.HTMLAnchorElement.prototype.click = originalClick;
  }
});
