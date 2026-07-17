"""add impact_analysis to theme_profiles

Revision ID: 003
Revises: 002
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("theme_profiles", sa.Column("impact_analysis", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("theme_profiles", "impact_analysis")
