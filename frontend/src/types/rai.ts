import type { EnvironmentPreview } from './environments';
export interface RaiConfiguration { provider: 'mock' | 'openai' | 'gemini'; model: string; is_mock: boolean; examiner_modes: string[]; diagnostics_available: boolean; }
export interface RaiProposal {
  id: string; agent_id: string; status: 'generating' | 'ready' | 'failed' | 'compiled';
  provider: 'mock' | 'openai' | 'gemini'; model: string; is_mock: boolean;
  capability_summary: { source: string; declared_description: string; commerce_evidence: boolean; capabilities_verified: boolean; uncertainties: string[]; tool_interface_source: string };
  validation: { valid: boolean | null; code: string; attempts?: number; message?: string };
  preview: EnvironmentPreview | null; environment_id: string | null; created_at: string; updated_at: string; event_sequence: number;
}
export interface ProposalEvent { id: string; proposal_id: string; sequence: number; created_at: string; event_type: string; payload: Record<string, unknown>; }
export interface ProviderCheck {
  status: 'ok' | 'failed' | 'skipped'; code: string; latency_ms: number | null; message?: string; http_status?: number | null;
}
export interface ProviderDiagnostics {
  provider: string; model: string; is_mock: boolean; key_configured: boolean;
  runtime: { pid: number; parent_pid: number; python_executable: string; env_file: string; process_override_names: string[];
    environment_proxy_inheritance: boolean; redirects_enabled: boolean; tls_verification: boolean };
  limits: Record<string, number>; check_limits: Record<string, number>;
  connectivity: ProviderCheck; smoke_test: ProviderCheck;
}
