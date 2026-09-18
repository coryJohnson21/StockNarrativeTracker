"""add insider_transactions and momentum_snapshots.insider_net_90d

Revision ID: 013
Revises: 012
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if "insider_transactions" not in inspector.get_table_names():
        op.create_table(
            "insider_transactions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("stock_id", UUID(as_uuid=True), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("accession_number", sa.String(25), nullable=False),
            sa.Column("seq", sa.Integer, nullable=False),
            sa.Column("filed_at", sa.Date, nullable=False),
            sa.Column("transaction_date", sa.Date, nullable=False),
            sa.Column("owner_name", sa.String(300), nullable=False),
            sa.Column("owner_role", sa.String(300)),
            sa.Column("transaction_code", sa.String(2), nullable=False),
            sa.Column("is_purchase", sa.Boolean, nullable=False),
            sa.Column("shares", sa.Float, nullable=False),
            sa.Column("price", sa.Float),
            sa.Column("value", sa.Float),
            sa.Column("shares_owned_after", sa.Float),
            sa.Column("is_10b5_1", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("filing_url", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.UniqueConstraint("accession_number", "seq", name="uq_insider_transactions_accession_seq"),
        )
        op.create_index("ix_insider_transactions_stock_id", "insider_transactions", ["stock_id"])
        op.create_index("ix_insider_transactions_filed_at", "insider_transactions", ["filed_at"])

    if "insider_net_90d" not in {c["name"] for c in inspector.get_columns("momentum_snapshots")}:
        op.add_column("momentum_snapshots", sa.Column("insider_net_90d", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("momentum_snapshots", "insider_net_90d")
    op.drop_table("insider_transactions")
