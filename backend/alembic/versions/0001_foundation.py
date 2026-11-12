"""Migration baseline; Alembic maintains alembic_version.

Domain tables belong to future scoped phases.
"""
revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
