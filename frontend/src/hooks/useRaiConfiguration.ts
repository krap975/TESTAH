import { useEffect, useState } from 'react';
import { raiApi } from '../services/rai';
import type { RaiConfiguration } from '../types/rai';

export function useRaiConfiguration() {
  const [configuration, setConfiguration] = useState<RaiConfiguration | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setConfiguration(null); setError('');
    void raiApi.configuration(controller.signal).then(value => {
      if (!controller.signal.aborted) setConfiguration(value);
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'RAI configuration unavailable.');
    });
    return () => controller.abort();
  }, [revision]);
  return { configuration, error, refresh: () => setRevision(value => value + 1) };
}
