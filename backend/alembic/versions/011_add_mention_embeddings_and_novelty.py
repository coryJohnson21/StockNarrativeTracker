"""add stock_mentions.embedding/novelty and stock_momentum.novelty_7d

Revision ID: 011
Revises: 010
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    mention_cols = _columns("stock_mentions")
    if "embedding" not in mention_cols:
        op.add_column("stock_mentions", sa.Column("embedding", Vector(1536), nullable=True))
    if "novelty" not in mention_cols:
        op.add_column("stock_mentions", sa.Column("novelty", sa.Float, nullable=True))

    if "novelty_7d" not in _columns("stock_momentum"):
        op.add_column("stock_momentum", sa.Column("novelty_7d", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("stock_momentum", "novelty_7d")
    op.drop_column("stock_mentions", "novelty")
    op.drop_column("stock_mentions", "embedding")
