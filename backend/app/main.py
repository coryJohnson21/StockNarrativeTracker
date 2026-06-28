import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.routers import ingest, stocks, themes, sources, sec, watchlist, podcasts, reddit
from app.tasks.sec_scan import scan_all_sp500
from app.tasks.podcast_poll import poll_all_feeds
from app.tasks.reddit_poll import poll_all_subreddits
from app.models.models import RedditFeed
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DEFAULT_SUBREDDITS = ["stocks", "wallstreetbets"]


async def _seed_reddit_feeds() -> None:
    async with AsyncSessionLocal() as db:
        for sub in _DEFAULT_SUBREDDITS:
            existing = (await db.execute(select(RedditFeed).where(RedditFeed.subreddit == sub))).scalar_one_or_none()
            if existing is None:
                db.add(RedditFeed(subreddit=sub))
        await db.commit()
    logger.info("Reddit feeds seeded")


async def _periodic_sec_scan():
    # Sleep before the first run so dev-server reloads don't trigger an
    # immediate full S&P 500 scan; use the /api/sec/scan endpoint to test on demand.
    while True:
        await asyncio.sleep(settings.sec_scan_interval_hours * 3600)
        try:
            await scan_all_sp500()
        except Exception:
            logger.exception("Periodic SEC scan failed")


async def _periodic_podcast_poll():
    # Same reload-safety reasoning as _periodic_sec_scan: sleep first, use
    # POST /api/podcasts/{id}/poll to check a feed on demand instead.
    while True:
        await asyncio.sleep(settings.podcast_poll_interval_minutes * 60)
        try:
            await poll_all_feeds()
        except Exception:
            logger.exception("Periodic podcast poll failed")


async def _periodic_reddit_poll():
    while True:
        await asyncio.sleep(settings.reddit_poll_interval_minutes * 60)
        try:
            await poll_all_subreddits()
        except Exception:
            logger.exception("Periodic Reddit poll failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for dev; use alembic in prod)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready")

    await _seed_reddit_feeds()
    tasks = []
    if settings.enable_auto_ingest:
        tasks = [
            asyncio.create_task(_periodic_sec_scan()),
            asyncio.create_task(_periodic_podcast_poll()),
            asyncio.create_task(_periodic_reddit_poll()),
        ]
        logger.info("Auto-ingest enabled: periodic SEC/podcast/Reddit polling started")
    else:
        logger.info("Auto-ingest disabled (ENABLE_AUTO_INGEST not set); use on-demand endpoints")
    yield
    for t in tasks:
        t.cancel()
    await engine.dispose()


app = FastAPI(
    title="NarrativeTracker API",
    description="Financial media intelligence — trending stocks, themes, and investment narratives",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(themes.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(sec.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(podcasts.router, prefix="/api")
app.include_router(reddit.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.database import AsyncSessionLocal
    from app.models.models import Source, Stock, Theme, StockMomentum, ThemeMomentum
    from sqlalchemy import select, func, desc

    async with AsyncSessionLocal() as db:
        total_sources = (await db.execute(select(func.count()).select_from(Source))).scalar()
        processing = (
            await db.execute(
                select(func.count()).select_from(Source).where(Source.status == "processing")
            )
        ).scalar()
        total_stocks = (await db.execute(select(func.count()).select_from(Stock))).scalar()
        total_themes = (await db.execute(select(func.count()).select_from(Theme))).scalar()

        top_stock_row = (
            await db.execute(
                select(Stock.ticker)
                .join(StockMomentum, Stock.id == StockMomentum.stock_id)
                .order_by(desc(StockMomentum.score))
                .limit(1)
            )
        ).scalar_one_or_none()

        top_theme_row = (
            await db.execute(
                select(Theme.name)
                .join(ThemeMomentum, Theme.id == ThemeMomentum.theme_id)
                .order_by(desc(ThemeMomentum.score))
                .limit(1)
            )
        ).scalar_one_or_none()

    return {
        "total_sources": total_sources,
        "sources_processing": processing,
        "total_stocks_tracked": total_stocks,
        "total_themes_tracked": total_themes,
        "top_stock": top_stock_row,
        "top_theme": top_theme_row,
    }
