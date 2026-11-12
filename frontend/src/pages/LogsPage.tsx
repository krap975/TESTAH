import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { RunEvent } from '../types/assessments';
import type { ReportList } from '../types/reports';
import { reportApi } from '../services/reports';
import { EvidenceGrid } from '../components/EvidenceGrid';

export function LogsPage() {
  const [search, setSearch] = useSearchParams(); const runId = search.get('run') ?? '';
  const [list, setList] = useState<ReportList | null>(null); const [offset, setOffset] = useState(0);
  const [events, setEvents] = useState<RunEvent[]>([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  useEffect(() => { const c = new AbortController(); void reportApi.list(offset, c.signal).then(setList).catch(() => { if (!c.signal.aborted) setError('Unable to list assessments.'); }); return () => c.abort(); }, [offset]);
  useEffect(() => {
    const c = new AbortController(); setEvents([]); setError(''); if (!runId) return () => c.abort(); setLoading(true);
    void (async () => { const all: RunEvent[] = []; for (;;) {
      const page = await reportApi.logs(runId, all.at(-1)?.sequence ?? 0, c.signal); all.push(...page);
      if (all.length > 5000) throw new Error('This history exceeds the 5000-event inspection limit.');
      if (page.length < 500) break;
    } if (!c.signal.aborted) setEvents(all); })().catch(err => { if (!c.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load logs.'); }).finally(() => { if (!c.signal.aborted) setLoading(false); });
    return () => c.abort();
  }, [runId]);
  return <><div className="page-heading"><div><p className="eyebrow">PERSISTED EXECUTION</p><h1>Execution logs</h1><p className="subtitle">Inspect recorded events without starting execution or changing payment state.</p></div></div>
    <section className="panel report-section"><label>Assessment<select value={runId} onChange={e => setSearch(e.target.value ? { run: e.target.value } : {})}><option value="">Select an assessment</option>
      {runId && !list?.items.some(r => r.run_id === runId) && <option value={runId}>{runId}</option>}{list?.items.map(r => <option key={r.run_id} value={r.run_id}>{r.agent_name} · {r.status} · {r.run_id}</option>)}</select></label>
      <div className="agent-actions"><button disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 100))}>Previous batch</button><button disabled={!list || offset + list.items.length >= list.total} onClick={() => setOffset(n => n + 100)}>Next batch</button>{runId && <Link to={'/reports/' + runId}>Open assessment report</Link>}</div>
      {loading && <p role="status">Loading persisted evidence…</p>}{error && <p role="alert" className="form-error">{error}</p>}
      <EvidenceGrid key={runId} events={events} /></section></>;
}
