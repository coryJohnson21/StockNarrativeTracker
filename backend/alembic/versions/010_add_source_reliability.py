"""add source_reliability and sources.reliability_weight

Revision ID: 010
Revises: 009
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if "reliability_weight" not in {c["name"] for c in inspector.get_columns("sources")}:
        op.add_column("sources", sa.Column("reliability_weight", sa.Float, nullable=False, server_default="1.0"))

    if "source_reliability" not in inspector.get_table_names():
        op.create_table(
            "source_reliability",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("channel_key", sa.String(300), unique=True, nullable=False),
            sa.Column("source_type", sa.String(20)),
            sa.Column("horizon", sa.Integer, nullable=False),
            sa.Column("n_calls", sa.Integer, nullable=False, server_default="0"),
            sa.Column("n_scored", sa.Integer, nullable=False, server_default="0"),
            sa.Column("hits", sa.Integer, nullable=False, server_default="0"),
            sa.Column("hit_rate", sa.Float),
            sa.Column("wilson_lower", sa.Float),
            sa.Column("mean_alpha_pct", sa.Float),
            sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
            sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("source_reliability")
    op.drop_column("sources", "reliability_weight")
