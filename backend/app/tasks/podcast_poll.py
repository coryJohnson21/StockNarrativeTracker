import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, PodcastFeed
from app.services import podcast as podcast_service
from app.services import youtube as youtube_service
from app.tasks.processing import process_podcast_episode_source, process_youtube_source

logger = logging.getLogger(__name__)

# Same reasoning as sec_scan.py's _PROCESSING_CONCURRENCY: the gpt-4o tier's
# per-minute token cap means concurrency beyond 1 just produces more 429s.
_processing_semaphore = asyncio.Semaphore(1)

# Safety cap on episodes processed in a single poll, in case a feed genuinely
# published a burst of new episodes since we last checked.
MAX_NEW_EPISODES_PER_POLL = 3

# A feed's full RSS history can be hundreds of episodes deep. Subscribing is meant to
# auto-ingest *new* episodes going forward, not backfill the archive -- so a feed's very
# first poll only looks this far back, establishing last_polled_at as the baseline for
# every poll after that. Without this, a feed with no last_polled_at would fall back to
# "newest not-yet-ingested," which just works through the backlog a few episodes at a
# time on every subsequent poll instead of coming up empty when there's nothing new.
FIRST_POLL_LOOKBACK_HOURS = 48


async def _process_bounded(source_id: str, is_youtube_channel: bool) -> None:
    async with _processing_semaphore:
        if is_youtube_channel:
            await process_youtube_source(source_id)
        else:
            await process_podcast_episode_source(source_id)


async def poll_feed(feed_id) -> list[str]:
    """Fetch one feed (podcast RSS or a YouTube channel's uploads feed), create Source
    rows for episodes/videos published since the last poll (deduped by URL as a safety
    net), process them, and stamp last_polled_at."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if feed is None:
            raise ValueError("Podcast feed not found")

        is_youtube_channel = feed.source_type == "youtube"
        cutoff = feed.last_polled_at or (datetime.utcnow() - timedelta(hours=FIRST_POLL_LOOKBACK_HOURS))

        if is_youtube_channel:
            episodes = await youtube_service.parse_channel_feed(feed.url)
        else:
            episodes = await podcast_service.parse_feed(feed.url)
        # Newest first by publish date when available (missing dates sort last),
        # so the cap below takes the most recent episodes rather than feed order.
        episodes.sort(key=lambda e: e.get("published_at") or (), reverse=True)

        created_ids = []
        for ep in episodes:
            if len(created_ids) >= MAX_NEW_EPISODES_PER_POLL:
                break

            # No publish date means we can't confirm this is actually new -- and
            # since the list is sorted newest-first, everything from here on is
            # this old or older (or equally undated), so stop looking entirely.
            if not ep.get("published_at"):
                break
            published_at = datetime(*ep["published_at"][:6])
            if published_at <= cutoff:
                break

            existing = await db.execute(select(Source).where(Source.url == ep["url"]))
            if existing.scalar_one_or_none() is not None:
                continue

            source = Source(
                type=feed.source_type,
                url=ep["url"],
                title=ep["title"],
                channel=feed.label,
                published_at=published_at,
                duration_seconds=ep.get("duration_seconds"),
                status="pending",
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            created_ids.append(str(source.id))

        feed.last_polled_at = datetime.utcnow()
        await db.commit()

    await asyncio.gather(*(_process_bounded(sid, is_youtube_channel) for sid in created_ids))
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
