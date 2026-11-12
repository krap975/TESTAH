import { useState } from 'react';
import { raiApi } from '../services/rai';
import { ApiError } from '../services/api';
import type { ProviderCheck, ProviderDiagnostics } from '../types/rai';

function CheckResult({ label, check }: { label: string; check: ProviderCheck }) {
  return <div className="mt-3"><strong>{label}: {check.status}</strong><p><code>{check.code}</code>
    {check.latency_ms !== null && <> · {check.latency_ms.toFixed(0)} ms</>}
    {check.http_status != null && <> · HTTP {check.http_status}</>}</p>{check.message && <p>{check.message}</p>}</div>;
}

export function RaiProviderDiagnostics() {
  const [result, setResult] = useState<ProviderDiagnostics | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function check() {
    setBusy(true); setError(''); setResult(null);
    try { setResult(await raiApi.diagnostics()); }
    catch (err) { setError(err instanceof ApiError ? err.code + ': ' + err.message : err instanceof Error ? err.message : 'Provider check failed.'); }
    finally { setBusy(false); }
  }
  return <section className="panel agent-form mb-5" aria-label="Development provider diagnostics">
    <h2>Development provider check</h2>
    <p className="form-help">Runs in the current API process. With Gemini configured, this checks HTTPS and makes one small authenticated generation request, which may incur API usage. Checks run only when you press this button.</p>
    <div className="agent-actions"><button type="button" disabled={busy} onClick={() => void check()}>{busy ? 'Checking provider…' : 'Check provider connectivity and authentication'}</button></div>
    {busy && <p role="status">Waiting for the backend check within its configured limits…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {result && <div aria-live="polite"><p>{result.is_mock ? 'MOCK DEVELOPMENT MODE' : result.provider} · {result.model} · API key configured: {result.key_configured ? 'yes' : 'no'}</p>
      <CheckResult label="Outbound HTTPS" check={result.connectivity} /><CheckResult label="Authenticated Gemini generation" check={result.smoke_test} />
      <details className="mt-3"><summary>Effective settings and API runtime</summary><pre>{JSON.stringify({ runtime: result.runtime, limits: result.limits, check_limits: result.check_limits }, null, 2)}</pre></details>
      <p className="form-help">This result applies to API process {result.runtime.pid} at check time. A smoke test does not validate a Designer proposal; review and compile a new proposal separately.</p>
    </div>}
  </section>;
}
