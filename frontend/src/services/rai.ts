import { apiRequest } from './api';
import type { ProposalEvent, ProviderDiagnostics, RaiConfiguration, RaiProposal } from '../types/rai';
const path = (id: string) => '/api/rai/proposals/' + encodeURIComponent(id);
export const raiApi = {
  configuration: (signal?: AbortSignal) => apiRequest<RaiConfiguration>('/api/rai/configuration', { signal }),
  diagnostics: () => apiRequest<ProviderDiagnostics>('/api/rai/diagnostics', { method: 'POST', body: JSON.stringify({ run_smoke_test: true }) }),
  list: (offset = 0, signal?: AbortSignal) => apiRequest<RaiProposal[]>('/api/rai/proposals?offset=' + offset + '&limit=100', { signal }),
  get: (id: string, signal?: AbortSignal) => apiRequest<RaiProposal>(path(id), { signal }),
  events: (id: string, signal?: AbortSignal) => apiRequest<ProposalEvent[]>(path(id) + '/events?limit=500', { signal }),
  generate: (agent_id: string, request_key: string) => apiRequest<RaiProposal>('/api/rai/proposals', { method: 'POST', body: JSON.stringify({ agent_id, request_key }) }),
  compile: (id: string) => apiRequest<RaiProposal>(path(id) + '/compile', { method: 'POST' }),
};
