"""One durable PayPal intent per assessment authorization; never store provider bodies."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.models.agent import utcnow


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("run_id", "approval_id", name="uq_payment_approval"),
        CheckConstraint("mode = 'paypal_sandbox'", name="ck_payment_sandbox"),
        CheckConstraint("amount_minor > 0", name="ck_payment_amount"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="paypal_sandbox")
    approval_id: Mapped[str] = mapped_column(String(64))
    cart: Mapped[dict] = mapped_column(JSON)
    merchant_id: Mapped[str] = mapped_column(String(32))
    client_binding: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), default="requested")
    order_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    capture_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    approval_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    callback_hash: Mapped[str] = mapped_column(String(64))
    create_key: Mapped[str] = mapped_column(String(36), unique=True)
    capture_key: Mapped[str] = mapped_column(String(36), unique=True)
    operation_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
