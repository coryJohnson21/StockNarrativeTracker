from datetime import datetime, timedelta

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import StockCall, Source
from app.services.extraction import CALL_TYPES

BULLISH_CALLS = ("buy",)
BEARISH_CALLS = ("sell", "avoid")


def call_consensus(counts: dict[str, int]) -> float | None:
    """Net stance across explicit calls, -1 (all sell/avoid) to +1 (all buy). Hold and
    watch count toward the denominator but neither direction."""
    total = sum(counts.get(t, 0) for t in CALL_TYPES)
    if total == 0:
        return None
    bullish = sum(counts.get(t, 0) for t in BULLISH_CALLS)
    bearish = sum(counts.get(t, 0) for t in BEARISH_CALLS)
    return round((bullish - bearish) / total, 2)


def _serialize(call: StockCall, source: Source) -> dict:
    return {
        "call": call.call,
        "price_target": call.price_target,
        "reasoning": call.reasoning,
        "called_at": call.called_at,
        "source_title": source.title,
        "source_type": source.type,
        "source_channel": source.channel,
        "source_url": source.url,
    }


async def get_stock_calls(db: AsyncSession, stock_id, limit: int = 50) -> list[dict]:
    q = (
        select(StockCall, Source)
        .join(Source, StockCall.source_id == Source.id)
        .where(StockCall.stock_id == stock_id)
        .order_by(desc(StockCall.called_at))
        .limit(limit)
    )
    return [_serialize(call, source) for call, source in (await db.execute(q)).all()]


async def get_stock_call_summary(db: AsyncSession, stock_id, window_days: int = 90, latest: int = 6) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    rows = (
        await db.execute(
            select(StockCall.call, func.count(StockCall.id))
            .where(StockCall.stock_id == stock_id, StockCall.called_at >= cutoff)
            .group_by(StockCall.call)
        )
    ).all()
    counts = {t: 0 for t in CALL_TYPES}
    for call_type, n in rows:
        if call_type in counts:
            counts[call_type] = n

    return {
        "window_days": window_days,
        "total": sum(counts.values()),
        "counts": counts,
        "consensus": call_consensus(counts),
        "latest": await get_stock_calls(db, stock_id, limit=latest),
    }
