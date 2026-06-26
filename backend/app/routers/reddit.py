import re
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import RedditFeed, Source
from app.schemas.schemas import RedditFeedAddRequest, RedditFeedResponse, RedditFeedListResponse
from app.tasks.reddit_poll import poll_subreddit

router = APIRouter(prefix="/reddit", tags=["reddit"])

_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,50}$")


async def _build_response(db: AsyncSession, feed: RedditFeed) -> RedditFeedResponse:
    count = (
        await db.execute(
            select(func.count(Source.id)).where(Source.channel == f"r/{feed.subreddit}")
        )
    ).scalar() or 0
    return RedditFeedResponse(
        id=feed.id,
        subreddit=feed.subreddit,
        last_polled_at=feed.last_polled_at,
        created_at=feed.created_at,
        post_count=count,
    )


@router.get("", response_model=RedditFeedListResponse)
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RedditFeed).order_by(desc(RedditFeed.created_at)))
    feeds = result.scalars().all()
    return {"feeds": [await _build_response(db, f) for f in feeds]}


@router.post("", response_model=RedditFeedResponse, status_code=201)
async def add_feed(request: RedditFeedAddRequest, db: AsyncSession = Depends(get_db)):
    sub = request.subreddit.strip().lstrip("r/").lstrip("/")
    if not _SUBREDDIT_RE.match(sub):
        raise HTTPException(status_code=400, detail="Invalid subreddit name")

    existing = await db.execute(select(RedditFeed).where(RedditFeed.subreddit == sub))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Already subscribed to this subreddit")

    feed = RedditFeed(subreddit=sub)
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return await _build_response(db, feed)


@router.delete("/{feed_id}", status_code=204)
async def remove_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RedditFeed).where(RedditFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()


@router.post("/{feed_id}/poll")
async def poll_now(feed_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RedditFeed).where(RedditFeed.id == feed_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    background_tasks.add_task(poll_subreddit, feed_id)
    return {"status": "started", "detail": "Fetching new posts in the background"}
