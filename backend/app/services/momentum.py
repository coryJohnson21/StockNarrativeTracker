import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, distinct, case, desc
from app.models.models import (
    Stock, Theme, StockMention, ThemeMention,
    StockMomentum, ThemeMomentum, Source,
)

# Press releases & earnings transcripts vs. general media coverage (CNBC, Bloomberg,
# YouTube, podcasts, pasted transcripts). Everything not explicitly a filing/earnings
# type is treated as media.
FILING_SOURCE_TYPES = ("10-K", "10-Q", "8-K", "earnings_call")

# Watchlist media baskets — finer-grained than the filing/media split above, used to
# show where a watched ticker's narrative is actually coming from. Source.type values
# are tagged at ingestion time (YouTube tab -> "youtube", Paste Transcript tab lets the
# user pick "news" or "reddit", SEC Filings tab -> 10-K/10-Q/8-K).
YOUTUBE_SOURCE_TYPES = ("youtube",)
PODCAST_SOURCE_TYPES = ("podcast",)
NEWS_SOURCE_TYPES = ("news", "cnbc", "bloomberg")
REDDIT_SOURCE_TYPES = ("reddit", "wallstreetbets", "r/wallstreetbets", "r/stocks")
TWITTER_SOURCE_TYPES = ("twitter", "x")

WATCHLIST_BASKETS = {
    "youtube": YOUTUBE_SOURCE_TYPES,
    "news": NEWS_SOURCE_TYPES,
    "reddit": REDDIT_SOURCE_TYPES,
    "filing": FILING_SOURCE_TYPES,
}

# Mapping used by the /trending?channel= filter on the dashboard media breakout.
MEDIA_CHANNEL_SOURCE_TYPES: dict[str, tuple[str, ...]] = {
    "youtube": YOUTUBE_SOURCE_TYPES,
    "podcast": PODCAST_SOURCE_TYPES,
    "news": NEWS_SOURCE_TYPES,
    "reddit": REDDIT_SOURCE_TYPES,
    "x": TWITTER_SOURCE_TYPES,
}

# A company talking about itself in its own press release isn't an independent signal
# the way outside coverage is, so self-mentions count for less toward momentum scoring
# (frequency/growth/sentiment) -- though raw mention counts shown in the UI stay
# unweighted so users see real totals, not a discounted number.
SELF_MENTION_WEIGHT = 0.3

LABEL_ORDER = ("positive", "building", "mixed", "fading", "negative")

# Growth compares the last 7 days against the *preceding* 23 days (days 8-30), so the
# baseline never contains the period being measured.
RECENT_WINDOW_DAYS = 7
PRIOR_WINDOW_DAYS = 23

# Pseudo-counts pull small samples toward "nothing happened" so a single Reddit post
# can't register as a maxed-out growth spike or a decisive sentiment reading.
GROWTH_PSEUDO_COUNT = 2.0
SENTIMENT_PSEUDO_COUNT = 3.0


def sentiment_to_label(avg_sentiment: float) -> str:
    if avg_sentiment >= 50:
        return "positive"
    elif avg_sentiment >= 20:
        return "building"
    elif avg_sentiment > -20:
        return "mixed"
    elif avg_sentiment > -50:
        return "fading"
    return "negative"


def confidence_label(total_mentions: int, unique_sources: int) -> str:
    """How much to trust the sentiment/score given the sample behind it."""
    if total_mentions < 3 or unique_sources < 2:
        return "low"
    if total_mentions >= 10 and unique_sources >= 3:
        return "high"
    return "medium"


def growth_component(recent_7d: float, prior_23d: float, pseudo: float = GROWTH_PSEUDO_COUNT) -> float:
    """0-1 growth signal from a shrunk log-ratio of recent vs. expected weekly mentions.
    Flat activity -> 0.5; 4x the expected rate saturates at 1.0; a quarter of it floors at 0."""
    expected_7d = prior_23d * RECENT_WINDOW_DAYS / PRIOR_WINDOW_DAYS
    ratio = (recent_7d + pseudo) / (expected_7d + pseudo)
    return min(max(0.5 + math.log2(ratio) / 2, 0.0), 1.0)


def shrunk_sentiment(
    avg_sentiment: float, n: float, market_avg_sentiment: float = 0.0, pseudo: float = SENTIMENT_PSEUDO_COUNT
) -> float:
    """Sentiment relative to the whole universe's average, pulled toward zero when the
    sample is small. +40 when everything is +40 is noise, and +90 from one mention is
    a guess."""
    if n <= 0:
        return 0.0
    return (avg_sentiment - market_avg_sentiment) * n / (n + pseudo)


def share_of_voice_percentile(share: float, all_shares: list[float]) -> float:
    """Mid-rank percentile (0-1) of one entity's share of all mentions. Relative
    attention that doesn't move when we simply ingest more sources in a given week."""
    if not all_shares:
        return 0.0
    below = sum(1 for s in all_shares if s < share)
    ties = sum(1 for s in all_shares if s == share)
    return (below + 0.5 * ties) / len(all_shares)


def _compute_score(
    freq_percentile: float,
    recent_7d: float,
    prior_23d: float,
    avg_sentiment: float,
    total_mentions: float,
    unique_sources: int,
    market_avg_sentiment: float = 0.0,
) -> float:
    """
    Weighted momentum score (0–100).
    - 30% share-of-voice percentile
    - 30% growth (recent 7d vs. prior 23d, shrunk)
    - 25% sentiment (market-relative, shrunk)
    - 15% cross-source diversity
    """
    freq = min(max(freq_percentile, 0.0), 1.0)
    growth = growth_component(recent_7d, prior_23d)
    sentiment_norm = (shrunk_sentiment(avg_sentiment, total_mentions, market_avg_sentiment) + 100) / 200.0
    cross = min(unique_sources / 5.0, 1.0)

    score = (0.30 * freq + 0.30 * growth + 0.25 * sentiment_norm + 0.15 * cross) * 100
    return round(min(max(score, 0), 100), 1)


def _mention_weight_expr(mention_model):
    if hasattr(mention_model, "is_self_mention"):
        return case((mention_model.is_self_mention.is_(True), SELF_MENTION_WEIGHT), else_=1.0)
    # Themes have no "self-mention" concept (no single company files a theme).
    return 1.0


@dataclass
class MentionStats:
    total: int = 0
    recent_7d: int = 0
    recent_30d: int = 0
    prior_23d: int = 0
    avg_sentiment: float = 0.0
    unique_sources: int = 0
    w_total: float = 0.0
    w_recent_7d: float = 0.0
    w_recent_30d: float = 0.0
    w_prior_23d: float = 0.0
    w_sentiment_sum: float = 0.0

    @property
    def w_avg_sentiment(self) -> float:
        return self.w_sentiment_sum / self.w_total if self.w_total else 0.0

    @property
    def growth_rate(self) -> float:
        expected_7d = self.prior_23d * RECENT_WINDOW_DAYS / PRIOR_WINDOW_DAYS
        if expected_7d > 0:
            return (self.recent_7d - expected_7d) / expected_7d
        return 1.0 if self.recent_7d > 0 else 0.0


def _stats_columns(mention_model, now: datetime) -> list:
    cutoff_7d = now - timedelta(days=RECENT_WINDOW_DAYS)
    cutoff_30d = now - timedelta(days=RECENT_WINDOW_DAYS + PRIOR_WINDOW_DAYS)
    weight = _mention_weight_expr(mention_model)
    in_7d = mention_model.mentioned_at >= cutoff_7d
    in_30d = mention_model.mentioned_at >= cutoff_30d
    in_prior = and_(mention_model.mentioned_at >= cutoff_30d, mention_model.mentioned_at < cutoff_7d)
    return [
        func.count(mention_model.id).label("total"),
        func.sum(case((in_7d, 1), else_=0)).label("recent_7d"),
        func.sum(case((in_30d, 1), else_=0)).label("recent_30d"),
        func.sum(case((in_prior, 1), else_=0)).label("prior_23d"),
        func.avg(mention_model.sentiment_score).label("avg_sentiment"),
        func.count(distinct(mention_model.source_id)).label("unique_sources"),
        func.sum(weight).label("w_total"),
        func.sum(case((in_7d, weight), else_=0)).label("w_recent_7d"),
        func.sum(case((in_30d, weight), else_=0)).label("w_recent_30d"),
        func.sum(case((in_prior, weight), else_=0)).label("w_prior_23d"),
        func.sum(mention_model.sentiment_score * weight).label("w_sentiment_sum"),
    ]


def _stats_from_row(row) -> MentionStats:
    return MentionStats(
        total=row.total or 0,
        recent_7d=row.recent_7d or 0,
        recent_30d=row.recent_30d or 0,
        prior_23d=row.prior_23d or 0,
        avg_sentiment=float(row.avg_sentiment or 0.0),
        unique_sources=row.unique_sources or 0,
        w_total=float(row.w_total or 0.0),
        w_recent_7d=float(row.w_recent_7d or 0.0),
        w_recent_30d=float(row.w_recent_30d or 0.0),
        w_prior_23d=float(row.w_prior_23d or 0.0),
        w_sentiment_sum=float(row.w_sentiment_sum or 0.0),
    )


class _Universe:
    """Cross-entity context a single score depends on: everyone's 30-day share of
    voice and the mention-weighted average sentiment across the whole set."""

    def __init__(self, stats: list[MentionStats]):
        universe_30d = sum(s.w_recent_30d for s in stats)
        self.shares = [s.w_recent_30d / universe_30d if universe_30d else 0.0 for s in stats]
        self._universe_30d = universe_30d
        total_w = sum(s.w_total for s in stats)
        self.market_avg_sentiment = sum(s.w_sentiment_sum for s in stats) / total_w if total_w else 0.0

    def score(self, s: MentionStats) -> float:
        share = s.w_recent_30d / self._universe_30d if self._universe_30d else 0.0
        return _compute_score(
            freq_percentile=share_of_voice_percentile(share, self.shares) if s.w_recent_30d else 0.0,
            recent_7d=s.w_recent_7d,
            prior_23d=s.w_prior_23d,
            avg_sentiment=s.w_avg_sentiment,
            total_mentions=s.w_total,
            unique_sources=s.unique_sources,
            market_avg_sentiment=self.market_avg_sentiment,
        )


async def _refresh_momentum(
    db: AsyncSession, parent_model, mention_model, mention_fk_col, momentum_model, momentum_fk_name: str
) -> None:
    now = datetime.utcnow()

    parents = (await db.execute(select(parent_model))).scalars().all()

    rows = (
        await db.execute(
            select(mention_fk_col.label("parent_id"), *_stats_columns(mention_model, now)).group_by(mention_fk_col)
        )
    ).all()
    stats_by_parent = {row.parent_id: _stats_from_row(row) for row in rows}
    universe = _Universe(list(stats_by_parent.values()))

    existing = (await db.execute(select(momentum_model))).scalars().all()
    momentum_by_parent = {getattr(m, momentum_fk_name): m for m in existing}

    for parent in parents:
        s = stats_by_parent.get(parent.id, MentionStats())
        new_label = sentiment_to_label(s.avg_sentiment)

        momentum = momentum_by_parent.get(parent.id)
        if momentum is None:
            momentum = momentum_model(**{momentum_fk_name: parent.id})
            db.add(momentum)

        if momentum.label and momentum.label != new_label:
            momentum.previous_label = momentum.label
        momentum.label = new_label
        momentum.score = universe.score(s)
        momentum.mention_count = s.total
        momentum.mention_count_7d = s.recent_7d
        momentum.mention_count_30d = s.recent_30d
        momentum.mention_growth_rate = round(s.growth_rate, 3)
        momentum.avg_sentiment = round(s.avg_sentiment, 1)
        momentum.unique_sources = s.unique_sources
        momentum.computed_at = now

    await db.commit()


async def refresh_stock_momentum(db: AsyncSession) -> None:
    """Recompute momentum for all stocks."""
    await _refresh_momentum(db, Stock, StockMention, StockMention.stock_id, StockMomentum, "stock_id")


async def refresh_theme_momentum(db: AsyncSession) -> None:
    """Recompute momentum for all themes."""
    await _refresh_momentum(db, Theme, ThemeMention, ThemeMention.theme_id, ThemeMomentum, "theme_id")


async def _trending_by_type_filter(
    db: AsyncSession,
    mention_model,
    parent_model,
    parent_id_col,
    mention_fk_col,
    type_filter,
    limit: int,
    offset: int,
    min_score: float,
    extra_filter=None,
) -> tuple[list[dict], int]:
    """Live-aggregate momentum for an arbitrary source-type filter without touching
    the precomputed momentum tables, which stay aggregate-across-everything."""
    now = datetime.utcnow()

    q = (
        select(parent_model, *_stats_columns(mention_model, now))
        .join(mention_model, mention_fk_col == parent_id_col)
        .join(Source, mention_model.source_id == Source.id)
        .where(type_filter)
        .group_by(parent_id_col)
    )
    if extra_filter is not None:
        q = q.where(extra_filter)

    rows = (await db.execute(q)).all()
    stats = [_stats_from_row(row) for row in rows]
    universe = _Universe(stats)

    results = []
    for row, s in zip(rows, stats):
        score = universe.score(s)
        if score < min_score:
            continue
        results.append(
            {
                "parent": row[0],
                "score": score,
                "mention_count": s.total,
                "mention_count_7d": s.recent_7d,
                "mention_count_30d": s.recent_30d,
                "mention_growth_rate": round(s.growth_rate, 3),
                "avg_sentiment": round(s.avg_sentiment, 1),
                "unique_sources": s.unique_sources,
                "ai_summary": None,
                "computed_at": now,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    total_count = len(results)
    return results[offset:offset + limit], total_count


def _category_type_filter(category: str):
    if category == "filing":
        return Source.type.in_(FILING_SOURCE_TYPES)
    return Source.type.notin_(FILING_SOURCE_TYPES)


async def get_trending_stocks_by_category(
    db: AsyncSession, category: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    return await _trending_by_type_filter(
        db, StockMention, Stock, Stock.id, StockMention.stock_id,
        _category_type_filter(category), limit, offset, min_score,
    )


async def get_trending_themes_by_category(
    db: AsyncSession, category: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    return await _trending_by_type_filter(
        db, ThemeMention, Theme, Theme.id, ThemeMention.theme_id,
        _category_type_filter(category), limit, offset, min_score,
        extra_filter=Theme.is_tracked.is_(True),
    )


async def get_trending_stocks_by_channel(
    db: AsyncSession, channel: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    types = MEDIA_CHANNEL_SOURCE_TYPES[channel]
    return await _trending_by_type_filter(
        db, StockMention, Stock, Stock.id, StockMention.stock_id,
        Source.type.in_(types), limit, offset, min_score,
    )


async def get_trending_themes_by_channel(
    db: AsyncSession, channel: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    types = MEDIA_CHANNEL_SOURCE_TYPES[channel]
    return await _trending_by_type_filter(
        db, ThemeMention, Theme, Theme.id, ThemeMention.theme_id,
        Source.type.in_(types), limit, offset, min_score,
        extra_filter=Theme.is_tracked.is_(True),
    )


async def get_stock_mention_breakdown(db: AsyncSession, stock_id) -> dict:
    """Per-category (filing vs. media) mention count, sentiment, and source diversity
    for a single stock — used on the stock landing page."""
    breakdown = {}
    for category in ("filing", "media"):
        type_filter = (
            Source.type.in_(FILING_SOURCE_TYPES)
            if category == "filing"
            else Source.type.notin_(FILING_SOURCE_TYPES)
        )
        q = (
            select(
                func.count(StockMention.id).label("total"),
                func.avg(StockMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(StockMention.source_id)).label("unique_sources"),
            )
            .join(Source, StockMention.source_id == Source.id)
            .where(StockMention.stock_id == stock_id, type_filter)
        )
        row = (await db.execute(q)).one()
        breakdown[category] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


async def get_stock_self_vs_external_breakdown(db: AsyncSession, stock_id) -> dict:
    """Mention count, sentiment, and source diversity split by self-mention (the company
    talking about itself in its own filing) vs. external (mentioned by someone else, or
    in general media) -- used on the stock landing page to show how much of a stock's
    apparent momentum is the company's own press releases vs. independent coverage."""
    breakdown = {}
    for key, is_self in (("self", True), ("external", False)):
        q = (
            select(
                func.count(StockMention.id).label("total"),
                func.avg(StockMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(StockMention.source_id)).label("unique_sources"),
            )
            .where(StockMention.stock_id == stock_id, StockMention.is_self_mention.is_(is_self))
        )
        row = (await db.execute(q)).one()
        breakdown[key] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


def empty_basket_breakdown() -> dict:
    return {
        name: {"mention_count": 0, "avg_sentiment": 0.0, "unique_sources": 0}
        for name in WATCHLIST_BASKETS
    }


async def get_stock_basket_breakdown(db: AsyncSession, stock_id) -> dict:
    """Per-basket (YouTube / news / Reddit & forums / filing) mention count, sentiment,
    and source diversity for a single stock — used on the watchlist."""
    breakdown = empty_basket_breakdown()
    for basket_name, source_types in WATCHLIST_BASKETS.items():
        q = (
            select(
                func.count(StockMention.id).label("total"),
                func.avg(StockMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(StockMention.source_id)).label("unique_sources"),
            )
            .join(Source, StockMention.source_id == Source.id)
            .where(StockMention.stock_id == stock_id, Source.type.in_(source_types))
        )
        row = (await db.execute(q)).one()
        breakdown[basket_name] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


# Bucket granularity and lookback window per chart range — daily buckets get noisy
# past a few months, so wider ranges roll up to weekly/monthly.
MENTION_HISTORY_RANGES = {
    "1mo": (30, "day"),
    "3mo": (90, "day"),
    "6mo": (180, "week"),
    "1y": (365, "week"),
    "5y": (1825, "month"),
}


async def get_stock_mention_history(db: AsyncSession, stock_id, range_: str = "6mo") -> list[dict]:
    """Mention count + average sentiment over time for a stock, bucketed from raw
    StockMention timestamps — lets the narrative momentum chart show when a story
    built, not just where it stands today."""
    days, granularity = MENTION_HISTORY_RANGES.get(range_, MENTION_HISTORY_RANGES["6mo"])
    cutoff = datetime.utcnow() - timedelta(days=days)

    bucket = func.date_trunc(granularity, StockMention.mentioned_at)
    q = (
        select(
            bucket.label("bucket"),
            func.count(StockMention.id).label("mention_count"),
            func.avg(StockMention.sentiment_score).label("avg_sentiment"),
        )
        .where(StockMention.stock_id == stock_id, StockMention.mentioned_at >= cutoff)
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "date": row.bucket.date().isoformat(),
            "mention_count": row.mention_count,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
        }
        for row in rows
    ]


async def get_theme_mention_breakdown(db: AsyncSession, theme_id) -> dict:
    """Per-category (filing vs. media) mention count, sentiment, and source diversity
    for a single theme — used on the theme landing page."""
    breakdown = {}
    for category in ("filing", "media"):
        type_filter = (
            Source.type.in_(FILING_SOURCE_TYPES)
            if category == "filing"
            else Source.type.notin_(FILING_SOURCE_TYPES)
        )
        q = (
            select(
                func.count(ThemeMention.id).label("total"),
                func.avg(ThemeMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(ThemeMention.source_id)).label("unique_sources"),
            )
            .join(Source, ThemeMention.source_id == Source.id)
            .where(ThemeMention.theme_id == theme_id, type_filter)
        )
        row = (await db.execute(q)).one()
        breakdown[category] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


async def get_stock_mention_contexts(db: AsyncSession, stock_id, category: str, limit: int = 6) -> list[str]:
    """Sample of recent mention context quotes for one category, used to ground the
    narrative-synthesis prompt in what was actually said rather than just aggregate scores."""
    type_filter = (
        Source.type.in_(FILING_SOURCE_TYPES)
        if category == "filing"
        else Source.type.notin_(FILING_SOURCE_TYPES)
    )
    q = (
        select(StockMention.context)
        .join(Source, StockMention.source_id == Source.id)
        .where(StockMention.stock_id == stock_id, type_filter, StockMention.context.isnot(None))
        .order_by(desc(StockMention.mentioned_at))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [row[0] for row in rows if row[0]]


async def get_top_stocks_for_theme(db: AsyncSession, theme_id, limit: int = 8) -> list[dict]:
    """Stocks most often mentioned in the same sources as this theme (co-mention count)."""
    q = (
        select(
            Stock.ticker,
            Stock.company_name,
            func.count(distinct(StockMention.source_id)).label("co_mentions"),
        )
        .join(StockMention, StockMention.stock_id == Stock.id)
        .join(ThemeMention, ThemeMention.source_id == StockMention.source_id)
        .where(ThemeMention.theme_id == theme_id)
        .group_by(Stock.id)
        .order_by(desc("co_mentions"))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [
        {"ticker": row.ticker, "company_name": row.company_name, "co_mentions": row.co_mentions}
        for row in rows
    ]


async def refresh_market_data_cache(db: AsyncSession) -> None:
    """Fetch and cache current price + market cap for all stocks with a momentum record.
    Called on a slow schedule — not during per-source processing to avoid hammering Yahoo
    Finance on every new ingest."""
    from app.services import market_data as _market_data

    rows = (await db.execute(
        select(Stock, StockMomentum).join(StockMomentum, Stock.id == StockMomentum.stock_id)
    )).all()

    for stock, momentum in rows:
        md = None
        # Yahoo's unofficial API is flaky under sequential batch load -- a None
        # result here is far more often a transient hiccup than a real "no data,"
        # so retry a couple times before treating it as one.
        for attempt in range(3):
            try:
                md = await _market_data.fetch_market_data(stock.ticker)
            except Exception:
                md = None
            if md and md.get("current_price"):
                break
            if attempt < 2:
                await asyncio.sleep(1.0)

        price = md.get("current_price") if md else None
        if price:
            stock.is_public = True
            momentum.current_price = price
            momentum.market_cap = md.get("market_cap")
        elif stock.is_public is None:
            # Never successfully fetched before -- safe to mark as no-data.
            # Will flip to True automatically once/if a fetch succeeds.
            stock.is_public = False
        # else: this stock previously had a confirmed status (public with a
        # price, or confirmed private/delisted) -- leave it alone rather than
        # let one more failed fetch wipe out or flap a previously-good value.

        await asyncio.sleep(0.25)

    await db.commit()


async def get_stock_momentum_extras(db: AsyncSession, stock_ids: list) -> dict:
    """Batch-fetch previous_label, current_price, market_cap from StockMomentum for a
    list of stock IDs — used to enrich live-aggregate trending query results."""
    if not stock_ids:
        return {}
    q = select(
        StockMomentum.stock_id,
        StockMomentum.previous_label,
        StockMomentum.current_price,
        StockMomentum.market_cap,
    ).where(StockMomentum.stock_id.in_(stock_ids))
    rows = (await db.execute(q)).all()
    return {
        row.stock_id: {
            "previous_label": row.previous_label,
            "current_price": row.current_price,
            "market_cap": row.market_cap,
        }
        for row in rows
    }


async def get_theme_momentum_extras(db: AsyncSession, theme_ids: list) -> dict:
    """Batch-fetch previous_label from ThemeMomentum for a list of theme IDs -- used to
    enrich live-aggregate trending query results, same purpose as get_stock_momentum_extras."""
    if not theme_ids:
        return {}
    q = select(ThemeMomentum.theme_id, ThemeMomentum.previous_label).where(
        ThemeMomentum.theme_id.in_(theme_ids)
    )
    rows = (await db.execute(q)).all()
    return {row.theme_id: {"previous_label": row.previous_label} for row in rows}
