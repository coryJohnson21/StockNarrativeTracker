import os
import re
import uuid
import asyncio
import logging
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript, Stock, Theme, StockMention, ThemeMention
from app.services.youtube import download_audio, get_video_info, parse_video_metadata
from app.services.transcription import transcribe_audio
from app.services.extraction import extract_from_transcript
from app.services.embeddings import generate_embedding
from app.services.momentum import refresh_stock_momentum, refresh_theme_momentum
from app.services import sec_edgar
from app.services import podcast as podcast_service
from app.config import settings

logger = logging.getLogger(__name__)


async def _get_or_create_stock(db: AsyncSession, ticker: str, company: str) -> Stock:
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if stock is None:
        stock = Stock(ticker=ticker, company_name=company)
        db.add(stock)
        await db.flush()
    elif company and not stock.company_name:
        stock.company_name = company
    return stock


async def _get_or_create_theme(db: AsyncSession, name: str) -> Theme:
    result = await db.execute(select(Theme).where(Theme.name == name))
    theme = result.scalar_one_or_none()
    if theme is None:
        theme = Theme(name=name)
        db.add(theme)
        await db.flush()
    return theme


async def process_youtube_source(source_id: str) -> None:
    """Full pipeline: download → transcribe → extract → embed → score."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            logger.error(f"Source {source_id} not found")
            return

        source.status = "processing"
        source.updated_at = datetime.utcnow()
        await db.commit()

        try:
            # Step 1: Get metadata if not already set
            if not source.title:
                info = await get_video_info(source.url)
                meta = parse_video_metadata(info)
                source.title = meta["title"]
                source.channel = meta["channel"]
                source.duration_seconds = meta["duration_seconds"]
                if meta["published_at"]:
                    try:
                        source.published_at = datetime.strptime(meta["published_at"], "%Y%m%d")
                    except Exception:
                        pass
                await db.commit()

            # Whisper API caps uploads at 25MB; at 64kbps that's ~50 minutes of audio.
            if source.duration_seconds and source.duration_seconds > 50 * 60:
                raise ValueError(
                    f"Video is {source.duration_seconds // 60} minutes long, which exceeds "
                    "the ~50 minute limit for transcription"
                )

            # Step 2: Download audio
            tmp_path = os.path.join(settings.temp_dir, f"{source_id}")
            os.makedirs(settings.temp_dir, exist_ok=True)
            audio_path = await download_audio(source.url, tmp_path)

            # Step 3: Transcribe
            transcript_text = await transcribe_audio(audio_path)

            # Cleanup temp file
            try:
                os.remove(audio_path)
            except Exception:
                pass

            await _store_and_process(db, source, transcript_text)

        except Exception as e:
            logger.exception(f"Error processing source {source_id}: {e}")
            source.status = "failed"
            source.error_message = str(e)[:500]
            source.updated_at = datetime.utcnow()
            await db.commit()


async def process_podcast_episode_source(source_id: str) -> None:
    """Pipeline for a podcast RSS episode: the feed already gives a direct audio
    URL, so this skips yt-dlp/metadata lookup and goes straight to download ->
    transcribe -> extract, same as process_youtube_source from there on."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            logger.error(f"Source {source_id} not found")
            return

        source.status = "processing"
        source.updated_at = datetime.utcnow()
        await db.commit()

        try:
            os.makedirs(settings.temp_dir, exist_ok=True)
            audio_path = os.path.join(settings.temp_dir, f"{source_id}.mp3")
            await podcast_service.download_episode_audio(source.url, audio_path)

            # Whisper API caps uploads at 25MB; bail out before paying for a
            # transcription call that will just fail.
            if os.path.getsize(audio_path) > 25 * 1024 * 1024:
                os.remove(audio_path)
                raise ValueError("Episode audio exceeds the 25MB Whisper upload limit")

            transcript_text = await transcribe_audio(audio_path)

            try:
                os.remove(audio_path)
            except Exception:
                pass

            await _store_and_process(db, source, transcript_text)

        except Exception as e:
            logger.exception(f"Error processing podcast episode source {source_id}: {e}")
            source.status = "failed"
            source.error_message = str(e)[:500]
            source.updated_at = datetime.utcnow()
            await db.commit()


_SUBSTANTIVE_MARKERS = (
    "MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS",
    "RESULTS OF OPERATIONS",
)


def _focus_on_substantive_section(text: str) -> str:
    """10-K/10-Q filings open with a table of contents that lists this same section
    title immediately followed by a page number, so a case-insensitive search for the
    first occurrence lands on the ToC instead of the real section -- handing GPT-4o a
    page index with no real content (which it then hallucinated stock/theme mentions
    to fill in). The actual heading is rendered in ALL CAPS and is followed by prose,
    not a page number, so match case-sensitively and reject ToC-style hits."""
    for marker in _SUBSTANTIVE_MARKERS:
        for match in re.finditer(re.escape(marker), text):
            tail = text[match.end():match.end() + 30].lstrip()
            if tail and not tail[0].isdigit():
                return text[match.start():]
    return text


async def process_sec_filing_source(source_id: str) -> None:
    """Pipeline for SEC EDGAR filings (10-K, 10-Q, 8-K earnings press releases)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            logger.error(f"Source {source_id} not found")
            return

        source.status = "processing"
        source.updated_at = datetime.utcnow()
        await db.commit()

        try:
            async with httpx.AsyncClient() as client:
                transcript_text = await sec_edgar.fetch_filing_text(client, source.url)

            if len(transcript_text) < 200:
                raise ValueError("Filing document text was too short to extract anything useful from")

            transcript_text = _focus_on_substantive_section(transcript_text)
            await _store_and_process(db, source, transcript_text)

        except Exception as e:
            logger.exception(f"Error processing SEC filing source {source_id}: {e}")
            source.status = "failed"
            source.error_message = str(e)[:500]
            source.updated_at = datetime.utcnow()
            await db.commit()


async def process_text_source(source_id: str, transcript_text: str) -> None:
    """Pipeline for pre-supplied transcript text."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            return

        source.status = "processing"
        source.updated_at = datetime.utcnow()
        await db.commit()

        try:
            await _store_and_process(db, source, transcript_text)
        except Exception as e:
            logger.exception(f"Error processing text source {source_id}: {e}")
            source.status = "failed"
            source.error_message = str(e)[:500]
            source.updated_at = datetime.utcnow()
            await db.commit()


async def _store_and_process(db: AsyncSession, source: Source, transcript_text: str) -> None:
    """Extract entities, store transcript, compute momentum."""
    # Step 1: Extract entities
    extraction = await extract_from_transcript(transcript_text, source.title or "")

    # Step 2: Generate embedding
    embedding = await generate_embedding(transcript_text)

    # Step 3: Store transcript
    transcript = Transcript(
        source_id=source.id,
        content=transcript_text,
        embedding=embedding,
    )
    db.add(transcript)
    await db.flush()

    # Step 4: Store stock mentions
    filer_ticker = (source.source_metadata or {}).get("ticker")
    for stock_data in extraction["stocks"]:
        stock = await _get_or_create_stock(
            db, stock_data["ticker"], stock_data.get("company", "")
        )
        mention = StockMention(
            source_id=source.id,
            stock_id=stock.id,
            sentiment_score=stock_data.get("sentiment", 0),
            context=stock_data.get("context", ""),
            mentioned_at=datetime.utcnow(),
            is_self_mention=filer_ticker is not None and stock.ticker == filer_ticker,
        )
        db.add(mention)

    # Step 5: Store theme mentions
    for theme_data in extraction["themes"]:
        theme = await _get_or_create_theme(db, theme_data["name"])
        mention = ThemeMention(
            source_id=source.id,
            theme_id=theme.id,
            sentiment_score=theme_data.get("sentiment", 0),
            context=theme_data.get("context", ""),
            mentioned_at=datetime.utcnow(),
        )
        db.add(mention)

    # Step 6: Update source status
    source.status = "completed"
    source.updated_at = datetime.utcnow()
    if not source.source_metadata:
        source.source_metadata = {}
    source.source_metadata = {**source.source_metadata, "summary": extraction["summary"]}

    await db.commit()

    # Step 7: Refresh momentum scores
    await refresh_stock_momentum(db)
    await refresh_theme_momentum(db)
