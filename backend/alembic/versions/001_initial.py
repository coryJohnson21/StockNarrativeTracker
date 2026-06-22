"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("channel", sa.Text),
        sa.Column("published_at", sa.DateTime),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), unique=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("embedding", Vector(1536)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "stocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(10), unique=True, nullable=False),
        sa.Column("company_name", sa.Text),
        sa.Column("sector", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "themes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "stock_mentions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE")),
        sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE")),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("context", sa.Text),
        sa.Column("mentioned_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_stock_mentions_stock_id", "stock_mentions", ["stock_id"])
    op.create_index("ix_stock_mentions_mentioned_at", "stock_mentions", ["mentioned_at"])

    op.create_table(
        "theme_mentions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE")),
        sa.Column("theme_id", UUID(as_uuid=True), sa.ForeignKey("themes.id", ondelete="CASCADE")),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("context", sa.Text),
        sa.Column("mentioned_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_theme_mentions_theme_id", "theme_mentions", ["theme_id"])
    op.create_index("ix_theme_mentions_mentioned_at", "theme_mentions", ["mentioned_at"])

    op.create_table(
        "stock_momentum",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), unique=True),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("mention_count", sa.Integer, server_default="0"),
        sa.Column("mention_count_7d", sa.Integer, server_default="0"),
        sa.Column("mention_count_30d", sa.Integer, server_default="0"),
        sa.Column("mention_growth_rate", sa.Float, server_default="0"),
        sa.Column("avg_sentiment", sa.Float, server_default="0"),
        sa.Column("unique_sources", sa.Integer, server_default="0"),
        sa.Column("ai_summary", sa.Text),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "theme_momentum",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", UUID(as_uuid=True), sa.ForeignKey("themes.id", ondelete="CASCADE"), unique=True),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("mention_count", sa.Integer, server_default="0"),
        sa.Column("mention_count_7d", sa.Integer, server_default="0"),
        sa.Column("mention_count_30d", sa.Integer, server_default="0"),
        sa.Column("mention_growth_rate", sa.Float, server_default="0"),
        sa.Column("avg_sentiment", sa.Float, server_default="0"),
        sa.Column("unique_sources", sa.Integer, server_default="0"),
        sa.Column("ai_summary", sa.Text),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("theme_momentum")
    op.drop_table("stock_momentum")
    op.drop_table("theme_mentions")
    op.drop_table("stock_mentions")
    op.drop_table("themes")
    op.drop_table("stocks")
    op.drop_table("transcripts")
    op.drop_table("sources")
