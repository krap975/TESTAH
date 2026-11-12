import { apiRequest } from './api';
import type { Environment, EnvironmentInput, EnvironmentSummary, EnvironmentTemplate, Currency } from '../types/environments';
export const environmentApi = {
  templates: (signal?: AbortSignal) => apiRequest<EnvironmentTemplate[]>('/api/environment-templates', { signal }),
  list: (offset = 0, signal?: AbortSignal) => apiRequest<EnvironmentSummary[]>('/api/environments?offset=' + offset + '&limit=100', { signal }),
  get: (id: string, signal?: AbortSignal) => apiRequest<Environment>('/api/environments/' + encodeURIComponent(id), { signal }),
  create: (data: EnvironmentInput) => apiRequest<Environment>('/api/environments', { method: 'POST', body: JSON.stringify(data) }),
};
export function formatMoney(minor: number, currency: Currency): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(minor / 100);
}
export function parseMinorUnits(value: string): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value.trim())) return null;
  const [whole, fraction = ''] = value.trim().split('.');
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(result) ? result : null;
}

