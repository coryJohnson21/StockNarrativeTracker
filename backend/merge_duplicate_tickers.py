"""Merge a stock row created under a wrong ticker into the correct one.

GPT sometimes emits a company name where a symbol belongs -- "LILY" for Eli Lilly,
"AMEX" for American Express -- which creates a second stocks row that no price feed
can ever resolve. _TICKER_ALIASES in services/extraction.py stops new ones appearing;
this moves the rows that already exist onto the real ticker and deletes the stray.

Mentions, calls, insider transactions, and snapshots are repointed; per-stock
singletons (momentum, profile, narrative) and prices are left on the surviving row,
since the duplicate's are empty or stale by construction. Momentum is recomputed at
the end so counts reflect the merge.

Usage:
    python merge_duplicate_tickers.py            # apply the built-in pairs
    python merge_duplicate_tickers.py --dry-run  # report only
    python merge_duplicate_tickers.py LILY:LLY   # a specific pair
"""
import asyncio
import logging
import sys

from sqlalchemy import delete, select, text, update

from app.database import AsyncSessionLocal
from app.models.models import (
    InsiderTransaction, MomentumSnapshot, Stock, StockCall, StockMention,
    StockMomentum, StockNarrative, StockPrice, StockProfile,
)
from app.services.momentum import refresh_stock_momentum

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("merge")

# wrong ticker -> real ticker. Keep in step with _TICKER_ALIASES.
DEFAULT_PAIRS = [
    ("LILY", "LLY"),
    ("AMEX", "AXP"),
    ("TSMC", "TSM"),
    ("REDDIT", "RDDT"),
    ("NEBIUS", "NBIS"),
]

# Tables holding at most one row per stock, or rows the good ticker already has
# from a real price feed. The duplicate's copies are dropped rather than moved.
_DROP_FROM_DUPLICATE = (StockMomentum, StockProfile, StockNarrative, StockPrice)


async def merge_pair(db, wrong: str, right: str, dry_run: bool) -> bool:
    dup = (await db.execute(select(Stock).where(Stock.ticker == wrong))).scalar_one_or_none()
    if dup is None:
        logger.info("%s: no such row, nothing to merge", wrong)
        return False

    good = (await db.execute(select(Stock).where(Stock.ticker == right))).scalar_one_or_none()
    if good is None:
        # Nothing to merge into -- just correct the ticker in place, keeping mentions.
        logger.info("%s -> %s: no existing %s row, renaming in place", wrong, right, right)
        if not dry_run:
            dup.ticker = right
            await db.commit()
        return True

    counts = {}
    for model in (StockMention, StockCall, InsiderTransaction, MomentumSnapshot):
        counts[model.__tablename__] = (
            await db.execute(
                select(text("count(*)")).select_from(model.__table__).where(model.stock_id == dup.id)
            )
        ).scalar_one()
    logger.info("%s -> %s: moving %s", wrong, right, counts)

    if dry_run:
        return True

    # stock_calls is unique on (source_id, stock_id): if the same source already
    # called the good ticker, the duplicate's call is redundant -- drop it.
    await db.execute(
        delete(StockCall).where(
            StockCall.stock_id == dup.id,
            StockCall.source_id.in_(select(StockCall.source_id).where(StockCall.stock_id == good.id)),
        )
    )
    # momentum_snapshots is unique on (stock_id, date). Both rows can hold a snapshot
    # for the same day; the good ticker's is the one built against real prices, so
    # drop the duplicate's rather than colliding on the update.
    await db.execute(
        delete(MomentumSnapshot).where(
            MomentumSnapshot.stock_id == dup.id,
            MomentumSnapshot.date.in_(
                select(MomentumSnapshot.date).where(MomentumSnapshot.stock_id == good.id)
            ),
        )
    )
    for model in (StockMention, StockCall, InsiderTransaction, MomentumSnapshot):
        await db.execute(update(model).where(model.stock_id == dup.id).values(stock_id=good.id))
    for model in _DROP_FROM_DUPLICATE:
        await db.execute(delete(model).where(model.stock_id == dup.id))

    # Carry over any detail the good row is missing before dropping the duplicate.
    if not good.company_name and dup.company_name:
        good.company_name = dup.company_name
    if not good.sector and dup.sector:
        good.sector = dup.sector

    await db.execute(delete(Stock).where(Stock.id == dup.id))
    await db.commit()
    return True


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry_run = "--dry-run" in sys.argv
    pairs = [tuple(a.split(":", 1)) for a in args] if args else DEFAULT_PAIRS

    merged = False
    async with AsyncSessionLocal() as db:
        for wrong, right in pairs:
            merged |= await merge_pair(db, wrong.upper(), right.upper(), dry_run)

    if merged and not dry_run:
        logger.info("recomputing momentum")
        async with AsyncSessionLocal() as db:
            await refresh_stock_momentum(db)
    logger.info("done%s", " (dry run)" if dry_run else "")


if __name__ == "__main__":
    asyncio.run(main())
