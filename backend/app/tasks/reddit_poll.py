import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, RedditFeed
from app.services.reddit import fetch_hot_posts
from app.tasks.processing import process_text_source

logger = logging.getLogger(__name__)

_processing_semaphore = asyncio.Semaphore(1)
MAX_NEW_POSTS_PER_POLL = 5


async def _process_bounded(source_id: str, text: str) -> None:
    async with _processing_semaphore:
        await process_text_source(source_id, text)


async def poll_subreddit(feed_id) -> list[str]:
    """Fetch new hot posts from one subreddit, create Source rows for unseen posts,
    process them through the text extraction pipeline, and stamp last_polled_at."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RedditFeed).where(RedditFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if feed is None:
            raise ValueError("Reddit feed not found")

        subreddit = feed.subreddit
        posts = await fetch_hot_posts(subreddit, limit=25)

        created = []
        for post in posts:
            if len(created) >= MAX_NEW_POSTS_PER_POLL:
                break

            existing = await db.execute(select(Source).where(Source.url == post["url"]))
            if existing.scalar_one_or_none() is not None:
                continue

            source = Source(
                type="reddit",
                url=post["url"],
                title=post["title"],
                channel=f"r/{subreddit}",
                status="pending",
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            created.append((str(source.id), post["text"]))

        feed.last_polled_at = datetime.utcnow()
        await db.commit()

    await asyncio.gather(*(_process_bounded(sid, text) for sid, text in created))
    return [sid for sid, _ in created]


async def poll_all_subreddits() -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RedditFeed.id))
        feed_ids = [row[0] for row in result.all()]

    total_new = 0
    failed = []
    for feed_id in feed_ids:
        try:
            total_new += len(await poll_subreddit(feed_id))
        except Exception:
            logger.exception(f"Reddit poll failed for feed {feed_id}")
            failed.append(str(feed_id))

    logger.info(f"Reddit poll complete: {total_new} new posts ingested, {len(failed)} feeds failed")
    return {"new_posts": total_new, "failed_feeds": failed}
