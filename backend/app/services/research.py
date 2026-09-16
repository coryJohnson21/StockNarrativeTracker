"""Turn narrative signals into testable claims: point-in-time momentum snapshots,
daily prices, forward returns, and a backtest that asks whether the score (or any
of its components) actually ranks future returns."""
import asyncio
import bisect
import logging
import math
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Stock, StockMention, StockMomentum, StockPrice, MomentumSnapshot
from app.services import market_data
from app.services.momentum import (
    MentionStats, _Universe, SELF_MENTION_WEIGHT, sentiment_to_label,
    RECENT_WINDOW_DAYS, PRIOR_WINDOW_DAYS,
)

logger = logging.getLogger(__name__)

BENCHMARK_TICKER = "SPY"
HORIZONS = (5, 20, 60)
_UPSERT_CHUNK = 1000
_MAX_ENTRY_LAG_DAYS = 5


# --- point-in-time mention statistics --------------------------------------


class MentionSeries:
    """One stock's mentions in time order with prefix sums, so the stats as of any
    day (only mentions published on or before it) come out in O(log n)."""

    def __init__(self, mentions):
        rows = sorted(mentions, key=lambda m: m[0])
        self.ts = [m[0] for m in rows]
        n = len(rows)
        self.cum_w = [0.0] * (n + 1)
        self.cum_ws = [0.0] * (n + 1)
        self.cum_s = [0.0] * (n + 1)
        self.cum_src = [0] * (n + 1)
        seen = set()
        for i, (_, sentiment, is_self, source_id) in enumerate(rows):
            w = SELF_MENTION_WEIGHT if is_self else 1.0
            s = float(sentiment or 0.0)
            self.cum_w[i + 1] = self.cum_w[i] + w
            self.cum_ws[i + 1] = self.cum_ws[i] + s * w
            self.cum_s[i + 1] = self.cum_s[i] + s
            seen.add(source_id)
            self.cum_src[i + 1] = len(seen)

    def stats_as_of(self, day: date) -> MentionStats:
        end = datetime.combine(day, time.max)
        i_end = bisect.bisect_right(self.ts, end)
        i_7 = min(bisect.bisect_left(self.ts, end - timedelta(days=RECENT_WINDOW_DAYS)), i_end)
        i_30 = min(bisect.bisect_left(self.ts, end - timedelta(days=RECENT_WINDOW_DAYS + PRIOR_WINDOW_DAYS)), i_end)
        total = i_end
        return MentionStats(
            total=total,
            recent_7d=i_end - i_7,
            recent_30d=i_end - i_30,
            prior_23d=i_7 - i_30,
            avg_sentiment=(self.cum_s[i_end] / total) if total else 0.0,
            unique_sources=self.cum_src[i_end],
            w_total=self.cum_w[i_end],
            w_recent_7d=self.cum_w[i_end] - self.cum_w[i_7],
            w_recent_30d=self.cum_w[i_end] - self.cum_w[i_30],
            w_prior_23d=self.cum_w[i_7] - self.cum_w[i_30],
            w_sentiment_sum=self.cum_ws[i_end],
        )


async def rebuild_momentum_snapshots(
    db: AsyncSession, since: Optional[date] = None, until: Optional[date] = None
) -> dict:
    """Recompute the score for every stock on every day from the first mention to
    `until` (default today). Idempotent: existing rows for a (stock, day) are updated."""
    rows = (
        await db.execute(
            select(
                StockMention.stock_id, StockMention.mentioned_at, StockMention.sentiment_score,
                StockMention.is_self_mention, StockMention.source_id,
            ).where(StockMention.mentioned_at.isnot(None))
        )
    ).all()
    if not rows:
        return {"days": 0, "rows": 0}

    by_stock: dict = defaultdict(list)
    for r in rows:
        by_stock[r.stock_id].append((r.mentioned_at, r.sentiment_score, r.is_self_mention, r.source_id))
    series = {sid: MentionSeries(ms) for sid, ms in by_stock.items()}

    first_day = min(r.mentioned_at for r in rows).date()
    until = until or date.today()
    day = max(since, first_day) if since else first_day

    written = 0
    days = 0
    pending: list[dict] = []
    while day <= until:
        stats = {sid: s.stats_as_of(day) for sid, s in series.items()}
        stats = {sid: st for sid, st in stats.items() if st.total > 0}
        if stats:
            universe = _Universe(list(stats.values()))
            for sid, st in stats.items():
                pending.append(
                    {
                        "id": uuid.uuid4(),
                        "stock_id": sid,
                        "date": day,
                        "score": universe.score(st),
                        "mention_count_7d": st.recent_7d,
                        "mention_count_30d": st.recent_30d,
                        "avg_sentiment": round(st.avg_sentiment, 1),
                        "unique_sources": st.unique_sources,
                        "share_of_voice": round(universe.share(st), 5),
                        "label": sentiment_to_label(st.avg_sentiment),
                    }
                )
            days += 1
        if len(pending) >= _UPSERT_CHUNK:
            written += await _upsert_snapshots(db, pending)
            pending = []
        day += timedelta(days=1)

    if pending:
        written += await _upsert_snapshots(db, pending)
    await db.commit()
    return {"days": days, "rows": written}


async def _upsert_snapshots(db: AsyncSession, values: list[dict]) -> int:
    update_cols = ("score", "mention_count_7d", "mention_count_30d", "avg_sentiment", "unique_sources", "share_of_voice", "label")
    for i in range(0, len(values), _UPSERT_CHUNK):
        chunk = values[i:i + _UPSERT_CHUNK]
        stmt = pg_insert(MomentumSnapshot).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_momentum_snapshots_stock_date",
            set_={c: getattr(stmt.excluded, c) for c in update_cols},
        )
        await db.execute(stmt)
    return len(values)


# --- prices ------------------------------------------------------------------


class PriceSeries:
    def __init__(self, points):
        pts = sorted(points, key=lambda p: p[0])
        self.dates = [p[0] for p in pts]
        self.closes = [float(p[1]) for p in pts]

    def __len__(self) -> int:
        return len(self.dates)

    def trailing_return(self, trading_days: int) -> Optional[float]:
        """Return over the last `trading_days` closes, None if the series is too short."""
        if len(self.closes) <= trading_days or self.closes[-1 - trading_days] <= 0:
            return None
        return self.closes[-1] / self.closes[-1 - trading_days] - 1.0

    def forward_return(self, start: date, horizon_trading_days: int) -> Optional[float]:
        """Return from the first close on/after `start` to the close `horizon` trading
        days later. None if there's no close within a few days of `start` (a gap in
        the data) or the exit is past the end of the series (not yet realized)."""
        i = bisect.bisect_left(self.dates, start)
        if i >= len(self.dates) or (self.dates[i] - start).days > _MAX_ENTRY_LAG_DAYS:
            return None
        j = i + horizon_trading_days
        if j >= len(self.dates) or self.closes[i] <= 0:
            return None
        return self.closes[j] / self.closes[i] - 1.0


async def _ensure_benchmark(db: AsyncSession) -> Stock:
    stock = (await db.execute(select(Stock).where(Stock.ticker == BENCHMARK_TICKER))).scalar_one_or_none()
    if stock is None:
        stock = Stock(ticker=BENCHMARK_TICKER, company_name="SPDR S&P 500 ETF", is_public=True)
        db.add(stock)
        await db.flush()
    return stock


async def upsert_prices(db: AsyncSession, stock_id, points: list[dict]) -> int:
    values = [
        {"id": uuid.uuid4(), "stock_id": stock_id, "date": date.fromisoformat(p["date"]), "close": float(p["close"])}
        for p in points
        if p.get("close") is not None
    ]
    for i in range(0, len(values), _UPSERT_CHUNK):
        chunk = values[i:i + _UPSERT_CHUNK]
        stmt = pg_insert(StockPrice).values(chunk)
        stmt = stmt.on_conflict_do_update(constraint="uq_stock_prices_stock_date", set_={"close": stmt.excluded.close})
        await db.execute(stmt)
    return len(values)


async def refresh_price_history(db: AsyncSession, full: bool = False) -> dict:
    """Pull daily closes from Yahoo for the benchmark and every public stock with a
    momentum record. A stock with no prices yet gets a year of history; the rest get
    a short top-up unless `full` is set."""
    benchmark = await _ensure_benchmark(db)
    stocks = (
        await db.execute(
            select(Stock)
            .join(StockMomentum, Stock.id == StockMomentum.stock_id)
            .where(Stock.is_public.isnot(False))
        )
    ).scalars().all()
    targets = {s.id: s for s in stocks}
    targets[benchmark.id] = benchmark

    have = set(
        sid for (sid,) in (await db.execute(select(StockPrice.stock_id).group_by(StockPrice.stock_id))).all()
    )

    fetched = 0
    rows = 0
    failed: list[str] = []
    for stock in targets.values():
        range_ = "1y" if (full or stock.id not in have) else "3mo"
        try:
            points = await market_data.fetch_price_history(stock.ticker, range_=range_)
        except Exception:
            logger.exception("Price history fetch failed for %s", stock.ticker)
            points = []
        if not points:
            failed.append(stock.ticker)
        else:
            rows += await upsert_prices(db, stock.id, points)
            fetched += 1
        await asyncio.sleep(0.25)

    await db.commit()
    return {"stocks_fetched": fetched, "rows": rows, "failed": failed}


async def load_price_series(db: AsyncSession, stock_ids: list) -> dict:
    if not stock_ids:
        return {}
    rows = (
        await db.execute(
            select(StockPrice.stock_id, StockPrice.date, StockPrice.close).where(StockPrice.stock_id.in_(stock_ids))
        )
    ).all()
    grouped: dict = defaultdict(list)
    for sid, d, c in rows:
        grouped[sid].append((d, c))
    return {sid: PriceSeries(pts) for sid, pts in grouped.items()}


# --- backtest statistics (pure) ---------------------------------------------


def average_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    """Rank correlation — the information coefficient. None when there's nothing to rank."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    rx, ry = average_ranks(xs), average_ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


@dataclass
class Observation:
    stock_id: object
    date: date
    score: float
    avg_sentiment: float
    mention_count_7d: int
    share_of_voice: float
    ret: float
    excess: Optional[float]


def _pct(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x * 100, 2)


def bucketize(obs: list[Observation], buckets: int) -> list[dict]:
    """Split observations into `buckets` equal-count groups by score (1 = lowest)."""
    if not obs:
        return []
    ordered = sorted(obs, key=lambda o: o.score)
    n = len(ordered)
    buckets = max(1, min(buckets, n))
    out = []
    for b in range(buckets):
        lo, hi = (b * n) // buckets, ((b + 1) * n) // buckets
        group = ordered[lo:hi]
        if not group:
            continue
        rets = [o.ret for o in group]
        excess = [o.excess for o in group if o.excess is not None]
        out.append(
            {
                "bucket": b + 1,
                "n": len(group),
                "score_min": round(group[0].score, 1),
                "score_max": round(group[-1].score, 1),
                "mean_return_pct": _pct(statistics.fmean(rets)),
                "mean_excess_pct": _pct(statistics.fmean(excess)) if excess else None,
                "median_excess_pct": _pct(statistics.median(excess)) if excess else None,
                "hit_rate": round(sum(1 for e in excess if e > 0) / len(excess), 3) if excess else None,
            }
        )
    return out


def factor_ic(obs: list[Observation], getter, min_per_date: int = 5) -> dict:
    """Overall rank IC of a factor against excess (or raw) return, plus the mean of
    per-date cross-sectional ICs and its t-stat, which is the honest significance test:
    one lucky week shouldn't count as evidence."""
    target = [o.excess if o.excess is not None else o.ret for o in obs]
    values = [getter(o) for o in obs]
    overall = spearman(values, target)

    by_date: dict = defaultdict(list)
    for o, v, t in zip(obs, values, target):
        by_date[o.date].append((v, t))
    daily = []
    for pairs in by_date.values():
        if len(pairs) >= min_per_date:
            ic = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            if ic is not None:
                daily.append(ic)

    mean_daily = statistics.fmean(daily) if daily else None
    t_stat = None
    if len(daily) >= 3:
        sd = statistics.stdev(daily)
        t_stat = round(mean_daily / (sd / math.sqrt(len(daily))), 2) if sd > 0 else None

    return {
        "ic": round(overall, 3) if overall is not None else None,
        "n": len(obs),
        "mean_daily_ic": round(mean_daily, 3) if mean_daily is not None else None,
        "t_stat": t_stat,
        "n_dates": len(daily),
    }


FACTORS = {
    "score": lambda o: o.score,
    "avg_sentiment": lambda o: o.avg_sentiment,
    "mention_count_7d": lambda o: float(o.mention_count_7d),
    "share_of_voice": lambda o: o.share_of_voice,
}


def summarize_backtest(obs: list[Observation], horizon: int, buckets: int, min_mentions_7d: int, benchmark_available: bool) -> dict:
    bucket_rows = bucketize(obs, buckets)
    spread = None
    if len(bucket_rows) >= 2 and bucket_rows[-1]["mean_excess_pct"] is not None and bucket_rows[0]["mean_excess_pct"] is not None:
        spread = round(bucket_rows[-1]["mean_excess_pct"] - bucket_rows[0]["mean_excess_pct"], 2)
    dates = sorted({o.date for o in obs})
    return {
        "horizon": horizon,
        "min_mentions_7d": min_mentions_7d,
        "n_observations": len(obs),
        "n_dates": len(dates),
        "date_from": dates[0].isoformat() if dates else None,
        "date_to": dates[-1].isoformat() if dates else None,
        "benchmark": BENCHMARK_TICKER,
        "benchmark_available": benchmark_available,
        "buckets": bucket_rows,
        "spread_excess_pct": spread,
        "factor_ic": [{"factor": name, **factor_ic(obs, getter)} for name, getter in FACTORS.items()],
    }


# --- orchestration -----------------------------------------------------------


async def run_backtest(db: AsyncSession, horizon: int = 20, buckets: int = 5, min_mentions_7d: int = 1) -> dict:
    snaps = (
        await db.execute(select(MomentumSnapshot).where(MomentumSnapshot.mention_count_7d >= min_mentions_7d))
    ).scalars().all()
    benchmark = (await db.execute(select(Stock).where(Stock.ticker == BENCHMARK_TICKER))).scalar_one_or_none()

    stock_ids = list({s.stock_id for s in snaps})
    if benchmark is not None:
        stock_ids.append(benchmark.id)
    prices = await load_price_series(db, stock_ids)
    bench = prices.get(benchmark.id) if benchmark is not None else None

    obs: list[Observation] = []
    for s in snaps:
        ps = prices.get(s.stock_id)
        if ps is None or s.stock_id == (benchmark.id if benchmark else None):
            continue
        r = ps.forward_return(s.date, horizon)
        if r is None:
            continue
        b = bench.forward_return(s.date, horizon) if bench is not None else None
        obs.append(
            Observation(
                stock_id=s.stock_id, date=s.date, score=s.score, avg_sentiment=s.avg_sentiment,
                mention_count_7d=s.mention_count_7d, share_of_voice=s.share_of_voice,
                ret=r, excess=(r - b) if b is not None else None,
            )
        )
    return summarize_backtest(obs, horizon, buckets, min_mentions_7d, benchmark_available=bench is not None and len(bench) > 0)


async def refresh_research(db: AsyncSession, full_prices: bool = False) -> dict:
    from app.services.reliability import compute_source_reliability

    prices = await refresh_price_history(db, full=full_prices)
    snapshots = await rebuild_momentum_snapshots(db)
    reliability = await compute_source_reliability(db)
    return {"prices": prices, "snapshots": snapshots, "reliability_channels": len(reliability)}


async def get_research_status(db: AsyncSession) -> dict:
    snap = (
        await db.execute(select(func.count(MomentumSnapshot.id), func.min(MomentumSnapshot.date), func.max(MomentumSnapshot.date)))
    ).one()
    px = (
        await db.execute(
            select(func.count(StockPrice.id), func.count(func.distinct(StockPrice.stock_id)), func.min(StockPrice.date), func.max(StockPrice.date))
        )
    ).one()
    bench = (
        await db.execute(
            select(func.count(StockPrice.id)).join(Stock, Stock.id == StockPrice.stock_id).where(Stock.ticker == BENCHMARK_TICKER)
        )
    ).scalar()
    return {
        "snapshots": snap[0],
        "snapshot_from": snap[1].isoformat() if snap[1] else None,
        "snapshot_to": snap[2].isoformat() if snap[2] else None,
        "price_rows": px[0],
        "price_stocks": px[1],
        "price_from": px[2].isoformat() if px[2] else None,
        "price_to": px[3].isoformat() if px[3] else None,
        "benchmark_available": bool(bench),
        "horizons": list(HORIZONS),
    }
