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
from app.services.youtube import download_audio, get_video_info, get_captions, parse_video_metadata
from app.services.transcription import transcribe_audio
from app.services.extraction import extract_from_transcript
from app.services.embeddings import generate_embedding
from app.services.momentum import refresh_stock_momentum, refresh_theme_momentum
from app.services import sec_edgar
from app.services import podcast as podcast_service
from app.config import settings

logger = logging.getLogger(__name__)

# At the 16kHz/mono/32kbps encode download_episode_audio uses, 25MB of audio is
# ~109 minutes; this leaves a margin below that for encoding/container overhead and
# imprecise <itunes:duration> metadata, so a feed-reported duration past this point
# fails fast (no download/transcode) instead of discovering the 25MB cap the hard way.
_MAX_PODCAST_DURATION_SECONDS = 100 * 60


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
    """Full pipeline: get metadata -> get transcript (YouTube's own captions when
    available, else download + Whisper) -> extract -> embed -> score."""
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
            # Step 1: Metadata (also carries the caption track listing, so this is
            # always fetched even if title/duration were already set on retry).
            info = await get_video_info(source.url)
            if not source.title:
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

            # Step 2: Prefer YouTube's own captions -- free, and skips downloading
            # audio and calling Whisper entirely when a usable track exists.
            transcript_text = await get_captions(info)

            if transcript_text is None:
                # No usable caption track -- fall back to audio + Whisper, which
                # caps uploads at 25MB (~50 minutes of audio at 64kbps).
                if source.duration_seconds and source.duration_seconds > 50 * 60:
                    raise ValueError(
                        f"Video is {source.duration_seconds // 60} minutes long, which exceeds "
                        "the ~50 minute limit for transcription and has no usable caption track"
                    )

                tmp_path = os.path.join(settings.temp_dir, f"{source_id}")
                os.makedirs(settings.temp_dir, exist_ok=True)
                audio_path = await download_audio(source.url, tmp_path)
                transcript_text = await transcribe_audio(audio_path)
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
            if source.duration_seconds and source.duration_seconds > _MAX_PODCAST_DURATION_SECONDS:
                raise ValueError(
                    f"Episode is {source.duration_seconds // 60} minutes long, which exceeds "
                    "the ~100 minute limit for transcription"
                )

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
    # Step 1: Extract entities, steered toward the user's currently tracked themes
    tracked_result = await db.execute(select(Theme.name).where(Theme.is_tracked.is_(True)))
    tracked_themes = [name for (name,) in tracked_result.all()]
    extraction = await extract_from_transcript(transcript_text, source.title or "", known_themes=tracked_themes)

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
    source.source_metadata = {
        **source.source_metadata,
        "summary": extraction["summary"],
        "calls": extraction.get("calls", []),
    }

    await db.commit()

    # Step 7: Refresh momentum scores
    await refresh_stock_momentum(db)
    await refresh_theme_momentum(db)
