"""Create orders table for one-time purchases."""

from alembic import op
import sqlalchemy as sa

revision = "c8d91f2a6b40"
down_revision = "b7c21d8e4f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("product_code", sa.String(length=100), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payment_provider", sa.String(length=50), nullable=False),
        sa.Column("external_reference", sa.String(length=100), nullable=False, unique=True),
        sa.Column("provider_preference_id", sa.String(length=100), nullable=True, unique=True),
        sa.Column("provider_payment_id", sa.String(length=100), nullable=True, unique=True),
        sa.Column("license_id", sa.Integer(), sa.ForeignKey("licenses.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_orders_customer_email", "orders", ["customer_email"])


def downgrade():
    op.drop_index("ix_orders_customer_email", table_name="orders")
    op.drop_table("orders")
