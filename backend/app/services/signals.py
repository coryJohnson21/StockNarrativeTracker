"""Divergences are where a narrative dataset earns its keep: management saying
one thing while the market says another, a story improving while the price
falls, or a crowd all leaning the same way on a stale story. Each detector is a
pure function over already-aggregated numbers so the thresholds are testable."""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Source, Stock, StockMention, StockMomentum
from app.services.momentum import FILING_SOURCE_TYPES
from app.services.research import load_price_series

MIN_MENTIONS = 2
TONE_GAP = 30.0           # sentiment points between filings and media before it's a gap
SENTIMENT_SHIFT = 20.0    # week-over-prior change in average sentiment that counts as a shift
PRICE_MOVE = 0.05         # 20-trading-day move that counts as "the price went somewhere"
CROWDED_ATTENTION_PCT = 0.8
CROWDED_SENTIMENT = 50.0
CROWDED_NOVELTY = 0.3
PRICE_WINDOW_TRADING_DAYS = 20


def _signal(key: str, severity: str, title: str, detail: str, **metrics) -> dict:
    return {"key": key, "severity": severity, "title": title, "detail": detail, "metrics": metrics}


def management_vs_media_signal(
    filing_sentiment: float, filing_n: int, media_sentiment: float, media_n: int, guidance_direction: Optional[str]
) -> Optional[dict]:
    """Company filings vs. outside coverage. Guidance direction is the strongest tell
    when it points against the tone of coverage."""
    if guidance_direction == "raised" and media_n >= MIN_MENTIONS and media_sentiment < -10:
        return _signal(
            "management_vs_media", "alert",
            "Guidance raised while coverage is negative",
            "The company lifted its outlook in its latest filing, but media sentiment is still negative. "
            "Either the market is slow to update or it doesn't believe the guide.",
            guidance_direction=guidance_direction, media_sentiment=round(media_sentiment, 1), media_n=media_n,
        )
    if guidance_direction == "lowered" and media_n >= MIN_MENTIONS and media_sentiment > 20:
        return _signal(
            "management_vs_media", "alert",
            "Guidance cut while coverage stays bullish",
            "The company lowered its outlook, yet coverage remains upbeat. Bullish narratives that "
            "outlive a guide-down tend to be the last to leave.",
            guidance_direction=guidance_direction, media_sentiment=round(media_sentiment, 1), media_n=media_n,
        )
    if filing_n < MIN_MENTIONS or media_n < MIN_MENTIONS:
        return None
    gap = filing_sentiment - media_sentiment
    if abs(gap) < TONE_GAP:
        return None
    if gap > 0:
        return _signal(
            "management_vs_media", "watch",
            "Management more upbeat than the market",
            f"Filings and earnings materials read {gap:.0f} points more positive than outside coverage. "
            "Companies always sell; the question is whether coverage is missing something or seeing through it.",
            filing_sentiment=round(filing_sentiment, 1), media_sentiment=round(media_sentiment, 1), gap=round(gap, 1),
        )
    return _signal(
        "management_vs_media", "watch",
        "Market more upbeat than management",
        f"Outside coverage reads {-gap:.0f} points more positive than the company's own filings. "
        "Management is rarely the more cautious party without reason.",
        filing_sentiment=round(filing_sentiment, 1), media_sentiment=round(media_sentiment, 1), gap=round(gap, 1),
    )


def narrative_vs_price_signal(
    recent_sentiment: Optional[float], recent_n: int, prior_sentiment: Optional[float], prior_n: int,
    price_return: Optional[float],
) -> Optional[dict]:
    """Sentiment shift over the last week vs. the preceding weeks, against the price
    move over roughly the same window."""
    if price_return is None or recent_sentiment is None or prior_sentiment is None:
        return None
    if recent_n < MIN_MENTIONS or prior_n < MIN_MENTIONS:
        return None
    shift = recent_sentiment - prior_sentiment
    if shift >= SENTIMENT_SHIFT and price_return <= -PRICE_MOVE:
        return _signal(
            "narrative_vs_price", "watch",
            "Narrative improving while the price falls",
            f"Sentiment is up {shift:.0f} points week-over-prior while the stock is down {abs(price_return) * 100:.1f}% "
            f"over {PRICE_WINDOW_TRADING_DAYS} trading days. Early recognition or a bull trap; the backtest's sentiment IC says which has been more common.",
            sentiment_shift=round(shift, 1), price_return_pct=round(price_return * 100, 2),
        )
    if shift <= -SENTIMENT_SHIFT and price_return >= PRICE_MOVE:
        return _signal(
            "narrative_vs_price", "watch",
            "Price rising while the narrative sours",
            f"Sentiment is down {abs(shift):.0f} points week-over-prior while the stock is up {price_return * 100:.1f}% "
            f"over {PRICE_WINDOW_TRADING_DAYS} trading days. Coverage is either late to a move or spotting a problem the tape hasn't priced.",
            sentiment_shift=round(shift, 1), price_return_pct=round(price_return * 100, 2),
        )
    return None


def crowding_signal(
    attention_percentile: Optional[float], avg_sentiment: float, novelty_7d: Optional[float], mention_count_7d: int
) -> Optional[dict]:
    """Heavy, one-sided, repetitive coverage. The attention literature finds this is
    where short-term continuation gives way to reversal."""
    if attention_percentile is None or mention_count_7d < MIN_MENTIONS * 2:
        return None
    if attention_percentile < CROWDED_ATTENTION_PCT or abs(avg_sentiment) < CROWDED_SENTIMENT:
        return None
    if novelty_7d is None or novelty_7d > CROWDED_NOVELTY:
        return None
    side = "bullish" if avg_sentiment > 0 else "bearish"
    return _signal(
        "crowding", "alert",
        f"Crowded {side} narrative",
        f"Top {round((1 - attention_percentile) * 100)}% of stocks by attention this week, sentiment {avg_sentiment:+.0f}, "
        f"and only {novelty_7d:.2f} novelty: everyone is saying the same {side} thing. Historically the setup for mean reversion, not continuation.",
        attention_percentile=round(attention_percentile, 3), avg_sentiment=round(avg_sentiment, 1),
        novelty_7d=round(novelty_7d, 3), mention_count_7d=mention_count_7d,
    )


async def _sentiment_window(db: AsyncSession, stock_id, start: datetime, end: datetime) -> tuple[Optional[float], int]:
    row = (
        await db.execute(
            select(func.avg(StockMention.sentiment_score), func.count(StockMention.id)).where(
                StockMention.stock_id == stock_id,
                and_(StockMention.mentioned_at >= start, StockMention.mentioned_at < end),
            )
        )
    ).one()
    return (float(row[0]) if row[0] is not None else None), row[1] or 0


async def _latest_guidance(db: AsyncSession, ticker: str) -> Optional[str]:
    row = (
        await db.execute(
            select(Source.source_metadata["guidance_direction"].astext)
            .where(Source.type.in_(FILING_SOURCE_TYPES), Source.source_metadata["ticker"].astext == ticker)
            .order_by(desc(func.coalesce(Source.published_at, Source.created_at)))
            .limit(1)
        )
    ).scalar_one_or_none()
    return row or None


async def _attention_percentile(db: AsyncSession, stock_id) -> Optional[float]:
    """Mid-rank percentile of this stock's 7-day mention count among stocks with any
    mentions this week, from the precomputed momentum table."""
    counts = [
        n for (n,) in (await db.execute(select(StockMomentum.mention_count_7d).where(StockMomentum.mention_count_7d > 0))).all()
    ]
    mine = (await db.execute(select(StockMomentum.mention_count_7d).where(StockMomentum.stock_id == stock_id))).scalar_one_or_none()
    if not counts or not mine:
        return None
    below = sum(1 for c in counts if c < mine)
    ties = sum(1 for c in counts if c == mine)
    return (below + 0.5 * ties) / len(counts)


async def get_stock_signals(db: AsyncSession, stock: Stock, mention_breakdown: dict, momentum: Optional[StockMomentum]) -> dict:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    guidance = await _latest_guidance(db, stock.ticker)
    recent_sent, recent_n = await _sentiment_window(db, stock.id, week_ago, now + timedelta(days=1))
    prior_sent, prior_n = await _sentiment_window(db, stock.id, month_ago, week_ago)

    prices = await load_price_series(db, [stock.id])
    series = prices.get(stock.id)
    price_return = series.trailing_return(PRICE_WINDOW_TRADING_DAYS) if series is not None else None

    attention_pct = await _attention_percentile(db, stock.id)

    filing, media = mention_breakdown["filing"], mention_breakdown["media"]
    signals = [
        s for s in (
            management_vs_media_signal(
                filing["avg_sentiment"], filing["mention_count"], media["avg_sentiment"], media["mention_count"], guidance,
            ),
            narrative_vs_price_signal(recent_sent, recent_n, prior_sent, prior_n, price_return),
            crowding_signal(
                attention_pct,
                momentum.avg_sentiment if momentum else 0.0,
                momentum.novelty_7d if momentum else None,
                momentum.mention_count_7d if momentum else 0,
            ),
        )
        if s is not None
    ]

    return {
        "signals": signals,
        "inputs": {
            "guidance_direction": guidance,
            "sentiment_7d": round(recent_sent, 1) if recent_sent is not None else None,
            "mentions_7d": recent_n,
            "sentiment_prior_23d": round(prior_sent, 1) if prior_sent is not None else None,
            "mentions_prior_23d": prior_n,
            "price_return_20d_pct": round(price_return * 100, 2) if price_return is not None else None,
            "attention_percentile": round(attention_pct, 3) if attention_pct is not None else None,
            "novelty_7d": momentum.novelty_7d if momentum else None,
        },
    }
