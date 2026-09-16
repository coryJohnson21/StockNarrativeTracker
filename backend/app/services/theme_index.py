"""Make a theme investable enough to check: an equal-weight return index of the
stocks most often discussed alongside it, lined up week by week against how much
and how positively the theme itself was being talked about. Then ask whether the
narrative led the basket, moved with it, or trailed it."""
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Stock, Theme, ThemeMention
from app.services.momentum import get_top_stocks_for_theme
from app.services.research import PriceSeries, load_price_series, spearman

DEFAULT_WINDOW_DAYS = 90
MAX_CONSTITUENTS = 8
MIN_WEEKS_FOR_LEAD_LAG = 6


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_equal_weight_index(series: dict[str, PriceSeries], start: date) -> list[dict]:
    """Daily-rebalanced equal-weight index, base 100 on the first trading day on or
    after `start`. Each day's move is the mean daily return of every constituent
    with closes on both that day and the previous trading day, so a stock with a
    gap or a late listing simply sits out that day instead of breaking the series."""
    closes_by_date: dict[date, dict[str, float]] = defaultdict(dict)
    lead_in = start - timedelta(days=10)
    for ticker, ps in series.items():
        for d, c in zip(ps.dates, ps.closes):
            if d >= lead_in and c > 0:
                closes_by_date[d][ticker] = c

    out: list[dict] = []
    value = 100.0
    prev: Optional[date] = None
    for d in sorted(closes_by_date):
        if prev is not None and out:
            today, yesterday = closes_by_date[d], closes_by_date[prev]
            rets = [today[t] / yesterday[t] - 1 for t in today if t in yesterday]
            if rets:
                value *= 1 + statistics.fmean(rets)
        if d >= start:
            out.append({"date": d.isoformat(), "value": round(value, 2), "constituents": len(closes_by_date[d])})
        prev = d
    return out


def weekly_buckets(index: list[dict], narrative_daily: list[dict]) -> list[dict]:
    """Join the index and the theme's daily mention stats into Monday-anchored weeks:
    the index's return over the week, total mentions, and mention-weighted sentiment."""
    week_close: dict[date, float] = {}
    for p in index:
        d = date.fromisoformat(p["date"])
        week_close[_week_start(d)] = p["value"]  # last value in the week wins (sorted input)

    mentions: dict[date, int] = defaultdict(int)
    sentiment_sum: dict[date, float] = defaultdict(float)
    for n in narrative_daily:
        w = _week_start(date.fromisoformat(n["date"]))
        mentions[w] += n["mention_count"]
        sentiment_sum[w] += n["avg_sentiment"] * n["mention_count"]

    weeks = sorted(set(week_close) | set(mentions))
    out = []
    prev_close: Optional[float] = None
    for w in weeks:
        close = week_close.get(w)
        ret = (close / prev_close - 1) if (close is not None and prev_close) else None
        n = mentions.get(w, 0)
        out.append(
            {
                "week": w.isoformat(),
                "index_value": close,
                "index_return_pct": round(ret * 100, 2) if ret is not None else None,
                "mention_count": n,
                "avg_sentiment": round(sentiment_sum[w] / n, 1) if n else None,
            }
        )
        if close is not None:
            prev_close = close
    return out


def _shifted_ic(weeks: list[dict], factor: str, shift: int) -> tuple[Optional[float], int]:
    """Rank correlation between factor in week w and index return in week w+shift."""
    xs, ys = [], []
    for i, wk in enumerate(weeks):
        j = i + shift
        if j < 0 or j >= len(weeks):
            continue
        x, y = wk.get(factor), weeks[j].get("index_return_pct")
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))
    if len(xs) < MIN_WEEKS_FOR_LEAD_LAG:
        return None, len(xs)
    ic = spearman(xs, ys)
    return (round(ic, 3) if ic is not None else None), len(xs)


def lead_lag(weeks: list[dict]) -> dict:
    """For sentiment and for mention volume: does this week's narrative correlate
    with next week's basket return (narrative leads), this week's (coincident), or
    last week's (narrative lags / chases price)?"""
    result = {}
    for factor in ("avg_sentiment", "mention_count"):
        leads, n_leads = _shifted_ic(weeks, factor, +1)
        coincident, n_co = _shifted_ic(weeks, factor, 0)
        lags, n_lags = _shifted_ic(weeks, factor, -1)
        verdict = None
        candidates = {k: v for k, v in (("leads", leads), ("coincident", coincident), ("lags", lags)) if v is not None}
        if candidates:
            best = max(candidates, key=lambda k: abs(candidates[k]))
            verdict = best if abs(candidates[best]) >= 0.3 else "none"
        result[factor] = {"leads": leads, "coincident": coincident, "lags": lags, "n_weeks": max(n_leads, n_co, n_lags), "verdict": verdict}
    return result


async def _theme_daily_narrative(db: AsyncSession, theme_id, since: datetime) -> list[dict]:
    bucket = func.date_trunc("day", ThemeMention.mentioned_at)
    rows = (
        await db.execute(
            select(bucket.label("day"), func.count(ThemeMention.id), func.avg(ThemeMention.sentiment_score))
            .where(ThemeMention.theme_id == theme_id, ThemeMention.mentioned_at >= since)
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()
    return [
        {"date": day.date().isoformat(), "mention_count": n, "avg_sentiment": round(float(avg or 0.0), 1)}
        for day, n, avg in rows
    ]


async def get_theme_index(db: AsyncSession, theme: Theme, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    start = date.today() - timedelta(days=days)
    top = await get_top_stocks_for_theme(db, theme.id, limit=MAX_CONSTITUENTS)
    tickers = [t["ticker"] for t in top]

    stocks = (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))).scalars().all() if tickers else []
    prices = await load_price_series(db, [s.id for s in stocks])
    series = {s.ticker: prices[s.id] for s in stocks if s.id in prices and len(prices[s.id]) >= 2}

    index = build_equal_weight_index(series, start)
    narrative = await _theme_daily_narrative(db, theme.id, datetime.combine(start, datetime.min.time()) - timedelta(days=7))
    weeks = weekly_buckets(index, narrative)

    return {
        "theme": theme.name,
        "window_days": days,
        "constituents": [{**t, "has_prices": t["ticker"] in series} for t in top],
        "index": index,
        "weekly": weeks,
        "lead_lag": lead_lag(weeks),
        "index_return_pct": round((index[-1]["value"] / index[0]["value"] - 1) * 100, 2) if len(index) >= 2 else None,
    }
