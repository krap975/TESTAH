import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AssessmentDetails } from '../components/AssessmentDetails';
import { useAssessments } from '../hooks/useAssessments';
import { assessmentApi } from '../services/assessments';

export function AssessmentsPage() {
  const { runId } = useParams(); const navigate = useNavigate();
  const [offset, setOffset] = useState(0); const data = useAssessments(runId, offset);
  const [agentId, setAgentId] = useState(''); const [environmentId, setEnvironmentId] = useState('');
  const [examinerMode, setExaminerMode] = useState<'deterministic' | 'rai'>('deterministic');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError('');
    try { await action(); data.refresh(); } catch (err) { setError(err instanceof Error ? err.message : 'Request failed.'); }
    finally { setBusy(false); }
  }
  const run = data.detail;
  return <>
    <div className="page-heading"><div><p className="eyebrow">DETERMINISTIC EXECUTION</p><h1>Assessments</h1><p className="subtitle">Run a connected external agent against an isolated commerce simulation.</p></div><button disabled={busy} onClick={data.refresh}>Refresh status</button></div>
    {(error || data.error) && <div role="alert" className="form-error mb-5">{error || data.error} <button onClick={data.refresh}>Retry loading</button></div>}
    <form className="panel agent-form mb-5" onSubmit={event => { event.preventDefault(); void perform(async () => { const created = await assessmentApi.create(agentId, environmentId, examinerMode); navigate('/assessments/' + created.id); }); }}>
      <h2>Create assessment</h2><div className="environment-form-grid"><label>Protocol-connected agent<select required value={agentId} onChange={event => setAgentId(event.target.value)}><option value="">Select agent</option>{data.agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label><label>Compiled environment<select required value={environmentId} onChange={event => setEnvironmentId(event.target.value)}><option value="">Select environment</option>{data.environments.map(environment => <option key={environment.id} value={environment.id}>{environment.name}</option>)}</select></label></div>
      <label>Customer mode<select value={examinerMode} onChange={event => setExaminerMode(event.target.value as 'deterministic' | 'rai')}><option value="deterministic">Deterministic customer</option><option value="rai">RAI Examiner (configured provider; details recorded on creation)</option></select></label>
      <p className="form-help">{data.agents.length === 0 ? 'Register and test an agent connection first. ' : ''}{data.environments.length === 0 ? 'Create a compiled environment first. ' : ''}Each run receives independent mutable state.</p><div className="agent-actions"><button className="primary-button" disabled={busy || !data.agents.some(agent => agent.id === agentId) || !data.environments.some(environment => environment.id === environmentId)}>Create assessment</button></div>
    </form>
    {data.loading && <p role="status" className="muted mb-5">Loading assessments…</p>}
    <div className="environment-workspace"><section className="panel" aria-label="Saved assessments"><div className="section-header"><h2>Saved assessments</h2></div>{data.runs.length === 0 ? <p className="p-6 form-help">{data.error ? 'Assessment data could not be loaded.' : 'No assessments on this page.'}</p> : data.runs.map(item => <Link className={'agent-list-item ' + (item.id === runId ? 'selected' : '')} key={item.id} to={'/assessments/' + item.id}><strong>{item.agent_name}</strong><span>{item.environment_name}</span><span>{item.status} · {item.id}</span></Link>)}<div className="agent-actions p-4"><button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous</button><button disabled={data.runs.length < 100} onClick={() => setOffset(value => value + 100)}>Next</button></div></section>
      <section className="panel" aria-label="Assessment workspace">{run ? <><div className="agent-actions p-6">{run.status === 'created' && <button className="primary-button" disabled={busy} onClick={() => void perform(() => assessmentApi.start(run.id))}>Start assessment</button>}{['created', 'running'].includes(run.status) && <button disabled={busy} onClick={() => void perform(() => assessmentApi.cancel(run.id))}>Cancel assessment</button>}</div><AssessmentDetails run={run} events={data.events} requestScore={() => void perform(() => assessmentApi.evaluate(run.id))} busy={busy} /></> : <p className="p-6 form-help">Select a saved assessment to inspect its actual outcome and events.</p>}</section>
    </div>
  </>;
}
