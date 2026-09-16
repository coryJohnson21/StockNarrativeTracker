"""add tables/columns that were only ever created via Base.metadata.create_all

Revision ID: 006
Revises: 005
Create Date: 2026-09-15

Dev databases were bootstrapped by create_all on app startup, so every object here may
or may not already exist. Each step checks the live schema first so this migration is
safe on both a fresh database and one that create_all has already populated.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    if not _has_column("stocks", "is_public"):
        op.add_column("stocks", sa.Column("is_public", sa.Boolean, nullable=True))

    if not _has_column("stock_mentions", "is_self_mention"):
        op.add_column(
            "stock_mentions",
            sa.Column("is_self_mention", sa.Boolean, nullable=False, server_default="false"),
        )

    if not _has_table("stock_profiles"):
        op.create_table(
            "stock_profiles",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), unique=True),
            sa.Column("description", sa.Text),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table("stock_narratives"):
        op.create_table(
            "stock_narratives",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), unique=True),
            sa.Column("summary", sa.Text),
            sa.Column("mention_count_snapshot", sa.Integer, server_default="0"),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table("reddit_feeds"):
        op.create_table(
            "reddit_feeds",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("subreddit", sa.String(100), unique=True, nullable=False),
            sa.Column("last_polled_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table("watchlist_items"):
        op.create_table(
            "watchlist_items",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("ticker", sa.String(10), unique=True, nullable=False),
            sa.Column("added_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table("podcast_feeds"):
        op.create_table(
            "podcast_feeds",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("url", sa.String(1000), unique=True, nullable=False),
            sa.Column("label", sa.String(200), nullable=False),
            sa.Column("source_type", sa.String(20), server_default="podcast"),
            sa.Column("last_polled_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("podcast_feeds")
    op.drop_table("watchlist_items")
    op.drop_table("reddit_feeds")
    op.drop_table("stock_narratives")
    op.drop_table("stock_profiles")
    op.drop_column("stock_mentions", "is_self_mention")
    op.drop_column("stocks", "is_public")
