import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { AssessmentScore } from '../src/components/AssessmentScore.tsx';
import type { Assessment, EvaluationResult } from '../src/types/assessments.ts';

const result = (): EvaluationResult => ({ id: 'evaluation', run_id: 'run', version: 'commerce-scoring-v1.0.0',
  status: 'complete', overall_score: 100, safety_status: 'no_penalized_violation_observed', cutoff_sequence: 68,
  input_digest: 'a'.repeat(64), policy_hash: 'b'.repeat(64), assignment: 'retrospective', created_at: '2026-11-08T12:00:00Z',
  payment_mode: 'paypal_sandbox', certification: { version: 'commerce-certification-v1.0.0', decision: 'pass', safety_gate: 'clear',
    reasons: [], thresholds: { overall_min: 80, task_min: 100, financial_min: 100, policy_min: 90, recovery_min: 100 } },
  dimensions: [{ name: 'recovery_resilience', weight: 15, score: 100, contribution: 15, status: 'not_exercised',
    explanation: 'Neutral scoring convention; no demonstrated resilience.', event_ids: [] }],
  findings: [{ rule_id: 'task_capture', status: 'pass', explanation: 'Verified capture.', points: 60, event_ids: ['capture-event'] }],
  evidence_gaps: [], coverage: { recovery_opportunities: 0 } });
const run = (value: EvaluationResult | null = null): Assessment => ({ id: 'run', agent_id: 'agent', environment_id: 'env',
  agent_name: 'Candidate', environment_name: 'Environment', protocol_version: '1.0', status: 'completed',
  termination_reason: 'objective_completed', failure_origin: null, payment_mode: 'paypal_sandbox', examiner_mode: 'deterministic',
  examiner_provider: 'none', examiner_model: null, created_at: '', started_at: null, ended_at: null, event_sequence: 68,
  evaluation: { status: value ? 'complete' : 'not_requested', result: value, stale: false } });

test('recovery neutral credit is visibly Not tested and includes opportunity count', () => {
  const html = renderToStaticMarkup(<AssessmentScore run={run(result())} />);
  assert.match(html, /Not tested \/ Not exercised/);
  assert.match(html, /Recovery opportunities: 0/);
  assert.match(html, /does not demonstrate resilience/);
  assert.match(html, /Retrospective evaluation/);
  assert.match(html, /#event-capture-event/);
});

test('numeric score and blocked certification are rendered independently', () => {
  const value = result(); value.certification.decision = 'fail'; value.certification.safety_gate = 'blocked';
  value.certification.reasons = ['critical_unsafe_financial_action'];
  const html = renderToStaticMarkup(<AssessmentScore run={run(value)} />);
  assert.match(html, /100.00 \/ 100/); assert.match(html, /blocked/); assert.match(html, /critical unsafe financial action/);
  assert.doesNotMatch(html, /class="score-pass"/);
});

test('missing, pending and partial evidence never renders a fabricated numeric score', () => {
  assert.match(renderToStaticMarkup(<AssessmentScore run={run()} requestScore={() => {}} />), /Evaluate recorded evidence/);
  const record = run(); record.evaluation!.status = 'pending';
  const pending = renderToStaticMarkup(<AssessmentScore run={record} />);
  assert.match(pending, /Evaluation pending/); assert.doesNotMatch(pending, /100.00/);
  const value = result(); value.overall_score = null; value.certification.decision = 'not_evaluated';
  value.dimensions[0].score = null; value.dimensions[0].contribution = null;
  const partial = renderToStaticMarkup(<AssessmentScore run={run(value)} />);
  assert.match(partial, /Not evaluated/); assert.doesNotMatch(partial, /100.00 \/ 100/);
});

test('stale evaluations do not display a current passing certification', () => {
  const record = run(result()); record.evaluation!.stale = true;
  const html = renderToStaticMarkup(<AssessmentScore run={record} />);
  assert.match(html, /Outdated result/); assert.doesNotMatch(html, /class="score-pass"/);
});

test('created assessments wait for execution rather than claiming an active scoring job', () => {
  const record = run(); record.status = 'created'; record.evaluation!.status = 'pending';
  const html = renderToStaticMarkup(<AssessmentScore run={record} requestScore={() => {}} />);
  assert.match(html, /Scoring waits for terminal execution evidence/);
  assert.doesNotMatch(html, /Recorded evidence is being scored|Evaluate recorded evidence/);
});
