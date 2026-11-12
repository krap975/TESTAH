import { useEffect, useState } from 'react';
import { agentApi } from '../services/agents';
import { raiApi } from '../services/rai';
import { allPages } from './useAssessments';
import type { Agent } from '../types/agents';
import type { ProposalEvent, RaiConfiguration, RaiProposal } from '../types/rai';

export function useRaiDesigner(proposalId: string | undefined, offset: number) {
  const [agents, setAgents] = useState<Agent[]>([]); const [proposals, setProposals] = useState<RaiProposal[]>([]);
  const [configuration, setConfiguration] = useState<RaiConfiguration | null>(null);
  const [detail, setDetail] = useState<RaiProposal | null>(null); const [events, setEvents] = useState<ProposalEvent[]>([]);
  const [error, setError] = useState(''); const [loading, setLoading] = useState(true); const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    setLoading(true); setError(''); setConfiguration(null); setDetail(null); setEvents([]);
    async function load() {
      try {
        const [agentList, config, list, record, evidence] = await Promise.all([
          allPages(agentApi.list, controller.signal), raiApi.configuration(controller.signal), raiApi.list(offset, controller.signal),
          proposalId ? raiApi.get(proposalId, controller.signal) : Promise.resolve(null),
          proposalId ? raiApi.events(proposalId, controller.signal) : Promise.resolve([]),
        ]);
        if (controller.signal.aborted) return;
        setAgents(agentList); setConfiguration(config); setProposals(list); setDetail(record); setEvents(evidence); setError('');
        if (record?.status === 'generating' || list.some(item => item.status === 'generating')) timer = setTimeout(load, 1500);
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load RAI proposals.'); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => { controller.abort(); clearTimeout(timer); };
  }, [proposalId, offset, revision]);
  return { agents, configuration, proposals, detail, events, error, loading, refresh: () => setRevision(value => value + 1) };
}
