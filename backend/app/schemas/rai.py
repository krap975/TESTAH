from datetime import datetime
from typing import Annotated, Literal
from pydantic import Field
from app.schemas.environments import EnvironmentPreview
from app.schemas.protocol import Identifier, StrictModel


class ProposalCreate(StrictModel):
    agent_id: Identifier
    request_key: Identifier


class ProposalRead(StrictModel):
    id: str
    agent_id: str
    status: Literal["generating", "ready", "failed", "compiled"]
    provider: Literal["mock", "openai", "gemini"]
    model: str
    is_mock: bool
    capability_summary: dict
    validation: dict
    preview: EnvironmentPreview | None
    environment_id: str | None
    created_at: datetime
    updated_at: datetime
    event_sequence: int


class ExaminerPlan(StrictModel):
    version: Literal["1.0"]
    intent: Literal["present_objective", "restate_preferences", "clarify_budget", "clarify_currency",
                    "explain_authorization", "suggest_catalog_lookup", "acknowledge_change", "decline_out_of_scope"]
    tone: Literal["concise", "friendly", "cautious"]
    preference_indexes: Annotated[list[Annotated[int, Field(ge=0, le=9)]], Field(max_length=10)]
    challenge_request: Identifier | None
