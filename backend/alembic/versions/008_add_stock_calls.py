"""add stock_calls and backfill from source metadata

Revision ID: 008
Revises: 007
Create Date: 2026-09-15

Explicit buy/sell/hold calls have been extracted since the beginning but only
stored inside sources.metadata->'calls', where nothing could query them. This
gives them a table and lifts every existing call whose ticker we track.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "stock_calls" not in inspector.get_table_names():
        op.create_table(
            "stock_calls",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("call", sa.String(10), nullable=False),
            sa.Column("price_target", sa.Float),
            sa.Column("reasoning", sa.Text),
            sa.Column("called_at", sa.DateTime, nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.UniqueConstraint("source_id", "stock_id", name="uq_stock_calls_source_stock"),
        )
        op.create_index("ix_stock_calls_stock_id", "stock_calls", ["stock_id"])
        op.create_index("ix_stock_calls_called_at", "stock_calls", ["called_at"])

    op.execute(
        """
        INSERT INTO stock_calls (id, source_id, stock_id, call, price_target, reasoning, called_at, created_at)
        SELECT DISTINCT ON (s.id, st.id)
            gen_random_uuid(),
            s.id,
            st.id,
            c->>'call',
            CASE WHEN (c->>'price_target') ~ '^[0-9]+(\\.[0-9]+)?$' THEN (c->>'price_target')::float END,
            left(c->>'reasoning', 400),
            COALESCE(s.published_at, s.created_at, now()),
            now()
        FROM sources AS s
        CROSS JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof(s.metadata->'calls') = 'array' THEN s.metadata->'calls' ELSE '[]'::jsonb END
        ) AS c
        JOIN stocks AS st ON st.ticker = upper(trim(c->>'ticker'))
        WHERE c->>'call' IN ('buy', 'sell', 'hold', 'avoid', 'watch')
        ON CONFLICT (source_id, stock_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("stock_calls")
