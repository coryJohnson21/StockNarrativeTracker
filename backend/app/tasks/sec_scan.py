import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source
from app.data.sp500 import get_sp500_constituents, find_company
from app.services import sec_edgar
from app.tasks.processing import process_sec_filing_source

logger = logging.getLogger(__name__)

# One-time historical catch-up starts here; the periodic job only needs a short
# rolling window since dedup-by-URL means re-scanning further back is wasted SEC traffic.
BACKFILL_SINCE = "2026-01-01"

# The account's gpt-4o tier caps at 30K tokens/minute — concurrency beyond 1 just
# produces more 429s rather than more throughput, since the limit is per-minute, not
# per-connection. Retry-with-backoff in extraction.py/embeddings.py handles the rest.
_PROCESSING_CONCURRENCY = 1
_processing_semaphore = asyncio.Semaphore(_PROCESSING_CONCURRENCY)


def recent_window_since(days: int = 10) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")


async def _discover_ticker(ticker: str, since_date: str) -> List[str]:
    """Fetch filings since since_date for one ticker, create Source rows for new ones
    (deduped by URL), and return their ids. Does not process them."""
    company = find_company(ticker)
    if company is None:
        raise ValueError(f"{ticker} is not in the tracked S&P 500 list")

    async with httpx.AsyncClient() as client:
        filings = await sec_edgar.get_filings_since(client, company["cik"], since_date)

    created_ids = []
    async with AsyncSessionLocal() as db:
        for filing in filings:
            existing = await db.execute(select(Source).where(Source.url == filing["document_url"]))
            if existing.scalar_one_or_none() is not None:
                continue

            source = Source(
                type=filing["form"],
                url=filing["document_url"],
                title=f"{ticker} {filing['form']} — {filing['filing_date']}",
                channel=company["company"],
                published_at=datetime.strptime(filing["filing_date"], "%Y-%m-%d"),
                status="pending",
                source_metadata={
                    "ticker": ticker,
                    "cik": company["cik"],
                    "accession_number": filing["accession_number"],
                    "is_exhibit": filing["is_exhibit"],
                },
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            created_ids.append(str(source.id))

    return created_ids


async def _process_bounded(source_id: str) -> None:
    async with _processing_semaphore:
        await process_sec_filing_source(source_id)


async def scan_ticker(ticker: str, since_date: str = None) -> List[str]:
    """Fetch and ingest filings for one S&P 500 ticker since since_date (default: last 10 days)."""
    since_date = since_date or recent_window_since()
    created_ids = await _discover_ticker(ticker, since_date)
    await asyncio.gather(*(_process_bounded(sid) for sid in created_ids))
    return created_ids


async def scan_all_sp500(since_date: str = None) -> dict:
    """Scan every tracked S&P 500 company for filings since since_date (default: last 10 days).
    Discovery runs ticker-by-ticker (SEC rate-limited); processing runs with bounded
    concurrency across the whole batch. Long-running for wide date ranges — meant for
    a background task."""
    since_date = since_date or recent_window_since()
    companies = get_sp500_constituents()
    all_new_ids: List[str] = []
    failed_tickers = []

    for company in companies:
        try:
            all_new_ids += await _discover_ticker(company["ticker"], since_date)
        except Exception:
            logger.exception(f"SEC discovery failed for {company['ticker']}")
            failed_tickers.append(company["ticker"])

    logger.info(f"SEC discovery complete: {len(all_new_ids)} new filings to process")
    await asyncio.gather(*(_process_bounded(sid) for sid in all_new_ids))

    logger.info(
        f"SEC scan complete: {len(all_new_ids)} new filings ingested, {len(failed_tickers)} tickers failed discovery"
    )
    return {"new_filings": len(all_new_ids), "failed_tickers": failed_tickers}


async def retry_failed_sec_filings() -> dict:
    """Re-process SEC filing sources currently marked 'failed' (e.g. ones that hit
    rate limits before retry-with-backoff was added). Safe to call repeatedly."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Source.id).where(Source.status == "failed", Source.type.in_(sec_edgar.TRACKED_FORMS))
        )
        ids = [str(row[0]) for row in result.all()]

    logger.info(f"Retrying {len(ids)} failed SEC filings")
    await asyncio.gather(*(_process_bounded(sid) for sid in ids))
    return {"retried": len(ids)}
