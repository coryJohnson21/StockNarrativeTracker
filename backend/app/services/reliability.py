"""Who is actually right? Score each channel's explicit calls against what the
stock then did relative to SPY, and turn that into a weight on its mentions.

The weight is used in *live* momentum scoring only. Point-in-time snapshots must
not use it: a channel's track record is computed from outcomes that happen after
each snapshot day, so folding it in would be look-ahead bias."""
import math
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Source, SourceReliability, Stock, StockCall
from app.services.momentum import FILING_SOURCE_TYPES
from app.services.research import BENCHMARK_TICKER, load_price_series

# Which way each call type bets. Hold and watch take no side, so they can't be
# right or wrong and aren't scored.
DIRECTIONAL = {"buy": 1, "sell": -1, "avoid": -1}

# Beta prior centred on a coin flip. Ten pseudo-calls means a channel needs a real
# sample before its weight drifts far from neutral -- 3 for 3 is encouraging, not proof.
PRIOR_STRENGTH = 10.0
DEFAULT_HORIZON = 20


def channel_key(source_type: str, channel: Optional[str]) -> str:
    """Group by named channel (podcast, YouTube channel, subreddit) when we have one,
    else by source type so anonymous uploads still get a collective record."""
    name = (channel or "").strip()
    return name if name else source_type


def call_alpha(call: str, excess_return: float) -> Optional[float]:
    """Excess return in the direction the call bet on; positive means the call was right."""
    direction = DIRECTIONAL.get(call)
    return None if direction is None else direction * excess_return


def score_call_outcome(
    call: str,
    ret: Optional[float],
    bench_ret: Optional[float],
    since: Optional[tuple[float, date, int]] = None,
) -> dict:
    """Turn one call's realized return into the outcome fields a UI shows, as percents.

    Everything is None when the call can't be judged -- no price yet, or a hold/watch
    that took no side -- so "not yet" and "wrong" stay distinguishable. Excess falls
    back to the raw return when no benchmark is loaded, matching compute_source_reliability.

    `since` is the open-ended (return, as-of date, trading days elapsed) from
    PriceSeries.return_since. It is reported but never scored: it has no fixed exit,
    so folding it into hit rate or alpha would make a channel's record drift with
    every new close. The scored verdict stays the fixed-horizon one.

    "alpha" is the unrounded fraction, for callers averaging across calls; the caller
    drops it from what it serves. Averaging the rounded percents instead would drift
    from the mean_alpha_pct compute_source_reliability stores for the same calls.
    """
    excess = (ret - bench_ret) if (ret is not None and bench_ret is not None) else ret
    alpha = call_alpha(call, excess) if excess is not None else None
    as_pct = lambda v: round(v * 100, 2) if v is not None else None
    since_ret, since_date, since_days = since if since is not None else (None, None, None)
    return {
        "alpha": alpha,
        "directional": call in DIRECTIONAL,
        "return_pct": as_pct(ret),
        "benchmark_return_pct": as_pct(bench_ret),
        "excess_return_pct": as_pct(excess),
        "alpha_pct": as_pct(alpha),
        "correct": None if alpha is None else alpha > 0,
        "return_since_pct": as_pct(since_ret),
        "since_as_of": since_date,
        "since_trading_days": since_days,
    }


def posterior_hit_rate(hits: int, scored: int, prior_strength: float = PRIOR_STRENGTH) -> float:
    return (hits + prior_strength / 2) / (scored + prior_strength)


def wilson_lower(hits: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the 95% Wilson interval for the hit rate -- what we can be fairly
    sure the channel's accuracy is at least."""
    if n == 0:
        return 0.0
    p = hits / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def reliability_weight(hits: int, scored: int) -> float:
    """0.5 + shrunk hit rate: exactly 1.0 with no evidence, ~1.2 for a channel that is
    right 70% of the time over a real sample, ~0.8 for one that is wrong that often."""
    return round(0.5 + posterior_hit_rate(hits, scored), 3)


async def compute_source_reliability(db: AsyncSession, horizon: int = DEFAULT_HORIZON) -> list[dict]:
    rows = (
        await db.execute(
            select(StockCall, Source.type, Source.channel)
            .join(Source, StockCall.source_id == Source.id)
            .where(Source.type.notin_(FILING_SOURCE_TYPES))
        )
    ).all()
    benchmark = (await db.execute(select(Stock).where(Stock.ticker == BENCHMARK_TICKER))).scalar_one_or_none()

    stock_ids = list({call.stock_id for call, _, _ in rows})
    if benchmark is not None:
        stock_ids.append(benchmark.id)
    prices = await load_price_series(db, stock_ids)
    bench = prices.get(benchmark.id) if benchmark is not None else None

    n_calls: Counter = Counter()
    scored: Counter = Counter()
    hits: Counter = Counter()
    alphas: dict[str, list[float]] = defaultdict(list)
    types: dict[str, Counter] = defaultdict(Counter)

    for call, source_type, channel in rows:
        key = channel_key(source_type, channel)
        n_calls[key] += 1
        types[key][source_type] += 1
        series = prices.get(call.stock_id)
        if series is None:
            continue
        day = call.called_at.date()
        ret = series.forward_return(day, horizon)
        if ret is None:
            continue
        bench_ret = bench.forward_return(day, horizon) if bench is not None else None
        excess = ret - bench_ret if bench_ret is not None else ret
        alpha = call_alpha(call.call, excess)
        if alpha is None:
            continue
        scored[key] += 1
        if alpha > 0:
            hits[key] += 1
        alphas[key].append(alpha)

    now = datetime.utcnow()
    results = []
    for key in n_calls:
        n, h = scored[key], hits[key]
        results.append(
            {
                "channel_key": key,
                "source_type": types[key].most_common(1)[0][0],
                "horizon": horizon,
                "n_calls": n_calls[key],
                "n_scored": n,
                "hits": h,
                "hit_rate": round(h / n, 3) if n else None,
                "wilson_lower": round(wilson_lower(h, n), 3) if n else None,
                "mean_alpha_pct": round(statistics.fmean(alphas[key]) * 100, 2) if alphas[key] else None,
                "weight": reliability_weight(h, n),
                "computed_at": now,
            }
        )
    results.sort(key=lambda r: (-r["weight"], -r["n_scored"], r["channel_key"]))

    await _persist(db, results)
    return results


async def _persist(db: AsyncSession, results: list[dict]) -> None:
    # Every source starts neutral; channels with a record then override. Channels
    # that no longer have any calls (e.g. after a cleanup) drop out of the table.
    await db.execute(update(Source).values(reliability_weight=1.0))
    keep = [r["channel_key"] for r in results]
    await db.execute(delete(SourceReliability).where(SourceReliability.channel_key.notin_(keep)) if keep else delete(SourceReliability))
    if results:
        stmt = pg_insert(SourceReliability).values([{"id": uuid.uuid4(), **r} for r in results])
        cols = [c for c in results[0] if c != "channel_key"]
        stmt = stmt.on_conflict_do_update(index_elements=["channel_key"], set_={c: getattr(stmt.excluded, c) for c in cols})
        await db.execute(stmt)
        key_expr = func.coalesce(func.nullif(func.trim(Source.channel), ""), Source.type)
        for r in results:
            if r["weight"] != 1.0:
                await db.execute(update(Source).where(key_expr == r["channel_key"]).values(reliability_weight=r["weight"]))
    await db.commit()


async def get_source_reliability(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(SourceReliability).order_by(SourceReliability.weight.desc(), SourceReliability.n_scored.desc())
        )
    ).scalars().all()
    return [
        {
            "channel_key": r.channel_key,
            "source_type": r.source_type,
            "horizon": r.horizon,
            "n_calls": r.n_calls,
            "n_scored": r.n_scored,
            "hits": r.hits,
            "hit_rate": r.hit_rate,
            "wilson_lower": r.wilson_lower,
            "mean_alpha_pct": r.mean_alpha_pct,
            "weight": r.weight,
            "computed_at": r.computed_at,
        }
        for r in rows
    ]


async def channel_track_record(db: AsyncSession, channel: str, horizon: int = DEFAULT_HORIZON) -> dict:
    """One channel's record with the individual calls behind it, newest first.

    The aggregate here is computed from the same calls the list shows, so a landing
    page can show the number and the evidence for it without them disagreeing. Calls
    too recent to have a realized `horizon`-day return are returned with a null
    outcome rather than dropped -- "made but not yet judged" is worth seeing."""
    # Same grouping as channel_key(), expressed in SQL so one channel's calls can be
    # fetched without loading every call in the database.
    key_expr = func.coalesce(func.nullif(func.trim(Source.channel), ""), Source.type)
    rows = (
        await db.execute(
            select(StockCall, Stock.ticker, Source.type, Source.title, Source.url)
            .join(Source, StockCall.source_id == Source.id)
            .join(Stock, StockCall.stock_id == Stock.id)
            .where(Source.type.notin_(FILING_SOURCE_TYPES), key_expr == channel)
            .order_by(StockCall.called_at.desc())
        )
    ).all()

    benchmark = (await db.execute(select(Stock).where(Stock.ticker == BENCHMARK_TICKER))).scalar_one_or_none()
    stock_ids = list({call.stock_id for call, *_ in rows})
    if benchmark is not None:
        stock_ids.append(benchmark.id)
    prices = await load_price_series(db, stock_ids)
    bench = prices.get(benchmark.id) if benchmark is not None else None

    calls: list[dict] = []
    alphas: list[float] = []
    hits = 0
    types: Counter = Counter()

    for call, ticker, source_type, title, url in rows:
        types[source_type] += 1
        series = prices.get(call.stock_id)
        day = call.called_at.date()
        outcome = score_call_outcome(
            call.call,
            series.forward_return(day, horizon) if series is not None else None,
            bench.forward_return(day, horizon) if bench is not None else None,
            since=series.return_since(day) if series is not None else None,
        )
        alpha = outcome.pop("alpha")
        if alpha is not None:
            alphas.append(alpha)
            if outcome["correct"]:
                hits += 1
        calls.append(
            {
                "ticker": ticker,
                "call": call.call,
                "price_target": call.price_target,
                "reasoning": call.reasoning,
                "called_at": call.called_at,
                "source_id": call.source_id,
                "source_title": title,
                "source_url": url,
                **outcome,
            }
        )

    scored = len(alphas)
    return {
        "channel_key": channel,
        "source_type": types.most_common(1)[0][0] if types else None,
        "horizon": horizon,
        "benchmark": BENCHMARK_TICKER if bench is not None else None,
        "n_calls": len(calls),
        "n_scored": scored,
        "hits": hits,
        "hit_rate": round(hits / scored, 3) if scored else None,
        "wilson_lower": round(wilson_lower(hits, scored), 3) if scored else None,
        "mean_alpha_pct": round(statistics.fmean(alphas) * 100, 2) if alphas else None,
        "weight": reliability_weight(hits, scored),
        "calls": calls,
    }
