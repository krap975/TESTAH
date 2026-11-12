import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AssessmentGraph } from '../components/AssessmentGraph';
import { AssessmentLifecycle } from '../components/AssessmentLifecycle';
import { AssessmentTimeline } from '../components/AssessmentTimeline';
import { EvidenceGrid } from '../components/EvidenceGrid';
import { SandboxCheckout } from '../components/SandboxCheckout';
import { useAssessmentStream } from '../hooks/useAssessmentStream';
import { assessmentGraph, describeEvent } from '../services/assessmentGraph';
import { assessmentApi } from '../services/assessments';
import type { Assessment } from '../types/assessments';
import '@xyflow/react/dist/style.css';

export function MonitorPage() {
  const { runId } = useParams(); const navigate = useNavigate();
  const [token, setToken] = useState(''); const [draftToken, setDraftToken] = useState(''); const [revision, setRevision] = useState(0);
  const [runs, setRuns] = useState<Assessment[]>([]); const [offset, setOffset] = useState(0); const [listError, setListError] = useState('');
  const [busy, setBusy] = useState(false); const [actionError, setActionError] = useState('');
  const [step, setStep] = useState<number | null>(null); const [selectedId, setSelectedId] = useState<string>();
  const [filter, setFilter] = useState<{ kind: 'node' | 'edge'; id: string } | null>(null);
  const stream = useAssessmentStream(runId, token, revision);
  useEffect(() => {
    const controller = new AbortController();
    void assessmentApi.list(offset, controller.signal).then(value => { setRuns(value); setListError(''); }).catch(() => { if (!controller.signal.aborted) setListError('Unable to load assessments.'); });
    return () => controller.abort();
  }, [offset, revision]);
  useEffect(() => { setStep(null); setSelectedId(undefined); setFilter(null); setActionError(''); }, [runId, revision]);
  const count = Math.min(step ?? stream.events.length, stream.events.length);
  const prefix = useMemo(() => stream.events.slice(0, count), [stream.events, count]);
  const graph = useMemo(() => assessmentGraph(prefix), [prefix]);
  const selection = filter ? (filter.kind === 'node' ? graph.nodes : graph.edges).find(item => item.id === filter.id) : undefined;
  const filteredEvents = useMemo(() => selection ? prefix.filter(event => selection.data.eventIds.includes(event.id)) : prefix, [prefix, selection]);
  const selected = prefix.find(event => event.id === selectedId) ?? filteredEvents.at(-1);
  async function action(callback: () => Promise<unknown>) {
    setBusy(true); setActionError('');
    try { await callback(); } catch (error) { setActionError(error instanceof Error ? error.message : 'Assessment action failed.'); }
    finally { setBusy(false); }
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">OBSERVED EXECUTION / DURABLE EVIDENCE</p><h1>Live Monitor</h1><p className="subtitle">Watch a run or reconstruct its recorded history. Payment mode is fixed per assessment.</p></div><Link to="/assessments">Manage assessments →</Link></div>
    <section className="panel agent-form mb-5" aria-label="Monitor access and assessment selection">
      <label>Saved assessment<select value={runId ?? ''} onChange={event => navigate(event.target.value ? '/monitor/' + event.target.value : '/monitor')}><option value="">Select an assessment</option>
        {runId && !runs.some(run => run.id === runId) && <option value={runId}>Assessment {runId}</option>}
        {runs.map(run => <option key={run.id} value={run.id}>{run.agent_name} · {stream.run?.id === run.id ? stream.run.status : run.status} · {run.id}</option>)}</select></label>
      <div className="agent-actions"><button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous page</button><button disabled={runs.length < 100} onClick={() => setOffset(value => value + 100)}>Next page</button><button onClick={() => setRevision(value => value + 1)}>Reload history / reconnect</button></div>
      {!token ? <form className="monitor-access" onSubmit={event => { event.preventDefault(); setToken(draftToken.trim()); setDraftToken(''); }}>
        <label>Monitoring access token<input type="password" autoComplete="off" spellCheck={false} required minLength={32} value={draftToken} onChange={event => setDraftToken(event.target.value)} /></label>
        <button className="primary-button" disabled={!draftToken.trim()}>Connect monitor</button>
        <p className="form-help">Use the separate TESTAH_MONITOR_TOKEN configured by your local operator. It is held in memory and must be re-entered after refresh. Do not enter a Gemini or agent API key.</p>
      </form> : <div className="agent-actions"><span className="form-help">Monitoring credential is held in memory.</span><button onClick={() => setToken('')}>Disconnect and clear credential</button></div>}
      <p role="status" className={'stream-status stream-' + stream.status}>Stream: {stream.status} · {stream.events.length} accepted persisted events</p>
      {listError && <p role="alert" className="form-error">{listError}</p>}{stream.error && <p role="alert" className="form-error">{stream.error}</p>}{actionError && <p role="alert" className="form-error">{actionError}</p>}
    </section>
    {stream.run && <>
      <AssessmentLifecycle run={stream.run} />
      <SandboxCheckout key={stream.run.id} run={stream.run} />
      <div className="agent-actions mb-5">{stream.run.status === 'created' && <button className="primary-button" disabled={busy} onClick={() => void action(() => assessmentApi.start(stream.run!.id))}>Start assessment</button>}
        {['created', 'running'].includes(stream.run.status) && <button disabled={busy} onClick={() => void action(() => assessmentApi.cancel(stream.run!.id))}>Cancel assessment</button>}
        <Link to={'/assessments/' + stream.run.id}>Open assessment details</Link><Link to={'/reports/' + stream.run.id}>Assessment report</Link></div>
    </>}
    {stream.events.length > 0 ? <>
      <section className="panel replay-controls mb-5" aria-label="Historical event replay">
        <div><strong>{step === null ? stream.status === 'settled' ? 'Full persisted history' : 'Latest accepted events' : 'Historical event prefix'}</strong><span className="muted"> · {count} / {stream.events.length} events visible</span></div>
        <input type="range" min={0} max={stream.events.length} value={count} aria-label="Visible event count" onChange={event => setStep(Number(event.target.value))} />
        <div className="agent-actions"><button disabled={count === 0} onClick={() => setStep(Math.max(0, count - 1))}>Previous event</button><button disabled={count === stream.events.length} onClick={() => setStep(count + 1)}>Next event</button><button onClick={() => setStep(null)}>Latest / full history</button></div>
        <p className="form-help">Replay changes only the displayed event prefix. It never sends agent requests or executes payments. Lifecycle metadata above describes the current saved assessment.</p>
      </section>
      <AssessmentGraph nodes={graph.nodes} edges={graph.edges} selection={filter} select={(kind, id) => { setFilter({ kind, id }); setSelectedId(undefined); }} />
      <div className="monitor-selection"><span>{filter ? 'Showing events supporting ' + (selection && 'label' in selection ? selection.label : selection?.data.label ?? filter.id) : 'Showing all visible events'}</span>{filter && <button onClick={() => setFilter(null)}>Show all events</button>}</div>
      <div className="panel report-section"><EvidenceGrid key={filter ? filter.kind + filter.id : 'all'} events={filteredEvents} selectedId={selected?.id} select={setSelectedId} />
        <details><summary>Chronological timeline</summary><AssessmentTimeline events={filteredEvents} selectedId={selected?.id} select={setSelectedId} /></details></div>
    </> : <section className="panel p-6"><p className="muted">{runId ? token ? 'Waiting for persisted assessment evidence.' : 'Connect with your monitoring token to load this assessment.' : 'Select a saved assessment. Create a new one from Assessments when needed.'}</p></section>}
  </>;
}
