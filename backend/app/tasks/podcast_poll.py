import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, PodcastFeed
from app.services import podcast as podcast_service
from app.tasks.processing import process_podcast_episode_source

logger = logging.getLogger(__name__)

# Same reasoning as sec_scan.py's _PROCESSING_CONCURRENCY: the gpt-4o tier's
# per-minute token cap means concurrency beyond 1 just produces more 429s.
_processing_semaphore = asyncio.Semaphore(1)

# A feed's full RSS history can be hundreds of episodes deep. Subscribing is meant
# to auto-ingest *new* episodes going forward, not backfill the archive — so every
# poll (first one included) only ever processes the newest few un-ingested episodes.
MAX_NEW_EPISODES_PER_POLL = 3


async def _process_bounded(source_id: str) -> None:
    async with _processing_semaphore:
        await process_podcast_episode_source(source_id)


async def poll_feed(feed_id) -> list[str]:
    """Fetch one feed's RSS, create Source rows for episodes not already ingested
    (deduped by audio URL), process them, and stamp last_polled_at."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if feed is None:
            raise ValueError("Podcast feed not found")

        episodes = await podcast_service.parse_feed(feed.url)
        # Newest first by publish date when available (missing dates sort last),
        # so the cap below takes the most recent episodes rather than feed order.
        episodes.sort(key=lambda e: e.get("published_at") or (), reverse=True)

        created_ids = []
        for ep in episodes:
            if len(created_ids) >= MAX_NEW_EPISODES_PER_POLL:
                break

            existing = await db.execute(select(Source).where(Source.url == ep["audio_url"]))
            if existing.scalar_one_or_none() is not None:
                continue

            published_at = None
            if ep.get("published_at"):
                published_at = datetime(*ep["published_at"][:6])

            source = Source(
                type=feed.source_type,
                url=ep["audio_url"],
                title=ep["title"],
                channel=feed.label,
                published_at=published_at,
                status="pending",
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            created_ids.append(str(source.id))

        feed.last_polled_at = datetime.utcnow()
        await db.commit()

    await asyncio.gather(*(_process_bounded(sid) for sid in created_ids))
    return created_ids


async def poll_all_feeds() -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PodcastFeed.id))
        feed_ids = [row[0] for row in result.all()]

    total_new = 0
    failed = []
    for feed_id in feed_ids:
        try:
            total_new += len(await poll_feed(feed_id))
        except Exception:
            logger.exception(f"Podcast feed poll failed for {feed_id}")
            failed.append(str(feed_id))

    logger.info(f"Podcast poll complete: {total_new} new episodes ingested, {len(failed)} feeds failed")
    return {"new_episodes": total_new, "failed_feeds": failed}
