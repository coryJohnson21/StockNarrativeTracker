from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.data.sp500 import get_sp500_constituents
from app.tasks.sec_scan import scan_ticker, scan_all_sp500, retry_failed_sec_filings, BACKFILL_SINCE

router = APIRouter(prefix="/sec", tags=["sec"])


@router.get("/sp500")
async def list_sp500():
    """Tracked S&P 500 tickers available for SEC filing ingestion."""
    companies = get_sp500_constituents()
    return {"companies": companies, "total": len(companies)}


@router.post("/scan/{ticker}")
async def scan_one_ticker(ticker: str, since: Optional[str] = Query(None)):
    """Fetch and ingest 10-K/10-Q/8-K-earnings filings for one S&P 500 ticker.
    Defaults to the last 10 days; pass ?since=YYYY-MM-DD for a wider range."""
    try:
        created_ids = await scan_ticker(ticker.upper(), since_date=since)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "ticker": ticker.upper(),
        "new_sources": created_ids,
        "count": len(created_ids),
    }


@router.post("/scan")
async def scan_full_sp500(background_tasks: BackgroundTasks, since: Optional[str] = Query(None)):
    """Kick off a full S&P 500 scan in the background. This can take a long time
    (hundreds of companies, each requiring SEC + OpenAI calls) so it runs async
    and does not block the response. Defaults to the last 10 days."""
    background_tasks.add_task(scan_all_sp500, since)
    return {"status": "started", "detail": "Full S&P 500 scan running in the background"}


@router.post("/backfill")
async def backfill_sp500(background_tasks: BackgroundTasks):
    """One-time historical catch-up: ingest every 10-K/10-Q/8-K-earnings filing for
    all S&P 500 companies since {BACKFILL_SINCE}. Runs in the background; expect this
    to take roughly an hour and to make a meaningful number of OpenAI API calls."""
    background_tasks.add_task(scan_all_sp500, BACKFILL_SINCE)
    return {
        "status": "started",
        "detail": f"Full S&P 500 backfill since {BACKFILL_SINCE} running in the background",
    }


@router.post("/retry-failed")
async def retry_failed(background_tasks: BackgroundTasks):
    """Re-process SEC filing sources currently marked 'failed' (mainly rate-limit
    failures from before retry-with-backoff was added)."""
    background_tasks.add_task(retry_failed_sec_filings)
    return {"status": "started", "detail": "Retrying failed SEC filings in the background"}
