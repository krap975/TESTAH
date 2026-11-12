import { useEffect, useState } from 'react';
import type { EvaluationResult, RunEvent } from '../types/assessments';
import type { AssessmentReport } from '../types/reports';
import { loadReportEvidence, reportApi } from '../services/reports';

export function useReport(runId: string | undefined, evaluationId: string | undefined, revision: number) {
  const [report, setReport] = useState<AssessmentReport | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [history, setHistory] = useState<EvaluationResult[]>([]);
  const [loading, setLoading] = useState(false); const [complete, setComplete] = useState(false);
  const [loaded, setLoaded] = useState(0); const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setReport(null); setEvents([]); setHistory([]); setError(''); setComplete(false); setLoaded(0);
    if (!runId) return () => controller.abort();
    setLoading(true);
    async function load() {
      try {
        const record = await reportApi.get(runId!, evaluationId, controller.signal);
        if (controller.signal.aborted) return;
        setReport(record);
        // History is paginated independently; report evidence is pinned immediately.
        const historyTask = (async () => {
          const all: EvaluationResult[] = [];
          for (let offset = 0; ; offset += 100) {
            const page = await reportApi.history(runId!, offset, controller.signal); all.push(...page);
            if (page.length < 100) break;
          }
          if (!controller.signal.aborted) setHistory(all);
        })();
        const evidenceTask = (async () => {
          const result = record.evaluation.result;
          if (!result) return;
          const evidence = await loadReportEvidence(runId!, result.id, controller.signal, count => { if (!controller.signal.aborted) setLoaded(count); });
          if (!controller.signal.aborted) {
            setEvents(evidence); setComplete(record.evidence_complete && evidence.length === record.evidence_total);
          }
        })();
        await Promise.all([historyTask, evidenceTask]);
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load report.'); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [runId, evaluationId, revision]);
  return { report, events, history, loading, complete, loaded, error };
}
