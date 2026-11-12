import { apiRequest } from './api';
import type { EvaluationResult, RunEvent } from '../types/assessments';
import type { AssessmentReport, ReportEventPage, ReportExport, ReportList } from '../types/reports';

const runPath = (id: string) => '/api/assessments/' + encodeURIComponent(id);
const selection = (id?: string) => id ? '?evaluation_id=' + encodeURIComponent(id) : '';
export const reportApi = {
  list: (offset = 0, signal?: AbortSignal) => apiRequest<ReportList>('/api/reports?offset=' + offset + '&limit=100', { signal }),
  get: (runId: string, evaluationId?: string, signal?: AbortSignal) => apiRequest<AssessmentReport>(runPath(runId) + '/report' + selection(evaluationId), { signal }),
  events: (runId: string, evaluationId: string, after = 0, signal?: AbortSignal) => apiRequest<ReportEventPage>(runPath(runId) + '/report/events' + selection(evaluationId) + '&after_sequence=' + after + '&limit=500', { signal }),
  history: (runId: string, offset = 0, signal?: AbortSignal) => apiRequest<EvaluationResult[]>(runPath(runId) + '/evaluations?offset=' + offset + '&limit=100', { signal }),
  export: (runId: string, evaluationId: string, signal?: AbortSignal) => apiRequest<ReportExport>(runPath(runId) + '/report/export' + selection(evaluationId), { signal }),
  logs: (runId: string, after = 0, signal?: AbortSignal) => apiRequest<RunEvent[]>(runPath(runId) + '/events?after_sequence=' + after + '&limit=500', { signal }),
};

/** Load the pinned cutoff, never just the first server/grid page. */
export async function loadReportEvidence(runId: string, evaluationId: string, signal: AbortSignal,
  progress: (count: number) => void): Promise<RunEvent[]> {
  const events: RunEvent[] = []; let after = 0;
  for (;;) {
    const page = await reportApi.events(runId, evaluationId, after, signal);
    if (page.evaluation_id !== evaluationId || page.events.some(e => e.run_id !== runId || e.sequence <= after || e.sequence > page.cutoff_sequence)) throw new Error('Report evidence did not match its selected evaluation.');
    events.push(...page.events); progress(events.length);
    if (events.length > 5000) throw new Error('This history exceeds the report limit of 5000 events.');
    if (page.next_after_sequence === null) {
      if (events.length !== page.total || new Set(events.map(e => e.id)).size !== events.length) throw new Error('Complete report evidence could not be loaded.');
      return events;
    }
    if (page.next_after_sequence <= after) throw new Error('Report evidence cursor did not advance.');
    after = page.next_after_sequence;
  }
}
