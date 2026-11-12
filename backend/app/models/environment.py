from datetime import datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.models.agent import utcnow

class EnvironmentTemplate(Base):
    __tablename__ = "environment_templates"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        ForeignKeyConstraint(["template_id", "template_version"], ["environment_templates.id", "environment_templates.version"]),
        CheckConstraint("budget_minor > 0", name="ck_environment_positive_budget"),
        CheckConstraint("status = 'compiled'", name="ck_environment_compiled_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    template_id: Mapped[str] = mapped_column(String(128))
    template_version: Mapped[str] = mapped_column(String(20))
    blueprint_version: Mapped[str] = mapped_column(String(20))
    blueprint_json: Mapped[dict] = mapped_column(JSON)
    currency: Mapped[str] = mapped_column(String(3))
    budget_minor: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="compiled")
    generation_mode: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    designer_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Reserved for a future authenticated scope. Null means unowned local workspace.
    owner_scope_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

