import type { Assessment, EvaluationState, RunEvent } from './assessments';

export interface Recommendation {
  id: string; category: string; title: string; action: string; rule_ids: string[]; event_ids: string[];
}
export interface PaymentEvidence {
  checkout_id: string; provider: string | null; status: string | null; total_minor: number | null;
  currency: string | null; order_id: string | null; capture_id: string | null;
  event_ids: string[]; captured_event_ids: string[]; inspection_event_ids: string[];
  authorization_event_ids: string[]; buyer_approval_event_ids: string[];
}
export interface AssessmentReport {
  schema_version: string; recommendations_version: string; assessment: Assessment;
  evaluation: EvaluationState; is_latest_evaluation: boolean; latest_evaluation_id: string | null;
  cutoff_sequence: number; evidence_total: number; evidence_complete: boolean; missing_event_ids: string[];
  recommendations: Recommendation[]; payments: PaymentEvidence[];
  recovery: { status: string; points: number; explanation: string; event_ids: string[] }[];
}
export interface ReportSummary {
  run_id: string; agent_name: string; environment_name: string; status: string; payment_mode: string;
  created_at: string; evaluation_id: string | null; evaluation_status: string;
  overall_score: number | null; certification: string | null; rubric: string | null; stale: boolean;
}
export interface ReportList { items: ReportSummary[]; total: number; offset: number; limit: number }
export interface ReportEventPage {
  evaluation_id: string | null; cutoff_sequence: number; events: RunEvent[]; total: number; next_after_sequence: number | null;
}
export interface ReportExport extends AssessmentReport { exported_at: string; evidence: RunEvent[] }
export interface EvidenceRequest { ids: string[]; revision: number }
