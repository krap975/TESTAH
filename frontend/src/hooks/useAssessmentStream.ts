import { useEffect, useState } from 'react';
import { watchAssessment, type ConnectionStatus } from '../services/assessmentStream';
import type { Assessment, RunEvent } from '../types/assessments';

export function useAssessmentStream(runId: string | undefined, token: string, revision: number) {
  const [run, setRun] = useState<Assessment | null>(null); const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('idle'); const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController(); let alive = true;
    setRun(null); setEvents([]); setError(''); setStatus('idle');
    if (runId && token) void watchAssessment(runId, token, controller.signal, {
      onRun: value => { if (alive) setRun(value); }, onEvent: value => { if (alive) setEvents(previous => [...previous, value]); },
      onStatus: value => { if (alive) setStatus(value); }, onError: value => { if (alive) setError(value); },
    });
    return () => { alive = false; controller.abort(); };
  }, [runId, token, revision]);
  return { run, events, status, error };
}
