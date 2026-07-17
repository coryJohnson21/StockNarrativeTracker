"""add is_tracked to themes

Revision ID: 004
Revises: 003
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "themes",
        sa.Column("is_tracked", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("themes", "is_tracked")
