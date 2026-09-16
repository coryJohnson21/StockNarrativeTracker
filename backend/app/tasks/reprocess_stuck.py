"""Re-dispatch sources left in 'pending' or 'processing' -- typically because the
server restarted (uvicorn --reload picks up a code change, a deploy) while a
background ingestion job was mid-flight. Pollers dedupe by URL, so a re-poll
skips these rows; nothing else ever picks them up.

Usage:
    docker compose exec backend python -m app.tasks.reprocess_stuck
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript
from app.services.sec_edgar import TRACKED_FORMS
from app.tasks.processing import (
    process_podcast_episode_source,
    process_sec_filing_source,
    process_text_source,
    process_youtube_source,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STUCK_STATUSES = ("pending", "processing")


async def reprocess_stuck() -> dict:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Source.id, Source.type, Transcript.content)
                .outerjoin(Transcript, Transcript.source_id == Source.id)
                .where(Source.status.in_(STUCK_STATUSES))
                .order_by(Source.created_at)
            )
        ).all()

    logger.info("Found %d stuck sources", len(rows))
    counts = {"youtube": 0, "podcast": 0, "filing": 0, "text": 0, "unrecoverable": 0}
    for source_id, source_type, transcript_text in rows:
        sid = str(source_id)
        if source_type == "youtube":
            await process_youtube_source(sid)
            counts["youtube"] += 1
        elif source_type == "podcast":
            await process_podcast_episode_source(sid)
            counts["podcast"] += 1
        elif source_type in TRACKED_FORMS:
            await process_sec_filing_source(sid)
            counts["filing"] += 1
        elif transcript_text:
            await process_text_source(sid, transcript_text)
            counts["text"] += 1
        else:
            # Text sources (Reddit, pasted transcripts) whose text was never stored
            # can't be rebuilt; mark them so they stop looking in-progress.
            async with AsyncSessionLocal() as db:
                source = (await db.execute(select(Source).where(Source.id == source_id))).scalar_one()
                source.status = "failed"
                source.error_message = "Interrupted before its text was stored; re-ingest to recover"
                source.updated_at = datetime.utcnow()
                await db.commit()
            counts["unrecoverable"] += 1
    logger.info("Reprocess complete: %s", counts)
    return counts


if __name__ == "__main__":
    asyncio.run(reprocess_stuck())
