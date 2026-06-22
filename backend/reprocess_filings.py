import asyncio
import logging
from datetime import datetime
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript, StockMention, ThemeMention
from app.tasks.processing import process_sec_filing_source
from app.services.momentum import refresh_stock_momentum, refresh_theme_momentum

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("reprocess")


async def _wipe_existing(source_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            Transcript.__table__.delete().where(Transcript.source_id == source_id)
        )
        await db.execute(
            StockMention.__table__.delete().where(StockMention.source_id == source_id)
        )
        await db.execute(
            ThemeMention.__table__.delete().where(ThemeMention.source_id == source_id)
        )
        await db.commit()


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Source.id, Source.channel, Source.type)
            .where(Source.type.in_(["10-K", "10-Q"]))
            .where(Source.status == "completed")
            .order_by(Source.created_at)
        )
        targets = result.all()

    total = len(targets)
    logger.info(f"Reprocessing {total} filings")

    failed = []
    for i, (source_id, channel, stype) in enumerate(targets, start=1):
        try:
            await _wipe_existing(source_id)
            await process_sec_filing_source(str(source_id))
        except Exception as e:
            logger.error(f"FAILED {channel} ({stype}) {source_id}: {e}")
            failed.append(str(source_id))

        if i % 25 == 0 or i == total:
            logger.info(f"Progress: {i}/{total} ({channel})")

        if i % 100 == 0:
            async with AsyncSessionLocal() as db:
                await refresh_stock_momentum(db)
                await refresh_theme_momentum(db)
            logger.info("Momentum refreshed (checkpoint)")

    async with AsyncSessionLocal() as db:
        await refresh_stock_momentum(db)
        await refresh_theme_momentum(db)

    logger.info(f"DONE. {total - len(failed)} succeeded, {len(failed)} failed.")
    if failed:
        logger.info("Failed source ids: " + ", ".join(failed))


asyncio.run(main())
