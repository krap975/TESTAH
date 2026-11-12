import { useEffect, useState } from 'react';
import { assessmentApi } from '../services/assessments';
import { agentApi } from '../services/agents';
import { environmentApi } from '../services/environments';
import type { Assessment, RunEvent } from '../types/assessments';
import type { Agent } from '../types/agents';
import type { EnvironmentSummary } from '../types/environments';

export async function allPages<T>(fetchPage: (offset: number, signal: AbortSignal) => Promise<T[]>, signal: AbortSignal): Promise<T[]> {
  const items: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await fetchPage(offset, signal); items.push(...page);
    if (page.length < 100) return items;
  }
}

export function useAssessments(runId: string | undefined, offset: number) {
  const [runs, setRuns] = useState<Assessment[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentSummary[]>([]);
  const [detail, setDetail] = useState<Assessment | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    setLoading(true); setError(''); setDetail(null); setEvents([]);
    async function load() {
      try {
        const [list, record, availableAgents, availableEnvironments] = await Promise.all([
          assessmentApi.list(offset, controller.signal),
          runId ? assessmentApi.get(runId, controller.signal) : Promise.resolve(null),
          allPages(agentApi.list, controller.signal), allPages(environmentApi.list, controller.signal),
        ]);
        const evidence: RunEvent[] = [];
        if (runId) {
          for (;;) {
            const page = await assessmentApi.events(runId, evidence.at(-1)?.sequence ?? 0, controller.signal);
            evidence.push(...page); if (page.length < 500) break;
          }
        }
        if (controller.signal.aborted) return;
        setRuns(list); setDetail(record); setAgents(availableAgents.filter(agent => agent.last_test_status === 'connected'));
        setEnvironments(availableEnvironments); setEvents(evidence); setError('');
        if (record?.status === 'running' || (record && !['created', 'running'].includes(record.status) && record.evaluation?.status === 'pending') || list.some(run => run.status === 'running')) timer = setTimeout(load, 2000);
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load assessments.'); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [runId, offset, revision]);
  return { runs, agents, environments, detail, events, error, loading, refresh: () => setRevision(value => value + 1) };
}
