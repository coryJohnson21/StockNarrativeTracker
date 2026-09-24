"""Resolve every tracked ticker against Yahoo and record the verdict.

New stocks are checked when created (tasks/processing.py). This backfills rows that
predate that, and can be re-run to recheck: a symbol can start resolving (a company
IPOs) or stop (delisting, acquisition).

Rows whose lookup fails are left unchanged rather than marked, so a rate limit or a
network blip never turns into a false "this ticker isn't real".

Usage:
    python validate_symbols.py                  # only rows never checked
    python validate_symbols.py --all            # recheck everything
    python validate_symbols.py --dry-run        # report, change nothing
    python validate_symbols.py --only LILY,FERC # specific tickers
"""
import asyncio
import logging
import sys
from collections import Counter
from datetime import datetime

import httpx
from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.models import Stock, StockMention
from app.services.symbols import resolve_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("validate")

_DELAY = 0.3


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    recheck_all = "--all" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = {t.strip().upper() for t in sys.argv[sys.argv.index("--only") + 1].split(",")}

    async with AsyncSessionLocal() as db:
        q = select(Stock).order_by(Stock.ticker)
        if only:
            q = q.where(Stock.ticker.in_(only))
        elif not recheck_all:
            q = q.where(Stock.symbol_status.is_(None))
        stocks = (await db.execute(q)).scalars().all()

        logger.info("checking %d tickers", len(stocks))
        counts: Counter = Counter()
        failed = 0

        async with httpx.AsyncClient() as client:
            for i, stock in enumerate(stocks):
                result = await resolve_symbol(stock.ticker, client)
                if result is None:
                    failed += 1
                    counts["lookup failed"] += 1
                else:
                    verdict = result["verdict"]
                    counts[verdict] += 1
                    if verdict != "ok":
                        mentions = (
                            await db.execute(
                                select(StockMention.id).where(StockMention.stock_id == stock.id).limit(50)
                            )
                        ).all()
                        logger.info(
                            "  %-10s %-9s %-10s %s (%d mentions)",
                            stock.ticker, verdict, result["instrument_type"] or "-",
                            (stock.company_name or "")[:40], len(mentions),
                        )
                    if not dry_run:
                        stock.symbol_status = verdict
                        stock.symbol_checked_at = datetime.utcnow()
                if i % 50 == 0 and i:
                    logger.info("  ... %d/%d", i, len(stocks))
                    if not dry_run:
                        await db.commit()
                await asyncio.sleep(_DELAY)

        if not dry_run:
            await db.commit()

    logger.info("summary: %s", dict(counts))
    if failed:
        logger.info("%d lookups failed and were left unchanged -- re-run to retry them", failed)


if __name__ == "__main__":
    asyncio.run(main())
