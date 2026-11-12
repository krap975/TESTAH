import { apiRequest } from './api';
import type { Agent, AgentInput, ConnectionTest } from '../types/agents';
export const agentApi = {
  list: (offset = 0, signal?: AbortSignal) => apiRequest<Agent[]>('/api/agents?offset=' + offset + '&limit=100', { signal }),
  get: (id: string, signal?: AbortSignal) => apiRequest<Agent>('/api/agents/' + encodeURIComponent(id), { signal }),
  create: (data: AgentInput) => apiRequest<Agent>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: AgentInput) => apiRequest<Agent>('/api/agents/' + encodeURIComponent(id), { method: 'PATCH', body: JSON.stringify(data) }),
  remove: (id: string) => apiRequest<void>('/api/agents/' + encodeURIComponent(id), { method: 'DELETE' }),
  test: (id: string) => apiRequest<ConnectionTest>('/api/agents/' + encodeURIComponent(id) + '/test', { method: 'POST', body: '{}' }),
};

