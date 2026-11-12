from datetime import datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.models.agent import utcnow


class RaiProposal(Base):
    __tablename__ = "rai_proposals"
    __table_args__ = (UniqueConstraint("agent_id", "request_key", name="uq_rai_proposal_request"),
                     CheckConstraint("status IN ('generating','ready','failed','compiled')", name="ck_rai_proposal_status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    request_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(100))
    capability_summary: Mapped[dict] = mapped_column(JSON)
    proposal_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blueprint_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_json: Mapped[dict] = mapped_column(JSON)
    provider_config: Mapped[dict] = mapped_column(JSON)
    environment_id: Mapped[str | None] = mapped_column(ForeignKey("environments.id"), nullable=True, unique=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)


class RaiProposalEvent(Base):
    __tablename__ = "rai_proposal_events"
    __table_args__ = (UniqueConstraint("proposal_id", "sequence", name="uq_rai_proposal_event_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("rai_proposals.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
