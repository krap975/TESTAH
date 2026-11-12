"""Phase 7: bind new payment intents to their server-owned PayPal app."""
from alembic import op
import sqlalchemy as sa

revision = "0007_paypal_binding"
down_revision = "0006_paypal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("client_binding", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "client_binding")
