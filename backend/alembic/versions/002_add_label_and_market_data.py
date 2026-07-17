"""add label, previous_label, current_price, market_cap to stock_momentum

Revision ID: 002
Revises: 001
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stock_momentum", sa.Column("label", sa.String(20), nullable=True))
    op.add_column("stock_momentum", sa.Column("previous_label", sa.String(20), nullable=True))
    op.add_column("stock_momentum", sa.Column("current_price", sa.Float, nullable=True))
    op.add_column("stock_momentum", sa.Column("market_cap", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("stock_momentum", "market_cap")
    op.drop_column("stock_momentum", "current_price")
    op.drop_column("stock_momentum", "previous_label")
    op.drop_column("stock_momentum", "label")
