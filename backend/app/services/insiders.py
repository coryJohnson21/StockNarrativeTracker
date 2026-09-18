"""Insider open-market trading from Form 4 filings: ingestion for the tracked
universe, per-stock summaries, and the net-buying ratio that feeds the signals
and the backtest."""
import logging
import uuid
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.sp500 import get_sp500_constituents, find_company
from app.database import AsyncSessionLocal
from app.models.models import InsiderTransaction, Stock
from app.services import sec_edgar
from app.services.form4 import parse_form4

logger = logging.getLogger(__name__)

SUMMARY_WINDOW_DAYS = 90
CLUSTER_WINDOW_DAYS = 30
CLUSTER_MIN_BUYERS = 3
_INSERT_CHUNK = 1000


def net_buy_ratio(buy_value: float, sell_value: float) -> Optional[float]:
    """(buys - sells) / (buys + sells) in dollars: +1 all buying, -1 all selling,
    None when nobody traded."""
    total = buy_value + sell_value
    if total <= 0:
        return None
    return round((buy_value - sell_value) / total, 3)


# --- ingestion -----------------------------------------------------------------


async def _known_accessions(db: AsyncSession, stock_id) -> set[str]:
    rows = await db.execute(
        select(InsiderTransaction.accession_number).where(InsiderTransaction.stock_id == stock_id).distinct()
    )
    return {a for (a,) in rows.all()}


async def scan_ticker_insiders(client: httpx.AsyncClient, db: AsyncSession, ticker: str, since_date: str) -> int:
    company = find_company(ticker)
    if company is None:
        raise ValueError(f"{ticker} is not in the tracked S&P 500 list")

    stock = (await db.execute(select(Stock).where(Stock.ticker == ticker))).scalar_one_or_none()
    if stock is None:
        stock = Stock(ticker=ticker, company_name=company["company"])
        db.add(stock)
        await db.flush()

    filings = await sec_edgar.get_form4_filings_since(client, company["cik"], since_date)
    known = await _known_accessions(db, stock.id)
    rows: list[dict] = []
    for filing in filings:
        if filing["accession_number"] in known:
            continue
        try:
            form = parse_form4(await sec_edgar.fetch_text(client, filing["document_url"]))
        except Exception:
            logger.warning("Could not parse Form 4 %s for %s", filing["accession_number"], ticker)
            continue
        filed_at = date.fromisoformat(filing["filing_date"])
        for seq, tx in enumerate(form.transactions):
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "stock_id": stock.id,
                    "accession_number": filing["accession_number"],
                    "seq": seq,
                    "filed_at": filed_at,
                    "transaction_date": tx.transaction_date,
                    "owner_name": tx.owner_name[:300],
                    "owner_role": (tx.owner_role or "")[:300] or None,
                    "transaction_code": tx.transaction_code,
                    "is_purchase": tx.is_purchase,
                    "shares": tx.shares,
                    "price": tx.price,
                    "value": tx.value,
                    "shares_owned_after": tx.shares_owned_after,
                    "is_10b5_1": tx.is_10b5_1,
                    "filing_url": filing["document_url"],
                }
            )
    # Postgres caps a statement at 32767 bind parameters; at 17 columns per row a
    # single insert of more than ~1900 rows is rejected outright, which a year of
    # Form 4s for a heavily-traded issuer easily exceeds. Chunk, as the momentum
    # snapshot upsert does.
    for i in range(0, len(rows), _INSERT_CHUNK):
        stmt = pg_insert(InsiderTransaction).values(rows[i:i + _INSERT_CHUNK]).on_conflict_do_nothing(
            constraint="uq_insider_transactions_accession_seq"
        )
        await db.execute(stmt)
    await db.commit()
    return len(rows)


async def scan_insider_transactions(since_date: str, tickers: Optional[list[str]] = None) -> dict:
    """Pull Form 4s for every tracked company (or the given tickers) filed on or
    after since_date. Rate-limited by sec_edgar._get; a full S&P 500 pass over a
    few months is thousands of small XML fetches, so run it in the background."""
    companies = get_sp500_constituents()
    if tickers:
        wanted = {t.upper() for t in tickers}
        companies = [c for c in companies if c["ticker"] in wanted]

    inserted = 0
    failed: list[str] = []
    async with httpx.AsyncClient() as client:
        for company in companies:
            try:
                async with AsyncSessionLocal() as db:
                    inserted += await scan_ticker_insiders(client, db, company["ticker"], since_date)
            except Exception:
                logger.exception("Insider scan failed for %s", company["ticker"])
                failed.append(company["ticker"])
    logger.info("Insider scan complete: %d transactions inserted, %d tickers failed", inserted, len(failed))
    return {"transactions_inserted": inserted, "tickers_scanned": len(companies), "failed_tickers": failed}


# --- summaries -----------------------------------------------------------------


def _serialize(tx: InsiderTransaction) -> dict:
    return {
        "owner_name": tx.owner_name,
        "owner_role": tx.owner_role,
        "transaction_date": tx.transaction_date,
        "filed_at": tx.filed_at,
        "is_purchase": tx.is_purchase,
        "shares": tx.shares,
        "price": tx.price,
        "value": tx.value,
        "shares_owned_after": tx.shares_owned_after,
        "is_10b5_1": tx.is_10b5_1,
        "filing_url": tx.filing_url,
    }


def summarize_transactions(rows: list, window_days: int = SUMMARY_WINDOW_DAYS, today: Optional[date] = None) -> dict:
    """Pure aggregation over InsiderTransaction-like rows (needs .transaction_date,
    .is_purchase, .value, .owner_name, .is_10b5_1)."""
    today = today or date.today()
    cutoff = today - timedelta(days=window_days)
    cluster_cutoff = today - timedelta(days=CLUSTER_WINDOW_DAYS)

    buys = sells = 0
    buy_value = sell_value = 0.0
    plan_sell_value = 0.0
    buyers: set[str] = set()
    sellers: set[str] = set()
    cluster_buyers: set[str] = set()
    for tx in rows:
        if tx.transaction_date < cutoff:
            continue
        value = tx.value or 0.0
        if tx.is_purchase:
            buys += 1
            buy_value += value
            buyers.add(tx.owner_name)
            if tx.transaction_date >= cluster_cutoff and not tx.is_10b5_1:
                cluster_buyers.add(tx.owner_name)
        else:
            sells += 1
            sell_value += value
            sellers.add(tx.owner_name)
            if tx.is_10b5_1:
                plan_sell_value += value

    discretionary_sell_value = sell_value - plan_sell_value
    return {
        "window_days": window_days,
        "buys": buys,
        "sells": sells,
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "plan_sell_value": round(plan_sell_value, 2),
        "net_value": round(buy_value - sell_value, 2),
        "net_ratio": net_buy_ratio(buy_value, sell_value),
        # Excludes scheduled 10b5-1 sales: routine diversification isn't a view.
        "discretionary_net_ratio": net_buy_ratio(buy_value, discretionary_sell_value),
        "distinct_buyers": len(buyers),
        "distinct_sellers": len(sellers),
        "cluster_buy": len(cluster_buyers) >= CLUSTER_MIN_BUYERS,
        "cluster_buyers": len(cluster_buyers),
    }


async def get_stock_insider_summary(db: AsyncSession, stock_id, latest: int = 8) -> dict:
    since = date.today() - timedelta(days=SUMMARY_WINDOW_DAYS)
    rows = (
        await db.execute(
            select(InsiderTransaction)
            .where(InsiderTransaction.stock_id == stock_id, InsiderTransaction.transaction_date >= since)
            .order_by(InsiderTransaction.transaction_date.desc(), InsiderTransaction.filed_at.desc())
        )
    ).scalars().all()
    summary = summarize_transactions(rows)
    summary["latest"] = [_serialize(tx) for tx in rows[:latest]]
    return summary


async def get_stock_insider_transactions(db: AsyncSession, stock_id, limit: int = 50) -> list[dict]:
    rows = (
        await db.execute(
            select(InsiderTransaction)
            .where(InsiderTransaction.stock_id == stock_id)
            .order_by(InsiderTransaction.transaction_date.desc(), InsiderTransaction.filed_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_serialize(tx) for tx in rows]


async def get_insider_status(db: AsyncSession) -> dict:
    row = (
        await db.execute(
            select(
                func.count(InsiderTransaction.id),
                func.count(func.distinct(InsiderTransaction.stock_id)),
                func.min(InsiderTransaction.filed_at),
                func.max(InsiderTransaction.filed_at),
                func.count(InsiderTransaction.id).filter(InsiderTransaction.is_purchase.is_(True)),
            )
        )
    ).one()
    return {
        "transactions": row[0],
        "stocks": row[1],
        "filed_from": row[2].isoformat() if row[2] else None,
        "filed_to": row[3].isoformat() if row[3] else None,
        "purchases": row[4],
        "sales": row[0] - row[4],
    }


RECENT_WINDOW_DAYS = 30


TEN_PERCENT_ROLE = "10% owner"


def _exclude_institutions_clause():
    """Form 4 covers officers, directors and 10% holders. The last group is usually a
    fund or holding entity rebalancing a position, and its trades are orders of
    magnitude larger, so they crowd out the officer and director activity that
    carries the information. `_owner_role` labels them exactly, and a filer who is
    also an officer or director keeps that richer title instead."""
    return InsiderTransaction.owner_role.is_distinct_from(TEN_PERCENT_ROLE)


async def _recent_trades(
    db: AsyncSession, is_purchase: bool, days: int, limit: int, include_institutions: bool = True
) -> list[dict]:
    """One row per insider decision, not per Form 4 line. A single sale is routinely
    reported as several lines at slightly different prices; listing them separately
    let one insider fill the whole leaderboard. Grouped by (stock, insider, day),
    with a share-weighted average price."""
    since = date.today() - timedelta(days=days)
    value = func.sum(InsiderTransaction.value)
    shares = func.sum(InsiderTransaction.shares)
    rows = (
        await db.execute(
            select(
                Stock.ticker,
                Stock.company_name,
                InsiderTransaction.owner_name,
                func.min(InsiderTransaction.owner_role).label("owner_role"),
                InsiderTransaction.transaction_date,
                func.max(InsiderTransaction.filed_at).label("filed_at"),
                shares.label("shares"),
                value.label("value"),
                func.bool_or(InsiderTransaction.is_10b5_1).label("is_10b5_1"),
                func.min(InsiderTransaction.filing_url).label("filing_url"),
                func.count().label("lines"),
            )
            .join(Stock, Stock.id == InsiderTransaction.stock_id)
            .where(
                InsiderTransaction.transaction_date >= since,
                InsiderTransaction.is_purchase.is_(is_purchase),
                InsiderTransaction.value.isnot(None),
                *([] if include_institutions else [_exclude_institutions_clause()]),
            )
            .group_by(
                Stock.ticker, Stock.company_name,
                InsiderTransaction.owner_name, InsiderTransaction.transaction_date,
            )
            .order_by(value.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "ticker": r.ticker,
            "company_name": r.company_name,
            "owner_name": r.owner_name,
            "owner_role": r.owner_role,
            "transaction_date": r.transaction_date,
            "filed_at": r.filed_at,
            "is_purchase": is_purchase,
            "shares": r.shares,
            "price": round(r.value / r.shares, 4) if r.shares else None,
            "value": round(r.value, 2),
            "is_10b5_1": r.is_10b5_1,
            "filing_url": r.filing_url,
            "lines": r.lines,
        }
        for r in rows
    ]


async def get_recent_notable_trades(
    db: AsyncSession, days: int = RECENT_WINDOW_DAYS, limit: int = 10, include_institutions: bool = True
) -> dict:
    """The largest open-market insider buys and sells of the last `days`, ranked
    separately. Buys and sells are not comparable in size -- routine selling at a
    mega-cap dwarfs almost any purchase -- so one combined list by dollar value
    would be all sells and would hide the rarer, more informative buying."""
    buys = await _recent_trades(db, True, days, limit, include_institutions)
    sells = await _recent_trades(db, False, days, limit, include_institutions)
    return {
        "window_days": days,
        "include_institutions": include_institutions,
        "buys": buys,
        "sells": sells,
    }


async def get_insider_overview(
    db: AsyncSession, days: int = RECENT_WINDOW_DAYS, include_institutions: bool = True
) -> dict:
    """Market-wide totals for the window, plus the stocks where several insiders
    bought independently -- the pattern with the strongest forward record."""
    since = date.today() - timedelta(days=days)
    where = [InsiderTransaction.transaction_date >= since, InsiderTransaction.value.isnot(None)]
    if not include_institutions:
        where.append(_exclude_institutions_clause())

    totals = (
        await db.execute(
            select(
                func.count().filter(InsiderTransaction.is_purchase.is_(True)).label("buys"),
                func.count().filter(InsiderTransaction.is_purchase.is_(False)).label("sells"),
                func.coalesce(func.sum(InsiderTransaction.value).filter(InsiderTransaction.is_purchase.is_(True)), 0.0).label("buy_value"),
                func.coalesce(func.sum(InsiderTransaction.value).filter(InsiderTransaction.is_purchase.is_(False)), 0.0).label("sell_value"),
                func.count(func.distinct(InsiderTransaction.stock_id)).label("stocks"),
                func.count(func.distinct(InsiderTransaction.owner_name)).label("insiders"),
            ).where(*where)
        )
    ).one()

    # Cluster buying: several insiders at one company buying unscheduled in the window.
    buyers = func.count(func.distinct(InsiderTransaction.owner_name))
    cluster_rows = (
        await db.execute(
            select(
                Stock.ticker,
                Stock.company_name,
                buyers.label("buyers"),
                func.sum(InsiderTransaction.value).label("value"),
                func.max(InsiderTransaction.transaction_date).label("latest"),
            )
            .join(Stock, Stock.id == InsiderTransaction.stock_id)
            .where(
                *where,
                InsiderTransaction.is_purchase.is_(True),
                InsiderTransaction.is_10b5_1.is_(False),
            )
            .group_by(Stock.ticker, Stock.company_name)
            .having(buyers >= CLUSTER_MIN_BUYERS)
            .order_by(buyers.desc(), func.sum(InsiderTransaction.value).desc())
            .limit(20)
        )
    ).all()

    return {
        "window_days": days,
        "include_institutions": include_institutions,
        "buys": totals.buys,
        "sells": totals.sells,
        "buy_value": round(totals.buy_value or 0.0, 2),
        "sell_value": round(totals.sell_value or 0.0, 2),
        "net_ratio": net_buy_ratio(totals.buy_value or 0.0, totals.sell_value or 0.0),
        "stocks": totals.stocks,
        "insiders": totals.insiders,
        "cluster_buys": [
            {
                "ticker": r.ticker,
                "company_name": r.company_name,
                "buyers": r.buyers,
                "value": round(r.value or 0.0, 2),
                "latest": r.latest,
            }
            for r in cluster_rows
        ],
    }
