"""add stock_prices and momentum_snapshots

Revision ID: 009
Revises: 008
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "stock_prices" not in existing:
        op.create_table(
            "stock_prices",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.Date, nullable=False),
            sa.Column("close", sa.Float, nullable=False),
            sa.UniqueConstraint("stock_id", "date", name="uq_stock_prices_stock_date"),
        )
        op.create_index("ix_stock_prices_stock_id", "stock_prices", ["stock_id"])

    if "momentum_snapshots" not in existing:
        op.create_table(
            "momentum_snapshots",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.Date, nullable=False),
            sa.Column("score", sa.Float, nullable=False),
            sa.Column("mention_count_7d", sa.Integer, nullable=False, server_default="0"),
            sa.Column("mention_count_30d", sa.Integer, nullable=False, server_default="0"),
            sa.Column("avg_sentiment", sa.Float, nullable=False, server_default="0"),
            sa.Column("unique_sources", sa.Integer, nullable=False, server_default="0"),
            sa.Column("share_of_voice", sa.Float, nullable=False, server_default="0"),
            sa.Column("label", sa.String(20)),
            sa.UniqueConstraint("stock_id", "date", name="uq_momentum_snapshots_stock_date"),
        )
        op.create_index("ix_momentum_snapshots_stock_id", "momentum_snapshots", ["stock_id"])
        op.create_index("ix_momentum_snapshots_date", "momentum_snapshots", ["date"])


def downgrade() -> None:
    op.drop_table("momentum_snapshots")
    op.drop_table("stock_prices")
