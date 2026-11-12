import { apiRequest } from './api';
import type { Assessment, RunEvent, EvaluationState } from '../types/assessments';
const path = (id: string) => '/api/assessments/' + encodeURIComponent(id);
export const assessmentApi = {
  list: (offset = 0, signal?: AbortSignal) => apiRequest<Assessment[]>('/api/assessments?offset=' + offset + '&limit=100', { signal }),
  get: (id: string, signal?: AbortSignal) => apiRequest<Assessment>(path(id), { signal }),
  events: (id: string, after = 0, signal?: AbortSignal) => apiRequest<RunEvent[]>(path(id) + '/events?after_sequence=' + after + '&limit=500', { signal }),
  create: (agent_id: string, environment_id: string, examiner_mode: 'deterministic' | 'rai' = 'deterministic') => apiRequest<Assessment>('/api/assessments', { method: 'POST', body: JSON.stringify({ agent_id, environment_id, examiner_mode }) }),
  start: (id: string) => apiRequest<Assessment>(path(id) + '/start', { method: 'POST' }),
  cancel: (id: string) => apiRequest<Assessment>(path(id) + '/cancel', { method: 'POST' }),
  evaluate: (id: string) => apiRequest<EvaluationState>(path(id) + '/evaluate', { method: 'POST', body: '{}' }),
};
