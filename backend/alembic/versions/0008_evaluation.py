"""Phase 8: additive deterministic evaluations and durable requests."""
from alembic import op
import sqlalchemy as sa

revision = "0008_evaluation"
down_revision = "0007_paypal_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("scoring_bindings",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("assessments.id"), primary_key=True),
        sa.Column("version", sa.String(80), nullable=False), sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False), sa.Column("assignment", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("version", sa.String(80), nullable=False), sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("cutoff_sequence", sa.Integer(), nullable=False), sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "version", "input_digest", name="uq_evaluation_inputs"))
    op.create_index("ix_evaluations_run_id", "evaluations", ["run_id"])
    op.create_table("evaluation_jobs",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("scoring_bindings.run_id"), primary_key=True),
        sa.Column("requested_sequence", sa.Integer(), nullable=False),
        sa.Column("completed_sequence", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False))


def downgrade() -> None:
    op.drop_table("evaluation_jobs")
    op.drop_index("ix_evaluations_run_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("scoring_bindings")
