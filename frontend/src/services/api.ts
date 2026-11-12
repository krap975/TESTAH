import type { ApiErrorResponse, HealthResponse } from '../types/api';
import { workspaceHeaders } from './workspaceAccess';
const baseUrl = (import.meta.env?.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const apiUrl = (path: string) => baseUrl + path;
export class ApiError extends Error {
  constructor(public readonly code: string, message: string) { super(message); }
}
export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const signal = options.signal;
  const response = await fetch(baseUrl + path, {
    ...options,
    headers: { Accept: 'application/json', ...workspaceHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    signal: AbortSignal.any([AbortSignal.timeout(path.endsWith('/reconcile') ? 150000 : path.endsWith('/diagnostics') ? 75000 : path.endsWith('/test') ? 65000 : 8000), ...(signal ? [signal] : [])]),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null;
    throw new ApiError(body?.error?.code ?? 'http_error', body?.error?.message ?? ('API request failed (' + response.status + ').'));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { signal });
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const health = await apiGet<HealthResponse>('/api/health', signal);
  if (health.status !== 'ok' || health.database !== 'connected' || typeof health.service !== 'string') {
    throw new Error('The backend returned an unexpected health response.');
  }
  return health;
}
