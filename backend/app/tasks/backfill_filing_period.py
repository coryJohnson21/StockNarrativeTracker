"""One-off backfill: populate period/teaser/filing_summary in source_metadata for SEC
filings that were ingested before those fields existed, reusing the transcript text
already stored at ingestion time (no re-fetch from SEC, no re-run of the full
extraction pipeline -- that would duplicate stock/theme mention rows).

Usage (scope to specific tickers first before running for the whole universe):
    docker compose exec backend python -m app.tasks.backfill_filing_period AAPL NVDA
    docker compose exec backend python -m app.tasks.backfill_filing_period   # all tickers
"""
import asyncio
import logging
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript
from app.services.sec_edgar import TRACKED_FORMS
from app.services.extraction import extract_filing_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill(tickers: list[str] | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        q = (
            select(Source, Transcript)
            .join(Transcript, Transcript.source_id == Source.id)
            .where(Source.type.in_(TRACKED_FORMS))
            .where(Source.status == "completed")
        )
        rows = (await db.execute(q)).all()

        updated = 0
        skipped = 0
        failed = 0
        for source, transcript in rows:
            meta = source.source_metadata or {}
            ticker = meta.get("ticker")
            if tickers and ticker not in tickers:
                continue
            if meta.get("filing_summary"):
                skipped += 1
                continue
            try:
                result = await extract_filing_details(transcript.content, source.title or "")
            except Exception:
                logger.exception(f"Failed to backfill {source.id} ({ticker})")
                failed += 1
                continue
            source.source_metadata = {
                **meta,
                "period": result["period"],
                "teaser": result["teaser"],
                "filing_summary": result["summary"],
            }
            await db.commit()
            updated += 1
            logger.info(f"{ticker} {source.title}: period={result['period']!r} teaser={result['teaser']!r}")

        return {"updated": updated, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    arg_tickers = [t.upper() for t in sys.argv[1:]] or None
    print(asyncio.run(backfill(arg_tickers)))
