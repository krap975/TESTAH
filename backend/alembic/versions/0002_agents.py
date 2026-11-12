"""Persist registered agents and safe connection-test metadata."""
from alembic import op
import sqlalchemy as sa
revision = "0002_agents"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("endpoint_url", sa.String(2048), nullable=False),
        sa.Column("connection_mode", sa.String(20), nullable=False),
        sa.Column("auth_header_name", sa.String(30), nullable=True),
        sa.Column("auth_secret_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_test_status", sa.String(20), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_code", sa.String(40), nullable=True),
        sa.Column("last_test_message", sa.String(300), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name_key"),
    )

def downgrade() -> None:
    op.drop_table("agents")

