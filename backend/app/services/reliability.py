"""Who is actually right? Score each channel's explicit calls against what the
stock then did relative to SPY, and turn that into a weight on its mentions.

The weight is used in *live* momentum scoring only. Point-in-time snapshots must
not use it: a channel's track record is computed from outcomes that happen after
each snapshot day, so folding it in would be look-ahead bias."""
import math
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Source, SourceReliability, Stock, StockCall
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
            select(StockCall, Source.type, Source.channel).join(Source, StockCall.source_id == Source.id)
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
    # Every source starts neutral; channels with a record then override.
    await db.execute(update(Source).values(reliability_weight=1.0))
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
