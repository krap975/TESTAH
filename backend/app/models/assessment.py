"""Durable execution aggregate and append-only evidence records."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.models.agent import utcnow


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (CheckConstraint("status IN ('created','running','completed','failed','cancelled','inconclusive')", name="ck_assessment_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"))
    agent_name: Mapped[str] = mapped_column(String(100))
    environment_name: Mapped[str] = mapped_column(String(100))
    agent_config: Mapped[dict] = mapped_column(JSON)
    blueprint_json: Mapped[dict] = mapped_column(JSON)
    runtime_json: Mapped[dict] = mapped_column(JSON)
    limits: Mapped[dict] = mapped_column(JSON)
    protocol_version: Mapped[str] = mapped_column(String(20), default="1.0")
    payment_mode: Mapped[str] = mapped_column(String(20), default="simulated", server_default="simulated")
    examiner_mode: Mapped[str] = mapped_column(String(20), default="deterministic", server_default="deterministic")
    examiner_provider: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    examiner_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    examiner_config: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), default="created")
    termination_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_origin: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_run_event_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_type: Mapped[str] = mapped_column(String(80))
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
