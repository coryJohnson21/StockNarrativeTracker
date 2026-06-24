from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import PodcastFeed, Source
from app.schemas.schemas import PodcastFeedAddRequest, PodcastFeedResponse, PodcastFeedListResponse
from app.tasks.podcast_poll import poll_feed

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


async def _build_response(db: AsyncSession, feed: PodcastFeed) -> PodcastFeedResponse:
    count = (
        await db.execute(
            select(func.count(Source.id)).where(Source.channel == feed.label)
        )
    ).scalar() or 0
    return PodcastFeedResponse(
        id=feed.id,
        url=feed.url,
        label=feed.label,
        source_type=feed.source_type,
        last_polled_at=feed.last_polled_at,
        created_at=feed.created_at,
        episode_count=count,
    )


@router.get("", response_model=PodcastFeedListResponse)
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PodcastFeed).order_by(desc(PodcastFeed.created_at)))
    feeds = result.scalars().all()
    return {"feeds": [await _build_response(db, f) for f in feeds]}


@router.post("", response_model=PodcastFeedResponse, status_code=201)
async def add_feed(request: PodcastFeedAddRequest, db: AsyncSession = Depends(get_db)):
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Feed URL is required")

    existing = await db.execute(select(PodcastFeed).where(PodcastFeed.url == url))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="This feed is already subscribed")

    feed = PodcastFeed(url=url, label=request.label.strip(), source_type=request.source_type)
    db.add(feed)
    await db.commit()
    await db.refresh(feed)

    return await _build_response(db, feed)


@router.delete("/{feed_id}", status_code=204)
async def remove_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()


@router.post("/{feed_id}/poll")
async def poll_now(feed_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Check this feed for new episodes right now instead of waiting for the
    periodic poller."""
    result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    background_tasks.add_task(poll_feed, feed_id)
    return {"status": "started", "detail": "Checking feed for new episodes in the background"}
