"""Isolated execution aggregates and ordered durable evidence."""
from alembic import op
import sqlalchemy as sa

revision = "0004_execution"
down_revision = "0003_environments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("environment_id", sa.String(36), sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("environment_name", sa.String(100), nullable=False),
        *[sa.Column(name, sa.JSON(), nullable=False) for name in ("agent_config", "blueprint_json", "runtime_json", "limits")],
        sa.Column("protocol_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("termination_reason", sa.String(80), nullable=True),
        sa.Column("failure_origin", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=True) for name in ("started_at", "ended_at", "lease_expires_at")],
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('created','running','completed','failed','cancelled','inconclusive')", name="ck_assessment_status"),
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_event_sequence"),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_table("assessments")
