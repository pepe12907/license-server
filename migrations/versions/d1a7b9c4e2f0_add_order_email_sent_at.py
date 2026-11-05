"""Add email delivery tracking to orders."""

from alembic import op
import sqlalchemy as sa

revision="d1a7b9c4e2f0"
down_revision="c8d91f2a6b40"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("orders",sa.Column("email_sent_at",sa.DateTime(),nullable=True))


def downgrade():
    op.drop_column("orders","email_sent_at")
