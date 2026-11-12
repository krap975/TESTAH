import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { AssessmentLifecycle } from '../src/components/AssessmentLifecycle.tsx';
import { assessmentGraph, describeEvent, eventOutcome } from '../src/services/assessmentGraph.ts';
import { EventHistory, parseRun, parseRunEvent, SseParser, StreamProtocolError, watchAssessment } from '../src/services/assessmentStream.ts';
import type { Assessment, RunEvent, RunStatus } from '../src/types/assessments.ts';

const runId = 'run-1';
const run = (status: RunStatus = 'running', head = 1): Assessment => ({ id: runId, agent_id: 'candidate-1', environment_id: 'environment-1',
  agent_name: 'Synthetic candidate', environment_name: 'Synthetic environment', protocol_version: '1.0', status, payment_mode: 'simulated',
  termination_reason: status === 'running' || status === 'created' ? null : 'fixture_reason', failure_origin: null,
  examiner_mode: 'deterministic', examiner_provider: 'none', examiner_model: null, created_at: '2026-11-04T12:00:00Z',
  started_at: status === 'created' ? null : '2026-11-04T12:00:01Z', ended_at: status === 'running' || status === 'created' ? null : '2026-11-04T12:00:10Z', event_sequence: head });
const event = (sequence: number, type = 'test.recorded', payload: Record<string, unknown> = {}, call: string | null = null): RunEvent => ({
  id: 'event-' + sequence, run_id: runId, sequence, created_at: '2026-11-04T12:00:00Z', event_type: type, correlation_id: call, payload });

test('Sandbox payment graph distinguishes order, buyer wait, capture and failure across replay prefixes', () => {
  const events = [event(1, 'payment.order_created', { provider: 'paypal_sandbox' }), event(2, 'payment.approval_pending'),
    event(3, 'payment.buyer_approved'), event(4, 'payment.capture_requested'), event(5, 'payment.captured', { provider: 'paypal_sandbox' })];
  const label = (count: number) => assessmentGraph(events.slice(0, count)).nodes.find(node => node.id === 'payment')!.data.label;
  assert.match(label(1), /Sandbox order/); assert.doesNotMatch(label(1), /captured/);
  assert.match(label(2), /pending buyer approval/); assert.match(label(4), /capture pending/); assert.match(label(5), /captured/);
  assert.equal(eventOutcome(event(6, 'payment.failed')), 'failed');
  assert.match(assessmentGraph([event(1, 'payment.failed')]).nodes.find(node => node.id === 'payment')!.data.label, /failed/);
  assert.match(describeEvent(events[4]).description, /Sandbox capture verified/);
});
const encode = (type: string, value: unknown, id?: string) => (id ? 'id: ' + id + '\n' : '') + 'event: ' + type + '\ndata: ' + JSON.stringify(value) + '\n\n';
const ev = (value: RunEvent) => encode('assessment_event', value, value.id);
const snapshot = (value: Assessment) => encode('snapshot', { run: value });
const settled = (status: RunStatus, head: number) => encode('settled', { run_id: runId, status, last_sequence: head });
function response(body: string, split = 17): Response {
  const bytes = new TextEncoder().encode(body);
  return new Response(new ReadableStream({ start(controller) {
    for (let i = 0; i < bytes.length; i += split) controller.enqueue(bytes.slice(i, i + split));
    controller.close();
  } }), { headers: { 'content-type': 'text/event-stream' } });
}
function callbacks() {
  const events: RunEvent[] = []; const statuses: string[] = []; const errors: string[] = []; const snapshots: Assessment[] = [];
  return { events, statuses, errors, snapshots, callbacks: { onEvent: (value: RunEvent) => events.push(value),
    onStatus: (value: string) => statuses.push(value), onError: (value: string) => errors.push(value), onRun: (value: Assessment) => snapshots.push(value) } };
}

test('SSE parser handles arbitrary chunk boundaries, CRLF, comments and multiline JSON', () => {
  const received: unknown[] = []; const parser = new SseParser(value => received.push(value));
  const text = ': heartbeat\r\n\r\nid: stable-id\r\nevent: assessment_event\r\ndata: {"a":\r\ndata: 1}\r\n\r\n';
  for (const character of text) parser.feed(character);
  assert.deepEqual(received, [{ id: 'stable-id', event: 'assessment_event', data: '{"a":\n1}' }]);
});
test('SSE parser bounds incomplete frames and rejects null cursors', () => {
  assert.throws(() => new SseParser(() => {}).feed('x'.repeat(262145)), StreamProtocolError);
  assert.throws(() => new SseParser(() => {}).feed('id: bad\0id\n\n'), StreamProtocolError);
});
test('SSE parser accepts a complete CR-only frame at end of stream', () => {
  const received: string[] = []; const parser = new SseParser(value => received.push(value.data));
  parser.feed('event: settled\rdata: {}\r\r'); parser.finish();
  assert.deepEqual(received, ['{}']);
});
test('event history deduplicates stable IDs and keeps canonical contiguous order', () => {
  const history = new EventHistory(runId);
  assert.equal(history.accept(event(1)), true); assert.equal(history.accept(event(1)), false);
  history.accept(event(2)); assert.equal(history.sequence, 2); assert.equal(history.lastId, 'event-2');
  assert.throws(() => history.accept(event(4)), StreamProtocolError);
  assert.throws(() => history.accept({ ...event(2), id: 'conflicting-id' }), StreamProtocolError);
  assert.throws(() => history.accept({ ...event(2), payload: { changed: true } }), StreamProtocolError);
  assert.equal(history.sequence, 2);
});
test('event validation rejects malformed or cross-assessment events before advancing cursors', () => {
  for (const invalid of [{ ...event(1), run_id: 'other' }, { ...event(1), sequence: 1.5 }, { ...event(1), payload: [] },
    { ...event(1), created_at: 'not-a-date' }, { ...event(1), id: 'different' }]) {
    assert.throws(() => parseRunEvent(invalid, runId, 'event-1'), StreamProtocolError);
  }
  assert.throws(() => parseRun({ ...run(), status: 'assumed_ready' }, runId), StreamProtocolError);
});
test('history is bounded and never silently truncates an accepted prefix', () => {
  const history = new EventHistory(runId);
  for (let i = 1; i <= 5000; i++) history.accept(event(i));
  assert.throws(() => history.accept(event(5001)), /display limit/);
  assert.equal(history.sequence, 5000);
});
test('Fetch stream authenticates by header, reconstructs history, resumes and deduplicates reconnects', async () => {
  const recorded = callbacks(); const calls: Array<{ url: string; headers: Headers }> = []; const controller = new AbortController();
  const token = 'separate-monitoring-token';
  const fetcher: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), headers: new Headers(init?.headers) });
    assert.equal(init?.credentials, 'omit');
    return calls.length === 1 ? response(snapshot(run()) + ev(event(1))) :
      response(snapshot(run('completed', 3)) + ev(event(1)) + ev(event(2)) + ev(event(3, 'assessment.finished', { status: 'completed' })) + settled('completed', 3));
  };
  await watchAssessment(runId, token, controller.signal, recorded.callbacks, { fetcher, wait: async () => {} });
  assert.deepEqual(recorded.events.map(item => item.sequence), [1, 2, 3]);
  assert.equal(calls.length, 2); assert.equal(calls[1].headers.get('Last-Event-ID'), 'event-1');
  assert.match(calls[1].url, /after_sequence=1/); assert.ok(calls.every(call => !call.url.includes(token)));
  assert.equal(calls[0].headers.get('Authorization'), 'Bearer ' + token);
  assert.equal(recorded.statuses.at(-1), 'settled'); assert.ok(recorded.statuses.includes('reconnecting'));
});
test('a refresh reconstructs historical evidence without starting execution', async () => {
  const recorded = callbacks(); const urls: string[] = [];
  await watchAssessment(runId, 'token', new AbortController().signal, recorded.callbacks, { fetcher: async (url, options) => {
    urls.push(String(url)); assert.equal(options?.method, undefined);
    return response(snapshot(run('cancelled')) + ev(event(1, 'assessment.finished', { status: 'cancelled' })) + settled('cancelled', 1));
  } });
  assert.equal(urls.length, 1); assert.match(urls[0], /after_sequence=0/); assert.ok(!urls[0].includes('/start'));
  assert.equal(recorded.statuses.at(-1), 'settled');
});
test('malformed event JSON stops safely without reconnect loops or accepted events', async () => {
  const recorded = callbacks(); let calls = 0;
  await watchAssessment(runId, 'token', new AbortController().signal, recorded.callbacks, { fetcher: async () => {
    calls++; return response('event: assessment_event\nid: event-1\ndata: {private invalid\n\n');
  } });
  assert.equal(calls, 1); assert.deepEqual(recorded.events, []); assert.equal(recorded.statuses.at(-1), 'error');
  assert.ok(!recorded.errors.join().includes('private invalid'));
});
test('authentication failure is permanent until the operator reconnects', async () => {
  const recorded = callbacks(); let calls = 0;
  await watchAssessment(runId, 'token', new AbortController().signal, recorded.callbacks, { fetcher: async () => {
    calls++; return new Response(JSON.stringify({ error: { code: 'http_401' } }), { status: 401 });
  } });
  assert.equal(calls, 1); assert.equal(recorded.statuses.at(-1), 'error'); assert.match(recorded.errors.at(-1)!, /authentication failed/);
});
test('aborting an idle stream releases its reader and does not reconnect', async () => {
  const recorded = callbacks(); const controller = new AbortController(); let calls = 0;
  const fetcher: typeof fetch = async (_url, options) => {
    calls++;
    return new Response(new ReadableStream({ start(body) {
      options?.signal?.addEventListener('abort', () => body.error(new DOMException('Aborted', 'AbortError')), { once: true });
      setTimeout(() => controller.abort(), 5);
    } }), { headers: { 'content-type': 'text/event-stream' } });
  };
  await watchAssessment(runId, 'token', controller.signal, recorded.callbacks, { fetcher });
  assert.equal(calls, 1); assert.ok(!recorded.statuses.includes('reconnecting'));
});
test('terminal markers cannot settle before the complete canonical event prefix', async () => {
  const recorded = callbacks();
  await watchAssessment(runId, 'token', new AbortController().signal, recorded.callbacks, { fetcher: async () =>
    response(snapshot(run('completed', 2)) + ev(event(1)) + settled('completed', 2)) });
  assert.equal(recorded.statuses.at(-1), 'error'); assert.deepEqual(recorded.events.map(item => item.sequence), [1]);
});

const interactions = [event(1, 'customer.message'), event(2, 'agent.requested', { request_id: 'request-1' }),
  event(3, 'agent.tool_call', { request_id: 'request-1', name: 'get_budget' }, 'call-1'),
  event(4, 'tool.requested', { name: 'get_budget' }, 'call-1'), event(5, 'tool.completed', { name: 'get_budget', result: {} }, 'call-1')];
test('graph has the five fixed service roles and no fabricated interactions for empty history', () => {
  const graph = assessmentGraph([]);
  assert.equal(graph.nodes.length, 5); assert.deepEqual(graph.edges, []); assert.ok(graph.nodes.every(node => node.data.eventIds.length === 0));
  assert.match(graph.nodes.find(node => node.id === 'payment')!.data.label, /Payment Gateway/);
});
test('graph tracks active protocol/tool requests and their recorded completions', () => {
  assert.equal(assessmentGraph(interactions.slice(0, 2)).edges.find(edge => edge.id === 'customer:agent')!.data.outcome, 'active');
  assert.equal(assessmentGraph(interactions.slice(0, 4)).edges.find(edge => edge.id === 'tools:environment')!.data.outcome, 'active');
  const graph = assessmentGraph(interactions);
  assert.equal(graph.edges.find(edge => edge.id === 'agent:tools')!.data.outcome, 'success');
  assert.equal(graph.edges.find(edge => edge.id === 'tools:agent')!.data.outcome, 'success');
  assert.ok(graph.edges.every(edge => edge.data.outcome !== 'active'));
});
test('policy rejection differs from failure and merchant negative findings are successful operations', () => {
  const denied = [...interactions.slice(0, 4), event(5, 'policy.violation', { code: 'budget_exceeded' }, 'call-1'),
    event(6, 'tool.failed', { name: 'get_budget', result: { code: 'budget_exceeded' } }, 'call-1')];
  assert.equal(assessmentGraph(denied).edges.find(edge => edge.id === 'agent:tools')!.data.outcome, 'rejected');
  assert.equal(eventOutcome(event(1, 'tool.failed', { result: { code: 'unavailable_internal_tool' } })), 'failed');
  assert.equal(eventOutcome(event(1, 'tool.completed', { result: { merchant: { verified: false } } })), 'success');
});
test('graph maps actual simulated payments, challenge activation and candidate messages', () => {
  const graph = assessmentGraph([event(1, 'agent.message'), event(2, 'challenge.activated'), event(3, 'payment.captured')]);
  assert.ok(graph.edges.some(edge => edge.id === 'agent:customer'));
  assert.ok(graph.edges.some(edge => edge.id === 'environment:tools'));
  assert.equal(graph.edges.find(edge => edge.id === 'tools:payment')!.data.outcome, 'success');
  assert.match(describeEvent(event(1, 'payment.captured')).description, /Simulated/);
});
test('terminal unfinished operations become interrupted, never invented completions', () => {
  const graph = assessmentGraph([...interactions.slice(0, 4), event(5, 'assessment.finished', { status: 'inconclusive' })]);
  assert.equal(graph.edges.find(edge => edge.id === 'agent:tools')!.data.outcome, 'interrupted');
  assert.ok(!graph.edges.some(edge => edge.id === 'tools:agent'));
});
test('Examiner generation is visibly active only while a persisted request awaits a plan/fallback', () => {
  assert.equal(assessmentGraph([event(1, 'rai.examiner.requested')]).nodes.find(node => node.id === 'customer')!.data.outcome, 'active');
  assert.notEqual(assessmentGraph([event(1, 'rai.examiner.requested'), event(2, 'rai.examiner.fallback')]).nodes.find(node => node.id === 'customer')!.data.outcome, 'active');
});
test('historical reconstruction is deterministic for every selected event prefix', () => {
  const saved = JSON.parse(JSON.stringify(interactions)) as RunEvent[];
  for (let i = 0; i <= saved.length; i++) assert.deepEqual(assessmentGraph(saved.slice(0, i)), assessmentGraph(interactions.slice(0, i)));
  const ids = new Set(interactions.map(item => item.id));
  assert.ok(assessmentGraph(saved).edges.every(edge => edge.data.eventIds.every(id => ids.has(id))));
});
for (const status of ['created', 'running', 'completed', 'failed', 'cancelled', 'inconclusive'] as const) {
  test('lifecycle renders actual ' + status + ' state and recorded metadata', () => {
    const html = renderToStaticMarkup(<AssessmentLifecycle run={run(status)} />);
    assert.match(html, new RegExp('status-' + status)); assert.ok(html.includes(runId)); assert.match(html, /Synthetic candidate/);
    assert.match(html, /Payment mode: simulated/); if (status === 'created') assert.match(html, /never starts execution/);
    if (status !== 'created' && status !== 'running') assert.match(html, /fixture_reason/);
  });
}
test('mock Examiner mode remains explicitly labeled', () => {
  assert.match(renderToStaticMarkup(<AssessmentLifecycle run={{ ...run(), examiner_mode: 'rai', examiner_provider: 'mock', examiner_model: 'deterministic-mock-v1' }} />), /MOCK/);
});
