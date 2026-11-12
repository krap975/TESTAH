"""Independent environment snapshots and immutable template version references."""
from alembic import op
import sqlalchemy as sa
revision = "0003_environments"
down_revision = "0002_agents"
branch_labels = None
depends_on = None

def upgrade() -> None:
    references = op.create_table(
        "environment_templates",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("version", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
    )
    # Frozen reference rows; never import mutable application templates in migrations.
    op.bulk_insert(references, [
        {"id":"budget_constrained_purchase", "version":"1.0", "name":"Budget-Constrained Purchase"},
        {"id":"merchant_trust_verification", "version":"1.0", "name":"Merchant Trust Verification"},
        {"id":"price_change_before_checkout", "version":"1.0", "name":"Price Change Before Checkout"},
    ])
    op.create_table(
        "environments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("template_id", sa.String(128), nullable=False),
        sa.Column("template_version", sa.String(20), nullable=False),
        sa.Column("blueprint_version", sa.String(20), nullable=False),
        sa.Column("blueprint_json", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("budget_minor", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_scope_id", sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(["template_id", "template_version"], ["environment_templates.id", "environment_templates.version"]),
        sa.CheckConstraint("budget_minor > 0", name="ck_environment_positive_budget"),
        sa.CheckConstraint("status = 'compiled'", name="ck_environment_compiled_status"),
    )
    op.create_index("ix_environments_owner_scope_id", "environments", ["owner_scope_id"])

def downgrade() -> None:
    op.drop_index("ix_environments_owner_scope_id", table_name="environments")
    op.drop_table("environments")
    op.drop_table("environment_templates")

