from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.protocol import Identifier, StrictModel
from app.schemas.evaluation import EvaluationRead

RunStatus = Literal["created", "running", "completed", "failed", "cancelled", "inconclusive"]


class AssessmentCreate(StrictModel):
    agent_id: Identifier
    environment_id: Identifier
    examiner_mode: Literal["deterministic", "rai"] = "deterministic"


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_id: str
    environment_id: str
    agent_name: str
    environment_name: str
    protocol_version: str
    payment_mode: Literal["simulated", "paypal_sandbox"]
    examiner_mode: Literal["deterministic", "rai"]
    examiner_provider: str
    examiner_model: str | None
    status: RunStatus
    termination_reason: str | None
    failure_origin: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    event_sequence: int
    evaluation: EvaluationRead | None = None

    @field_validator("created_at", "started_at", "ended_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    sequence: int
    created_at: datetime
    event_type: str
    correlation_id: str | None
    payload: dict

    @field_validator("created_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
