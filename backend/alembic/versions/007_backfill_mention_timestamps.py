"""backfill mentioned_at from the source's publish date

Revision ID: 007
Revises: 006
Create Date: 2026-09-15

Mentions used to be stamped with ingest time. For anything backfilled (SEC
filings since January, podcast back-catalogs) that put months-old statements
on "today", inflating 7-day counts and fabricating growth spikes. Re-point
every mention at its source's publish date where one is known.
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("stock_mentions", "theme_mentions"):
        op.execute(
            f"""
            UPDATE {table} AS m
            SET mentioned_at = s.published_at
            FROM sources AS s
            WHERE m.source_id = s.id
              AND s.published_at IS NOT NULL
              AND m.mentioned_at <> s.published_at
            """
        )


def downgrade() -> None:
    # Ingest-time stamps are not recoverable; the closest proxy is created_at.
    for table in ("stock_mentions", "theme_mentions"):
        op.execute(
            f"""
            UPDATE {table} AS m
            SET mentioned_at = s.created_at
            FROM sources AS s
            WHERE m.source_id = s.id AND s.created_at IS NOT NULL
            """
        )
