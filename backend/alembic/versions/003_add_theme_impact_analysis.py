"""add impact_analysis to theme_profiles

Revision ID: 003
Revises: 002
Create Date: 2026-07-13

theme_profiles was never created by an earlier migration (only by create_all at app
startup), so on a fresh database this has to create the table itself rather than
add a column to a table that doesn't exist.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "theme_profiles" not in inspector.get_table_names():
        op.create_table(
            "theme_profiles",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("theme_id", UUID(as_uuid=True), sa.ForeignKey("themes.id", ondelete="CASCADE"), unique=True),
            sa.Column("description", sa.Text),
            sa.Column("impact_analysis", JSONB, nullable=True),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )
        return

    columns = {c["name"] for c in inspector.get_columns("theme_profiles")}
    if "impact_analysis" not in columns:
        op.add_column("theme_profiles", sa.Column("impact_analysis", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("theme_profiles", "impact_analysis")
