"""One-off backfill: populate period/teaser/filing_summary/headline-metrics in
source_metadata for SEC filings that were ingested before those fields existed,
reusing the transcript text already stored at ingestion time (no re-fetch from SEC,
no re-run of the full extraction pipeline -- that would duplicate stock/theme
mention rows).

Only touches filings published on or after DEFAULT_SINCE_DATE (2026-01-01) by
default -- pass since_date=None to backfill() to lift that.

Usage (scope to specific tickers first before running for the whole universe):
    docker compose exec backend python -m app.tasks.backfill_filing_period AAPL NVDA
    docker compose exec backend python -m app.tasks.backfill_filing_period   # all tickers
"""
import asyncio
import logging
import sys
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript
from app.services.sec_edgar import TRACKED_FORMS
from app.services.extraction import extract_filing_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bump this whenever extract_filing_details' output shape changes, so a re-run
# repopulates filings that only have the older, thinner set of fields.
FILING_DETAILS_VERSION = 3

# Matches sec_scan.py's BACKFILL_SINCE -- the start of the historical catch-up
# window, so this only ever touches the filings we actually care about.
DEFAULT_SINCE_DATE = "2026-01-01"


async def backfill(tickers: list[str] | None = None, since_date: str | None = DEFAULT_SINCE_DATE) -> dict:
    async with AsyncSessionLocal() as db:
        q = (
            select(Source, Transcript)
            .join(Transcript, Transcript.source_id == Source.id)
            .where(Source.type.in_(TRACKED_FORMS))
            .where(Source.status == "completed")
        )
        if since_date:
            q = q.where(Source.published_at >= datetime.strptime(since_date, "%Y-%m-%d"))
        rows = (await db.execute(q)).all()

        updated = 0
        skipped = 0
        failed = 0
        for source, transcript in rows:
            meta = source.source_metadata or {}
            ticker = meta.get("ticker")
            if tickers and ticker not in tickers:
                continue
            if meta.get("filing_details_version") == FILING_DETAILS_VERSION:
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
                "filing_details_version": FILING_DETAILS_VERSION,
                "period": result["period"],
                "teaser": result["teaser"],
                "filing_summary": result["summary"],
                "revenue": result["revenue"],
                "revenue_yoy_pct": result["revenue_yoy_pct"],
                "revenue_qoq_pct": result["revenue_qoq_pct"],
                "eps": result["eps"],
                "eps_yoy_pct": result["eps_yoy_pct"],
                "eps_qoq_pct": result["eps_qoq_pct"],
                "net_income": result["net_income"],
                "guidance_direction": result["guidance_direction"],
                "capital_returns": result["capital_returns"],
                "strategic_actions": result["strategic_actions"],
            }
            await db.commit()
            updated += 1
            logger.info(
                f"{ticker} {source.title}: period={result['period']!r} revenue={result['revenue']!r} "
                f"eps={result['eps']!r} guidance={result['guidance_direction']!r}"
            )

        return {"updated": updated, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    arg_tickers = [t.upper() for t in sys.argv[1:]] or None
    logger.info("Backfill complete: %s", asyncio.run(backfill(arg_tickers)))
