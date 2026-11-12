"""Public scoring contracts intentionally exclude private evaluator inputs."""
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.protocol import StrictModel


class EvaluationRequest(StrictModel):
    """Server chooses version, weights and evidence; clients provide no score inputs."""


class FindingRead(BaseModel):
    rule_id: str
    status: Literal["pass", "fail", "not_evaluated", "not_exercised"]
    explanation: str
    event_ids: list[str]
    points: int


class DimensionRead(BaseModel):
    name: str
    weight: int
    score: float | None
    contribution: float | None
    status: Literal["pass", "fail", "not_evaluated", "not_exercised"]
    explanation: str
    event_ids: list[str]


class CertificationRead(BaseModel):
    version: str
    decision: Literal["pass", "fail", "not_evaluated"]
    safety_gate: Literal["clear", "blocked", "not_evaluated"]
    thresholds: dict[str, int]
    reasons: list[str]


class EvaluationResultRead(BaseModel):
    id: str
    run_id: str
    version: str
    status: Literal["complete", "partial"]
    overall_score: float | None
    safety_status: str
    certification: CertificationRead
    dimensions: list[DimensionRead]
    findings: list[FindingRead]
    evidence_gaps: list[str]
    coverage: dict[str, int]
    payment_mode: str
    scenario_version: str
    template_id: str
    protocol_version: str
    cutoff_sequence: int
    input_digest: str
    policy_hash: str
    engine_hash: str
    assignment: Literal["before_execution", "retrospective"]
    created_at: str


class EvaluationRead(BaseModel):
    status: Literal["not_requested", "pending", "error", "complete", "partial"]
    result: EvaluationResultRead | None = None
    stale: bool = False
