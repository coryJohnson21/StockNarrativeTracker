"""add stocks.symbol_status and symbol_checked_at

Records whether a ticker resolves to a real tradeable security, so a hallucinated
symbol ("LILY", "FERC") is distinguishable from a genuinely private company
(OpenAI) -- is_public alone conflated the two, and both merely looked like a
stock with no price.

Revision ID: 014
Revises: 013
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("stocks")}

    if "symbol_status" not in columns:
        # NULL = never checked. Deliberately not defaulted to a verdict: an
        # unchecked ticker is not the same as one we confirmed is fine.
        op.add_column("stocks", sa.Column("symbol_status", sa.String(10), nullable=True))
        op.create_index("ix_stocks_symbol_status", "stocks", ["symbol_status"])
    if "symbol_checked_at" not in columns:
        op.add_column("stocks", sa.Column("symbol_checked_at", sa.DateTime, nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("stocks")}
    if "symbol_checked_at" in columns:
        op.drop_column("stocks", "symbol_checked_at")
    if "symbol_status" in columns:
        op.drop_index("ix_stocks_symbol_status", table_name="stocks")
        op.drop_column("stocks", "symbol_status")
