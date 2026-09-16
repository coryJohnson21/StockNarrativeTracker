"""remove calls extracted from SEC filings

Revision ID: 012
Revises: 011
Create Date: 2026-09-16

A company's own filing is not a recommendation. GPT occasionally read "we
expect growth" in a 10-Q as a buy call, and migration 008 lifted those into
stock_calls, where the reliability table then ranked "Fortinet" alongside
podcasts. Calls are now media-only; this removes the ones already stored.
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

FILING_TYPES = ("10-K", "10-Q", "8-K", "earnings_call")


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM stock_calls
        USING sources
        WHERE stock_calls.source_id = sources.id
          AND sources.type IN ({", ".join(f"'{t}'" for t in FILING_TYPES)})
        """
    )


def downgrade() -> None:
    # The rows can be regenerated from sources.metadata->'calls' by re-running the
    # backfill in migration 008; nothing to restore here.
    pass
