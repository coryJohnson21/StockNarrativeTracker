import os
import re
import uuid
import asyncio
import logging
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal
from app.models.models import Source, Transcript, Stock, Theme, StockMention, ThemeMention, StockCall
from app.services.youtube import download_audio, get_video_info, get_captions, parse_video_metadata
from app.services.transcription import transcribe_audio
from app.services.extraction import extract_from_transcript, extract_filing_details
from app.services.symbols import resolve_symbol
from app.services.embeddings import generate_embedding
from app.services.narratives import embed_and_score_mentions
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
        # Check the symbol once, when the row is first created. GPT regularly emits
        # a company name ("LILY") or an acronym that is not a company at all ("FERC",
        # "AWS") in the ticker slot; recording the verdict here keeps those out of
        # trending and price refreshes instead of leaving a permanently unpriceable
        # row behind. A failed lookup leaves it NULL to be retried later.
        verdict = await resolve_symbol(ticker)
        if verdict is not None:
            stock.symbol_status = verdict["verdict"]
            stock.symbol_checked_at = datetime.utcnow()
            if verdict["verdict"] != "ok":
                logger.info("ticker %s did not resolve (%s)", ticker, verdict["verdict"])
        db.add(stock)
        await db.flush()
    elif company and not stock.company_name:
        stock.company_name = company
    return stock


async def _store_calls(db: AsyncSession, source: Source, calls: list[dict], called_at: datetime) -> int:
    """Persist a source's explicit recommendations, replacing any from a previous
    processing run of the same source."""
    await db.execute(delete(StockCall).where(StockCall.source_id == source.id))
    stored = 0
    for c in calls:
        stock = await _get_or_create_stock(db, c["ticker"], "")
        db.add(
            StockCall(
                source_id=source.id,
                stock_id=stock.id,
                call=c["call"],
                price_target=c.get("price_target"),
                reasoning=c.get("reasoning") or None,
                called_at=called_at,
            )
        )
        stored += 1
    return stored


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
            # Fill whatever the poller didn't know. Feed-created sources arrive with
            # a title but no duration, and the Whisper cap below needs the duration.
            meta = parse_video_metadata(info)
            source.title = source.title or meta["title"]
            source.channel = source.channel or meta["channel"]
            source.duration_seconds = source.duration_seconds or meta["duration_seconds"]
            if not source.published_at and meta["published_at"]:
                try:
                    source.published_at = datetime.strptime(meta["published_at"], "%Y%m%d")
                except Exception:
                    pass
            await db.commit()

            # Step 2: Prefer YouTube's own captions -- free, and skips downloading
            # audio and calling Whisper entirely when a usable track exists.
            transcript_text = await get_captions(info)

            if transcript_text is None:
                # No usable caption track (or YouTube is rate-limiting captions) --
                # fall back to audio + Whisper. At the 16kHz/mono/32kbps encode
                # download_audio uses, Whisper's 25MB cap is ~100 minutes.
                if source.duration_seconds and source.duration_seconds > _MAX_PODCAST_DURATION_SECONDS:
                    raise ValueError(
                        f"Video is {source.duration_seconds // 60} minutes long, which exceeds "
                        f"the ~{_MAX_PODCAST_DURATION_SECONDS // 60} minute transcription limit, and has no usable caption track"
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

    # Step 1b: Filing/earnings sources also get a dedicated period/teaser/earnings
    # summary -- the generic transcript summary above is structured for financial
    # media discussions, not a single-company earnings report.
    filing_details = None
    if source.type in sec_edgar.TRACKED_FORMS:
        filing_details = await extract_filing_details(transcript_text, source.title or "")

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

    # Step 4: Store stock mentions. Timestamp them by when the source was published,
    # not when we happened to ingest it -- otherwise a backfilled filing or an old
    # podcast episode shows up as a mention spike "today" and corrupts every
    # time-windowed statistic downstream.
    mentioned_at = source.published_at or source.created_at or datetime.utcnow()
    filer_ticker = (source.source_metadata or {}).get("ticker")
    new_mentions: list[StockMention] = []
    for stock_data in extraction["stocks"]:
        stock = await _get_or_create_stock(
            db, stock_data["ticker"], stock_data.get("company", "")
        )
        mention = StockMention(
            source_id=source.id,
            stock_id=stock.id,
            sentiment_score=stock_data.get("sentiment", 0),
            context=stock_data.get("context", ""),
            mentioned_at=mentioned_at,
            is_self_mention=filer_ticker is not None and stock.ticker == filer_ticker,
        )
        db.add(mention)
        new_mentions.append(mention)
    await db.flush()

    # Step 4a: Embed each mention's context and score how new it is. Best-effort:
    # a failed embedding call shouldn't fail the whole source.
    try:
        await embed_and_score_mentions(db, new_mentions)
    except Exception:
        logger.exception("Mention embedding failed for source %s; continuing without novelty", source.id)

    # Step 4b: Store explicit recommendations -- from media only. A company's own
    # filing isn't a recommendation, and GPT will occasionally read "we expect
    # growth" in a 10-Q as a buy call, which would then score the company as a
    # "channel" in the reliability table.
    if source.type not in sec_edgar.TRACKED_FORMS:
        await _store_calls(db, source, extraction.get("calls", []), mentioned_at)

    # Step 5: Store theme mentions
    for theme_data in extraction["themes"]:
        theme = await _get_or_create_theme(db, theme_data["name"])
        mention = ThemeMention(
            source_id=source.id,
            theme_id=theme.id,
            sentiment_score=theme_data.get("sentiment", 0),
            context=theme_data.get("context", ""),
            mentioned_at=mentioned_at,
        )
        db.add(mention)

    # Step 6: Update source status
    source.status = "completed"
    source.error_message = None
    source.updated_at = datetime.utcnow()
    if not source.source_metadata:
        source.source_metadata = {}
    source.source_metadata = {
        **source.source_metadata,
        "summary": extraction["summary"],
        "calls": extraction.get("calls", []),
    }
    if filing_details:
        source.source_metadata["filing_details_version"] = 3
        source.source_metadata["period"] = filing_details["period"]
        source.source_metadata["teaser"] = filing_details["teaser"]
        source.source_metadata["filing_summary"] = filing_details["summary"]
        source.source_metadata["revenue"] = filing_details["revenue"]
        source.source_metadata["revenue_yoy_pct"] = filing_details["revenue_yoy_pct"]
        source.source_metadata["revenue_qoq_pct"] = filing_details["revenue_qoq_pct"]
        source.source_metadata["eps"] = filing_details["eps"]
        source.source_metadata["eps_yoy_pct"] = filing_details["eps_yoy_pct"]
        source.source_metadata["eps_qoq_pct"] = filing_details["eps_qoq_pct"]
        source.source_metadata["net_income"] = filing_details["net_income"]
        source.source_metadata["guidance_direction"] = filing_details["guidance_direction"]
        source.source_metadata["capital_returns"] = filing_details["capital_returns"]
        source.source_metadata["strategic_actions"] = filing_details["strategic_actions"]

    await db.commit()

    # Step 7: Refresh momentum scores
    await refresh_stock_momentum(db)
    await refresh_theme_momentum(db)
