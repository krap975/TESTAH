"""Additive scoring storage; execution/payment evidence is never rewritten."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.models.agent import utcnow


class ScoringBinding(Base):
    __tablename__ = "scoring_bindings"
    run_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    version: Mapped[str] = mapped_column(String(80))
    policy_json: Mapped[dict] = mapped_column(JSON)
    policy_hash: Mapped[str] = mapped_column(String(64))
    assignment: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("run_id", "version", "input_digest", name="uq_evaluation_inputs"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    version: Mapped[str] = mapped_column(String(80))
    input_digest: Mapped[str] = mapped_column(String(64))
    cutoff_sequence: Mapped[int] = mapped_column(Integer)
    # Private bounded structured facts; never export inputs, credentials or transcript.
    input_json: Mapped[dict] = mapped_column(JSON)
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationJob(Base):
    __tablename__ = "evaluation_jobs"
    run_id: Mapped[str] = mapped_column(ForeignKey("scoring_bindings.run_id"), primary_key=True)
    requested_sequence: Mapped[int] = mapped_column(Integer)
    completed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
