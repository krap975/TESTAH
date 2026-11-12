"""Allowlisted read-only reporting contracts. No evaluator input or payment secrets."""
from typing import Literal
from pydantic import BaseModel
from app.schemas.assessments import AssessmentRead, EventRead
from app.schemas.evaluation import EvaluationRead


class RecommendationRead(BaseModel):
    id: str
    category: Literal["safety", "correctness", "recovery", "efficiency", "evidence"]
    title: str
    action: str
    rule_ids: list[str]
    event_ids: list[str]


class PaymentEvidenceRead(BaseModel):
    checkout_id: str
    provider: str | None
    status: str | None
    total_minor: int | None
    currency: str | None
    order_id: str | None
    capture_id: str | None
    authorization_event_ids: list[str]
    buyer_approval_event_ids: list[str]
    event_ids: list[str]
    captured_event_ids: list[str]
    inspection_event_ids: list[str]


class RecoveryRead(BaseModel):
    status: str
    points: int
    explanation: str
    event_ids: list[str]


class ReportRead(BaseModel):
    schema_version: str
    recommendations_version: str
    assessment: AssessmentRead
    evaluation: EvaluationRead
    is_latest_evaluation: bool
    latest_evaluation_id: str | None
    cutoff_sequence: int
    evidence_total: int
    evidence_complete: bool
    missing_event_ids: list[str]
    recommendations: list[RecommendationRead]
    payments: list[PaymentEvidenceRead]
    recovery: list[RecoveryRead]


class ReportSummaryRead(BaseModel):
    run_id: str
    agent_name: str
    environment_name: str
    status: str
    payment_mode: str
    created_at: str
    evaluation_id: str | None
    evaluation_status: str
    overall_score: float | None
    certification: str | None
    rubric: str | None
    stale: bool


class ReportListRead(BaseModel):
    items: list[ReportSummaryRead]
    total: int
    offset: int
    limit: int


class ReportEventsRead(BaseModel):
    evaluation_id: str | None
    cutoff_sequence: int
    events: list[EventRead]
    total: int
    next_after_sequence: int | None


class ReportExportRead(ReportRead):
    exported_at: str
    evidence: list[EventRead]
