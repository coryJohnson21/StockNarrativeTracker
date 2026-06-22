import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Source
from app.schemas.schemas import YouTubeIngestRequest, TranscriptUploadRequest, SourceResponse
from app.tasks.processing import process_youtube_source, process_text_source

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/youtube", response_model=SourceResponse)
async def ingest_youtube(
    request: YouTubeIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a YouTube URL for ingestion and processing."""
    # Deduplicate by URL
    existing = await db.execute(select(Source).where(Source.url == request.url))
    existing_source = existing.scalar_one_or_none()
    if existing_source and existing_source.status in ("completed", "processing"):
        return existing_source

    source = Source(
        type="youtube",
        url=request.url,
        status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    source_id = str(source.id)
    background_tasks.add_task(process_youtube_source, source_id)

    return source


@router.post("/transcript", response_model=SourceResponse)
async def ingest_transcript(
    request: TranscriptUploadRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Upload a pre-transcribed text for AI processing."""
    source = Source(
        type=request.source_type,
        title=request.title,
        channel=request.channel,
        published_at=request.published_at,
        status="pending",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    source_id = str(source.id)
    content = request.content
    background_tasks.add_task(process_text_source, source_id, content)

    return source
