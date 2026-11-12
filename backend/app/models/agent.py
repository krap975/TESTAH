from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(300), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    endpoint_url: Mapped[str] = mapped_column(String(2048))
    connection_mode: Mapped[str] = mapped_column(String(20), default="external")
    auth_header_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    auth_secret_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_test_status: Mapped[str] = mapped_column(String(20), default="not_tested")
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(String(300), nullable=True)

    revision: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": revision}

    @property
    def authentication_configured(self) -> bool:
        return self.auth_secret_key is not None

