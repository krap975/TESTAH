import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { assessmentApi } from '../services/assessments';
import type { Assessment } from '../types/assessments';
export function AssessmentActivity() {
  const [runs, setRuns] = useState<Assessment[]>([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    assessmentApi.list(0, controller.signal).then(setRuns).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load activity.'); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  return <section className="panel"><div className="section-header"><h2>Recorded assessments</h2><Link className="text-sm" to="/assessments">Open assessments →</Link></div>{loading ? <p className="p-6 muted">Loading activity…</p> : error ? <p role="alert" className="p-6 muted">{error}</p> : runs.length === 0 ? <p className="p-6 muted text-sm">No assessments yet. Create a run with a connected agent and compiled environment.</p> : runs.slice(0, 5).map(run => <Link className="agent-list-item" key={run.id} to={'/assessments/' + run.id}><strong>{run.agent_name} · {run.environment_name}</strong><span>{run.status} · {run.id}</span></Link>)}</section>;
}
