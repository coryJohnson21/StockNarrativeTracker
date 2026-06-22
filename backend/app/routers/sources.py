from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.database import get_db
from app.models.models import Source, Transcript
from app.schemas.schemas import SourceResponse, SourceListResponse

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
async def list_sources(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Source).order_by(desc(Source.created_at))
    if status:
        q = q.where(Source.status == status)

    count_q = select(func.count()).select_from(Source)
    if status:
        count_q = count_q.where(Source.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar()

    result = await db.execute(q.offset(offset).limit(limit))
    sources = result.scalars().all()

    return {"sources": sources, "total": total}


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/{source_id}/transcript")
async def get_transcript(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transcript).where(Transcript.source_id == source_id)
    )
    transcript = result.scalar_one_or_none()
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {
        "source_id": source_id,
        "content": transcript.content,
        "language": transcript.language,
        "created_at": transcript.created_at,
    }


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
