import { useState, type FormEvent } from 'react';
import { agentApi } from '../services/agents';
import type { Agent, AgentInput } from '../types/agents';

const LOCAL_URL = 'http://127.0.0.1:9001/agent';
export function AgentForm({ agent, onSaved, onCancel }: { agent?: Agent; onSaved: (agent: Agent) => void; onCancel: () => void }) {
  const [name, setName] = useState(agent?.name ?? '');
  const [description, setDescription] = useState(agent?.description ?? '');
  const [endpoint, setEndpoint] = useState(agent?.endpoint_url ?? '');
  const [mode, setMode] = useState<AgentInput['connection_mode']>(agent?.connection_mode ?? 'external');
  const [authAction, setAuthAction] = useState(agent?.authentication_configured ? 'keep' : 'none');
  const [header, setHeader] = useState<'Authorization' | 'X-API-Key'>('Authorization');
  const [secretKey, setSecretKey] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    if (!name.trim()) { setError('Enter an agent name.'); return; }
    if (mode === 'external') {
      try {
        const url = new URL(endpoint);
        if (url.protocol !== 'https:' || (url.port && url.port !== '443') || url.username || url.password || url.search || url.hash) throw new Error();
      } catch { setError('Use an HTTPS endpoint on port 443 without credentials, query parameters, or a fragment.'); return; }
    }
    const data: AgentInput = { name: name.trim(), description: description.trim(), endpoint_url: mode === 'local_sample' ? LOCAL_URL : endpoint.trim(), connection_mode: mode };
    if (authAction === 'replace') data.authentication = { header_name: header, secret_key: secretKey };
    else if (authAction === 'none') data.authentication = null;
    setBusy(true);
    try { onSaved(agent ? await agentApi.update(agent.id, data) : await agentApi.create(data)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save the agent.'); }
    finally { setBusy(false); }
  }
  return <form className="agent-form" onSubmit={submit} aria-label={agent ? 'Edit agent' : 'Register agent'}>
    <h2>{agent ? 'Edit agent configuration' : 'Register an agent'}</h2>
    <label>Name<input value={name} onChange={e => setName(e.target.value)} required maxLength={100} disabled={busy} autoComplete="off" /></label>
    <label>Description<textarea value={description} onChange={e => setDescription(e.target.value)} maxLength={4000} rows={3} disabled={busy} /></label>
    <label>Connection mode<select value={mode} onChange={e => { const next = e.target.value as AgentInput['connection_mode']; setMode(next); if (next === 'local_sample') setEndpoint(LOCAL_URL); else if (endpoint === LOCAL_URL) setEndpoint(''); }} disabled={busy}><option value="external">External HTTPS agent</option><option value="local_sample">Local sample (development only)</option></select></label>
    {mode === 'local_sample' && <p className="form-help">Requires TESTAH_ALLOW_LOCAL_SAMPLE=true on a development backend. Only the fixed sample endpoint is permitted.</p>}
    <label>Endpoint URL<input type="url" value={mode === 'local_sample' ? LOCAL_URL : endpoint} onChange={e => setEndpoint(e.target.value)} readOnly={mode === 'local_sample'} required maxLength={2048} disabled={busy} placeholder="https://agent.example.com/agent" /></label>
    <p className="form-help">Public HTTPS on port 443. Private destinations and redirects are blocked by the backend.</p>
    <label>Authentication<select value={authAction} onChange={e => setAuthAction(e.target.value)} disabled={busy}>{agent?.authentication_configured && <option value="keep">Keep configured authentication</option>}<option value="none">No authentication / remove existing</option><option value="replace">Use a server-side secret reference</option></select></label>
    {authAction === 'replace' && <><label>Header<select value={header} onChange={e => setHeader(e.target.value as typeof header)} disabled={busy}><option>Authorization</option><option>X-API-Key</option></select></label><label>Server secret key<input value={secretKey} onChange={e => setSecretKey(e.target.value)} required pattern="[A-Z][A-Z0-9_]{0,63}" maxLength={64} placeholder="MY_AGENT" disabled={busy} /></label><p className="form-help">Enter a reference key from TESTAH_AGENT_SECRETS. Configure credential values on the server, never in this form.</p></>}
    {error && <p role="alert" className="form-error">{error}</p>}
    <div className="agent-actions"><button type="submit" className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save agent'}</button><button type="button" onClick={onCancel} disabled={busy}>Cancel</button></div>
  </form>;
}

