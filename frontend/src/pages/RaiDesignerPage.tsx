import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { RaiProviderStatus } from '../components/RaiProviderStatus';
import { RaiProviderDiagnostics } from '../components/RaiProviderDiagnostics';
import { RaiProposalDetails } from '../components/RaiProposalDetails';
import { useRaiDesigner } from '../hooks/useRaiDesigner';
import { assessmentApi } from '../services/assessments';
import { raiApi } from '../services/rai';
import { ApiError } from '../services/api';

export function RaiDesignerPage() {
  const { proposalId } = useParams(); const navigate = useNavigate(); const [offset, setOffset] = useState(0);
  const data = useRaiDesigner(proposalId, offset); const [agentId, setAgentId] = useState('');
  const [examinerMode, setExaminerMode] = useState<'rai' | 'deterministic'>('rai');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const request = useRef<{ agent: string; key: string } | null>(null);
  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); data.refresh(); } catch (err) { setError(err instanceof ApiError ? err.code + ': ' + err.message : err instanceof Error ? err.message : 'RAI request failed.'); }
    finally { setBusy(false); }
  }
  const proposal = data.detail;
  useEffect(() => { if (proposal && !agentId) setAgentId(proposal.agent_id); }, [proposal, agentId]);
  async function generateFor(agent: string) {
    if (!request.current || request.current.agent !== agent) request.current = { agent, key: crypto.randomUUID() };
    const generated = await raiApi.generate(agent, request.current.key); request.current = null;
    navigate('/rai/' + generated.id);
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">DESIGN / VALIDATE / EXAMINE</p><h1>Generate with RAI</h1><p className="subtitle">Design a controlled commerce scenario for a registered agent, then review it before compilation.</p></div><Link className="text-sm muted" to="/environments">Advanced / Manual environments →</Link></div>
    {(error || data.error) && <div className="form-error mb-5" role="alert">{error || data.error} <button onClick={data.refresh}>Retry loading</button></div>}
    <form className="panel agent-form mb-5" onSubmit={event => { event.preventDefault(); void perform(async () => {
      await generateFor(agentId);
    }); }}>
      <h2>Design an environment</h2><RaiProviderStatus configuration={data.configuration} />
      <label>Registered agent<select required value={agentId} onChange={event => setAgentId(event.target.value)}><option value="">Select agent</option>{data.agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label>
      <p className="form-help">Declared capabilities are unverified. Missing or unsupported capability descriptions use conservative commerce defaults. Model output must pass deterministic validation.</p>
      <div className="agent-actions"><button className="primary-button" disabled={busy || !data.configuration || !agentId}>Generate with RAI</button><button type="button" disabled={busy} onClick={data.refresh}>Refresh proposals</button></div>
    </form>
    {data.configuration?.diagnostics_available && <RaiProviderDiagnostics />}
    {data.loading && <p role="status" className="muted mb-5">Loading proposals…</p>}
    <div className="environment-workspace"><section className="panel" aria-label="Saved RAI proposals"><div className="section-header"><h2>Saved proposals</h2></div>{data.proposals.length === 0 ? <p className="p-6 form-help">No proposals on this page.</p> : data.proposals.map(item => <Link key={item.id} className={'agent-list-item ' + (item.id === proposalId ? 'selected' : '')} to={'/rai/' + item.id}><strong>{item.preview?.objective ?? 'Environment proposal'}</strong><span>{item.status} · {item.is_mock ? 'MOCK' : item.provider}</span><span>{item.id}</span></Link>)}<div className="agent-actions p-4"><button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous</button><button disabled={data.proposals.length < 100} onClick={() => setOffset(value => value + 100)}>Next</button></div></section>
      <section className="panel" aria-label="RAI proposal workspace">{proposal ? <>
        {proposal.status === 'failed' && <div className="agent-actions p-6"><button type="button" className="primary-button" disabled={busy} onClick={() => void perform(async () => { await generateFor(proposal.agent_id); })}>Retry generation with the same agent</button></div>}
        {proposal.status === 'ready' && <div className="agent-actions p-6"><button className="primary-button" disabled={busy} onClick={() => void perform(async () => { await raiApi.compile(proposal.id); })}>Confirm and compile</button></div>}
        {proposal.status === 'compiled' && proposal.environment_id && <div className="agent-form"><h2>Start from this compiled environment</h2><Link className="text-sm" to={'/environments/' + proposal.environment_id}>Inspect saved environment →</Link><label>Customer mode<select value={examinerMode} onChange={event => setExaminerMode(event.target.value as 'rai' | 'deterministic')}><option value="rai">RAI Examiner ({data.configuration?.is_mock ? 'mock provider' : data.configuration ? data.configuration.provider + ' / ' + data.configuration.model : 'configured provider'})</option><option value="deterministic">Deterministic customer</option></select></label><p className="form-help">The agent must have a current protocol connection. The Examiner cannot grant approval or modify financial state.</p><div className="agent-actions"><button className="primary-button" disabled={busy} onClick={() => void perform(async () => { const run = await assessmentApi.create(proposal.agent_id, proposal.environment_id!, examinerMode); navigate('/assessments/' + run.id); })}>Create assessment from proposal</button><Link to={'/agents/' + proposal.agent_id}>Manage agent connection</Link></div></div>}
        <RaiProposalDetails proposal={proposal} events={data.events} />
      </> : <p className="p-6 form-help">Select an agent to generate a proposal, or choose a saved proposal to review its validated preview and persisted decisions.</p>}</section>
    </div>
  </>;
}
