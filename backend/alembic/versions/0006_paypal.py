"""Sandbox payment intents and frozen assessment payment mode."""
from alembic import op
import sqlalchemy as sa

revision = "0006_paypal"
down_revision = "0005_rai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("payment_mode", sa.String(20), nullable=False, server_default="simulated"))
    op.create_table("payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        *[sa.Column(name, sa.String(size), nullable=False) for name, size in (
            ("mode", 20), ("approval_id", 64), ("merchant_id", 32), ("currency", 3),
            ("status", 32), ("callback_hash", 64))],
        sa.Column("cart", sa.JSON(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.String(36), nullable=True, unique=True) for name in ("order_id", "capture_id")],
        *[sa.Column(name, sa.String(36), nullable=False, unique=True) for name in ("create_key", "capture_key")],
        sa.Column("approval_url", sa.String(512), nullable=True),
        sa.Column("operation_token", sa.String(36), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("created_at", "updated_at", "expires_at")],
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=True) for name in ("operation_expires_at", "approved_at", "capture_requested_at", "captured_at")],
        sa.UniqueConstraint("run_id", "approval_id", name="uq_payment_approval"),
        sa.CheckConstraint("mode = 'paypal_sandbox'", name="ck_payment_sandbox"),
        sa.CheckConstraint("amount_minor > 0", name="ck_payment_amount"),
    )
    op.create_index("ix_payments_run_id", "payments", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_run_id", table_name="payments")
    op.drop_table("payments")
    op.drop_column("assessments", "payment_mode")
