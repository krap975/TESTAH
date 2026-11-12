import { useEffect, useState } from 'react';
import { getHealth } from '../services/api';
import type { HealthResponse } from '../types/api';
type HealthState = { status: 'checking' } | { status: 'connected'; data: HealthResponse } | { status: 'unavailable'; message: string };
export function useHealth() {
  const [state, setState] = useState<HealthState>({ status: 'checking' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'checking' });
    getHealth(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setState({ status: 'connected', data }); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ status: 'unavailable', message: error instanceof Error ? error.message : 'Connection failed.' }); });
    return () => controller.abort();
  }, [attempt]);
  return { state, refresh: () => setAttempt((value) => value + 1) };
}
