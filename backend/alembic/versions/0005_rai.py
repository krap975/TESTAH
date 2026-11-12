"""RAI proposals, ordered proposal evidence, and backwards-compatible customer mode."""
from alembic import op
import sqlalchemy as sa

revision = "0005_rai"
down_revision = "0004_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("environments", sa.Column("generation_mode", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("environments", sa.Column("designer_model", sa.String(100), nullable=True))
    op.add_column("assessments", sa.Column("examiner_mode", sa.String(20), nullable=False, server_default="deterministic"))
    op.add_column("assessments", sa.Column("examiner_provider", sa.String(20), nullable=False, server_default="none"))
    op.add_column("assessments", sa.Column("examiner_model", sa.String(100), nullable=True))
    op.add_column("assessments", sa.Column("examiner_config", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table("rai_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        *[sa.Column(name, sa.String(size), nullable=False) for name, size in (("status", 20), ("provider", 20), ("model", 100))],
        *[sa.Column(name, sa.JSON(), nullable=False) for name in ("capability_summary", "validation_json", "provider_config")],
        *[sa.Column(name, sa.JSON(), nullable=True) for name in ("proposal_json", "blueprint_json")],
        sa.Column("environment_id", sa.String(36), sa.ForeignKey("environments.id"), nullable=True, unique=True),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("created_at", "updated_at")],
        *[sa.Column(name, sa.Integer(), nullable=False) for name in ("revision", "event_sequence")],
        sa.UniqueConstraint("agent_id", "request_key", name="uq_rai_proposal_request"),
        sa.CheckConstraint("status IN ('generating','ready','failed','compiled')", name="ck_rai_proposal_status"),
    )
    op.create_table("rai_proposal_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("rai_proposals.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("proposal_id", "sequence", name="uq_rai_proposal_event_sequence"),
    )
    op.create_index("ix_rai_proposal_events_proposal_id", "rai_proposal_events", ["proposal_id"])


def downgrade() -> None:
    op.drop_index("ix_rai_proposal_events_proposal_id", table_name="rai_proposal_events")
    op.drop_table("rai_proposal_events")
    op.drop_table("rai_proposals")
    for name in ("examiner_config", "examiner_model", "examiner_provider", "examiner_mode"):
        op.drop_column("assessments", name)
    for name in ("designer_model", "generation_mode"):
        op.drop_column("environments", name)
