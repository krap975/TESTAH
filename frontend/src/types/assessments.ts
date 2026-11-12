export type RunStatus = 'created' | 'running' | 'completed' | 'failed' | 'cancelled' | 'inconclusive';
export interface Assessment {
  id: string; agent_id: string; environment_id: string; agent_name: string; environment_name: string;
  protocol_version: string; status: RunStatus; termination_reason: string | null; failure_origin: string | null;
  payment_mode: 'simulated' | 'paypal_sandbox';
  examiner_mode: 'deterministic' | 'rai'; examiner_provider: string; examiner_model: string | null;
  created_at: string; started_at: string | null; ended_at: string | null; event_sequence: number;
  evaluation?: EvaluationState | null;
}
export interface EvaluationFinding {
  rule_id: string; status: string; explanation: string; event_ids: string[]; points: number;
}
export interface EvaluationResult {
  id: string; run_id: string; version: string; status: 'complete' | 'partial'; overall_score: number | null;
  engine_hash?: string;
  safety_status: string; cutoff_sequence: number; input_digest: string; policy_hash: string;
  assignment: 'before_execution' | 'retrospective'; created_at: string; payment_mode: string;
  certification: { version: string; decision: 'pass' | 'fail' | 'not_evaluated'; safety_gate: string; reasons: string[]; thresholds: Record<string, number> };
  dimensions: { name: string; weight: number; score: number | null; contribution: number | null; status: string; explanation: string; event_ids: string[] }[];
  findings: EvaluationFinding[]; evidence_gaps: string[]; coverage: Record<string, number>;
}
export interface EvaluationState {
  status: 'not_requested' | 'pending' | 'error' | 'complete' | 'partial'; result: EvaluationResult | null; stale: boolean;
}
export interface RunEvent {
  id: string; run_id: string; sequence: number; created_at: string; event_type: string;
  correlation_id: string | null; payload: Record<string, unknown>;
}
