"""Ten sources repeating the same headline is one signal, not ten. Embed each
mention's context, measure how new it is relative to what was already said about
the stock, and cluster a window of mentions into distinct storylines."""
import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import StockMention, Source
from app.services.embeddings import generate_embeddings

logger = logging.getLogger(__name__)

NOVELTY_LOOKBACK_DAYS = 30
# Cosine similarity at or above which two mention contexts are "the same story".
# text-embedding-3-small puts paraphrases of one claim around 0.85-0.95 and
# unrelated claims about the same company around 0.4-0.7.
SAME_STORY_THRESHOLD = 0.85


# --- pure helpers -------------------------------------------------------------


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def novelty_from_max_similarity(max_similarity: Optional[float]) -> Optional[float]:
    """1 - similarity to the closest prior mention, clamped. None when there is
    nothing to compare against (the first thing ever said about a stock isn't
    'novel', it's unmeasured)."""
    if max_similarity is None:
        return None
    return round(min(max(1.0 - max_similarity, 0.0), 1.0), 4)


def cluster_greedy(embeddings: list[Sequence[float]], threshold: float = SAME_STORY_THRESHOLD) -> list[list[int]]:
    """Single-pass clustering in the given (chronological) order: each item joins
    the first existing cluster whose running centroid is at least `threshold`
    similar, else starts a new one. Returns index lists, in order of first appearance."""
    clusters: list[list[int]] = []
    centroids: list[list[float]] = []
    for i, emb in enumerate(embeddings):
        best, best_sim = -1, threshold
        for c, centroid in enumerate(centroids):
            sim = cosine_similarity(emb, centroid)
            if sim >= best_sim:
                best, best_sim = c, sim
        if best == -1:
            clusters.append([i])
            centroids.append([float(x) for x in emb])
        else:
            clusters[best].append(i)
            n = len(clusters[best])
            centroids[best] = [(c * (n - 1) + float(x)) / n for c, x in zip(centroids[best], emb)]
    return clusters


# --- database ------------------------------------------------------------------


async def prior_max_similarity(
    db: AsyncSession, stock_id, source_id, mentioned_at: datetime, embedding: Sequence[float]
) -> Optional[float]:
    """Highest cosine similarity between this embedding and any other source's
    mention of the same stock in the preceding lookback window."""
    since = mentioned_at - timedelta(days=NOVELTY_LOOKBACK_DAYS)
    row = await db.execute(
        select(func.max(1 - StockMention.embedding.cosine_distance(list(embedding)))).where(
            StockMention.stock_id == stock_id,
            StockMention.source_id != source_id,
            StockMention.embedding.isnot(None),
            StockMention.mentioned_at >= since,
            StockMention.mentioned_at < mentioned_at,
        )
    )
    value = row.scalar()
    return float(value) if value is not None else None


async def embed_and_score_mentions(db: AsyncSession, mentions: list[StockMention]) -> int:
    """Embed the contexts of freshly stored mentions and compute each one's novelty
    against earlier mentions. Mentions must already be flushed."""
    targets = [m for m in mentions if m.context and m.context.strip()]
    if not targets:
        return 0
    vectors = await generate_embeddings([m.context for m in targets])
    for m, vec in zip(targets, vectors):
        m.embedding = vec
    await db.flush()
    for m in targets:
        m.novelty = novelty_from_max_similarity(
            await prior_max_similarity(db, m.stock_id, m.source_id, m.mentioned_at, m.embedding)
        )
    return len(targets)


async def backfill_mention_embeddings(db: AsyncSession, batch_size: int = 200) -> dict:
    """Embed every mention that has a context but no embedding, oldest first, then
    fill in novelty for anything embedded but unscored -- also oldest first, so each
    mention is compared only against what came before it."""
    embedded = 0
    while True:
        batch = (
            await db.execute(
                select(StockMention)
                .where(StockMention.embedding.is_(None), StockMention.context.isnot(None), StockMention.context != "")
                .order_by(StockMention.mentioned_at)
                .limit(batch_size)
            )
        ).scalars().all()
        if not batch:
            break
        vectors = await generate_embeddings([m.context for m in batch])
        for m, vec in zip(batch, vectors):
            m.embedding = vec
        await db.commit()
        embedded += len(batch)

    scored = 0
    unscored = (
        await db.execute(
            select(StockMention)
            .where(StockMention.embedding.isnot(None), StockMention.novelty.is_(None))
            .order_by(StockMention.mentioned_at)
        )
    ).scalars().all()
    for i, m in enumerate(unscored, 1):
        sim = await prior_max_similarity(db, m.stock_id, m.source_id, m.mentioned_at, m.embedding)
        m.novelty = novelty_from_max_similarity(sim)
        if m.novelty is None:
            m.novelty = 1.0  # first word on the stock in its window: mark measured, fully new
        scored += 1
        if i % 500 == 0:
            await db.commit()
    await db.commit()
    return {"embedded": embedded, "scored": scored}


async def get_stock_narratives(
    db: AsyncSession, stock_id, days: int = NOVELTY_LOOKBACK_DAYS, threshold: float = SAME_STORY_THRESHOLD, max_clusters: int = 8
) -> dict:
    """Distinct storylines about a stock in the window, largest first, with how much
    of the coverage is just repetition."""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    rows = (
        await db.execute(
            select(StockMention, Source.title, Source.channel, Source.type)
            .join(Source, StockMention.source_id == Source.id)
            .where(StockMention.stock_id == stock_id, StockMention.mentioned_at >= since)
            .order_by(StockMention.mentioned_at)
        )
    ).all()

    embedded = [(m, title, channel, stype) for m, title, channel, stype in rows if m.embedding is not None]
    clusters = cluster_greedy([m.embedding for m, *_ in embedded], threshold)

    week_ago = now - timedelta(days=7)
    recent_novelty = [m.novelty for m, *_ in rows if m.novelty is not None and m.mentioned_at >= week_ago]

    out = []
    for idx_list in sorted(clusters, key=len, reverse=True)[:max_clusters]:
        members = [embedded[i] for i in idx_list]
        first, *_ = members[0]
        sentiments = [m.sentiment_score for m, *_ in members if m.sentiment_score is not None]
        out.append(
            {
                "size": len(members),
                "first_seen": first.mentioned_at,
                "last_seen": members[-1][0].mentioned_at,
                "avg_sentiment": round(sum(sentiments) / len(sentiments), 1) if sentiments else 0.0,
                "unique_sources": len({m.source_id for m, *_ in members}),
                "representative": first.context,
                "source_title": members[0][1],
                "source_channel": members[0][2] or members[0][3],
                "novelty": first.novelty,
            }
        )

    return {
        "window_days": days,
        "mention_count": len(rows),
        "embedded_count": len(embedded),
        "distinct_narratives": len(clusters),
        "echo_ratio": round(1 - len(clusters) / len(embedded), 3) if embedded else None,
        "novelty_7d": round(sum(recent_novelty) / len(recent_novelty), 3) if recent_novelty else None,
        "clusters": out,
    }
