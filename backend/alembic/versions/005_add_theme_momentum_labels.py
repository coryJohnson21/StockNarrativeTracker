"""add label, previous_label to theme_momentum

Revision ID: 005
Revises: 004
Create Date: 2026-07-20

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("theme_momentum", sa.Column("label", sa.String(20), nullable=True))
    op.add_column("theme_momentum", sa.Column("previous_label", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("theme_momentum", "previous_label")
    op.drop_column("theme_momentum", "label")
