
"""Expand password hash columns to 255 characters."""

from alembic import op
import sqlalchemy as sa

revision = "b7c21d8e4f90"
down_revision = "f4e1c73af19f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "admins",
        "password_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=255),
        existing_nullable=False
    )
    op.alter_column(
        "organization_admins",
        "password_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=255),
        existing_nullable=False
    )


def downgrade():
    op.alter_column(
        "organization_admins",
        "password_hash",
        existing_type=sa.String(length=255),
        type_=sa.String(length=128),
        existing_nullable=False
    )
    op.alter_column(
        "admins",
        "password_hash",
        existing_type=sa.String(length=255),
        type_=sa.String(length=128),
        existing_nullable=False
    )
