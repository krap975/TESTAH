import { test } from 'node:test';
import assert from 'node:assert/strict';
import { apiRequest } from '../src/services/api.ts';
import { watchAssessment } from '../src/services/assessmentStream.ts';
import { setWorkspaceToken } from '../src/services/workspaceAccess.ts';

test('workspace access travels in headers and preserves separate payment authority', async () => {
  const original = globalThis.fetch;
  const calls: Array<{ url: string; headers: Headers }> = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), headers: new Headers(init?.headers) });
    return Response.json({ ok: true });
  };
  try {
    setWorkspaceToken('synthetic-workspace-access');
    await apiRequest('/api/assessments/test/payments', { headers: { Authorization: 'Bearer synthetic-payment-access' } });
    assert.equal(calls[0].headers.get('X-Testah-Workspace-Token'), 'synthetic-workspace-access');
    assert.equal(calls[0].headers.get('Authorization'), 'Bearer synthetic-payment-access');
    assert.ok(!calls[0].url.includes('synthetic'));
    setWorkspaceToken('');
    await apiRequest('/api/agents');
    assert.equal(calls[1].headers.get('X-Testah-Workspace-Token'), null);
  } finally { setWorkspaceToken(''); globalThis.fetch = original; }
});

test('SSE carries workspace access separately from its monitoring token', async () => {
  setWorkspaceToken('synthetic-workspace-access');
  const errors: string[] = [];
  try {
    await watchAssessment('test-run', 'synthetic-monitor-access', new AbortController().signal, {
      onStatus: () => {}, onRun: () => {}, onEvent: () => {}, onError: message => errors.push(message),
    }, { fetcher: async (url, init) => {
      const headers = new Headers(init?.headers);
      assert.equal(headers.get('X-Testah-Workspace-Token'), 'synthetic-workspace-access');
      assert.equal(headers.get('Authorization'), 'Bearer synthetic-monitor-access');
      assert.ok(!String(url).includes('synthetic'));
      return Response.json({ error: { code: 'monitor_not_configured' } }, { status: 503 });
    } });
    assert.ok(errors.some(message => message.includes('Monitoring is not configured')));
  } finally { setWorkspaceToken(''); }
});
