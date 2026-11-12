import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AgentForm } from '../components/AgentForm';
import { agentApi } from '../services/agents';
import type { Agent } from '../types/agents';

const statusLabel = { not_tested: 'Not tested', connected: 'Protocol connected', failed: 'Connection failed' };
export function AgentsPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [detail, setDetail] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState<'create' | 'edit' | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setNotice(''); setDetail(null); setForm(null); setDeleting(false);
    Promise.all([agentApi.list(offset, controller.signal), agentId ? agentApi.get(agentId, controller.signal) : Promise.resolve(null)])
      .then(([items, record]) => { if (!controller.signal.aborted) { setAgents(items); setDetail(record); } })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load agents.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [agentId, offset, revision]);
  async function testConnection() {
    if (!detail) return;
    setBusy(true); setError(''); setNotice('');
    try { const result = await agentApi.test(detail.id); setNotice(result.message + ' Response type: ' + result.response_type + '.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Connection test failed.'); }
    finally {
      try { const record = await agentApi.get(detail.id); setDetail(record); setAgents(items => items.map(item => item.id === record.id ? record : item)); }
      catch { setError(previous => previous || 'Unable to reload the agent after testing.'); }
      setBusy(false);
    }
  }
  async function remove() {
    if (!detail) return;
    setBusy(true); setError('');
    try { await agentApi.remove(detail.id); navigate('/agents'); setRevision(value => value + 1); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete agent.'); }
    finally { setBusy(false); }
  }
  function saved(record: Agent) { setForm(null); if (record.id === agentId) setRevision(value => value + 1); else navigate('/agents/' + record.id); }
  return <>
    <div className="page-heading"><div><p className="eyebrow">CANDIDATE CONNECTIONS</p><h1>My Agents</h1><p className="subtitle">Register an independently hosted agent and verify its protocol.</p></div><button className="primary-button" disabled={busy || loading} onClick={() => { setForm('create'); setDeleting(false); }}>Register agent</button></div>
    {error && <div className="form-error mb-5" role="alert">{error} <button onClick={() => setRevision(value => value + 1)} disabled={busy}>Refresh</button></div>}
    {notice && <p role="status" className="form-success mb-5">{notice}</p>}
    {loading ? <p role="status" className="muted">Loading registered agents…</p> : <div className="agent-workspace">
      <section className="panel agent-list" aria-label="Registered agents"><div className="section-header"><h2>Registered agents</h2></div>{agents.length === 0 ? <p className="p-6 muted">{error ? 'The agent list could not be loaded.' : offset ? 'No agents on this page.' : 'No agents registered. Add your first endpoint to get started.'}</p> : agents.map(agent => <Link key={agent.id} className={'agent-list-item ' + (agentId === agent.id ? 'selected' : '')} to={'/agents/' + agent.id} onClick={e => { if (busy) e.preventDefault(); }}><strong>{agent.name}</strong><span>{statusLabel[agent.last_test_status]}</span></Link>)}<div className="agent-actions p-4"><button disabled={offset === 0 || busy} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous</button><button disabled={agents.length < 100 || busy} onClick={() => setOffset(value => value + 100)}>Next</button></div></section>
      <section className="panel agent-detail" aria-label="Agent details">{form ? <AgentForm key={form + (form === 'edit' ? detail?.id : '')} agent={form === 'edit' ? detail ?? undefined : undefined} onSaved={saved} onCancel={() => setForm(null)} /> : detail ? <div className="p-6">
        <p className="eyebrow">AGENT DETAILS</p><h2 className="mt-3 text-xl">{detail.name}</h2><p className="agent-description">{detail.description || 'No description provided.'}</p>
        <dl className="agent-facts"><dt>Endpoint</dt><dd>{detail.endpoint_url}</dd><dt>Connection mode</dt><dd>{detail.connection_mode === 'external' ? 'External HTTPS' : 'Local sample (development)'}</dd><dt>Authentication</dt><dd>{detail.authentication_configured ? detail.auth_header_name + ' configured on server' : 'Not configured'}</dd><dt>Connection status</dt><dd>{statusLabel[detail.last_test_status]}</dd><dt>Last tested</dt><dd>{detail.last_test_at ? new Date(detail.last_test_at).toLocaleString() : 'Never'}</dd><dt>Created</dt><dd>{new Date(detail.created_at).toLocaleString()}</dd><dt>Updated</dt><dd>{new Date(detail.updated_at).toLocaleString()}</dd><dt>Agent ID</dt><dd>{detail.id}</dd></dl>
        {detail.last_test_message && <p className="form-help mt-4">{detail.last_test_code ? detail.last_test_code + ': ' : ''}{detail.last_test_message}</p>}
        <p className="form-help mt-4">A connection test sends one protocol message. It does not run an assessment, execute tools, or verify financial behavior.</p>
        <div className="agent-actions mt-6"><button className="primary-button" onClick={testConnection} disabled={busy}>{busy ? 'Working…' : 'Test connection'}</button><button onClick={() => setForm('edit')} disabled={busy}>Edit</button><button className="danger-button" onClick={() => setDeleting(true)} disabled={busy}>Delete</button></div>
        {deleting && <div className="delete-confirm mt-5" role="group" aria-label="Confirm deletion"><p>Delete this agent configuration? This cannot be undone.</p><div className="agent-actions mt-3"><button className="danger-button" disabled={busy} onClick={remove}>Confirm delete</button><button disabled={busy} onClick={() => setDeleting(false)}>Keep agent</button></div></div>}
      </div> : <div className="empty-state"><h2>Select an agent</h2><p>Choose a registered agent to inspect its configuration or test its connection.</p></div>}</section>
    </div>}
  </>;
}

