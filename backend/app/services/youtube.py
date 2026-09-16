import asyncio
import json
import logging
import os
import re
import time
from typing import Optional
import feedparser
import httpx
import yt_dlp
from app.config import settings

# Order of preference when picking an English caption track. "en-orig" is yt-dlp's
# label for the original-language auto-caption track on videos where YouTube also
# offers translated auto-captions.
_PREFERRED_CAPTION_LANGS = ("en", "en-US", "en-GB", "en-orig")

_VTT_TAG_RE = re.compile(r"<[^>]+>")
_VTT_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}")

# Below this many characters, treat a caption track as unusable (e.g. a music-only
# auto-caption track that's just a handful of "[Music]" cues) and fall back to Whisper.
_MIN_CAPTION_LENGTH = 200


async def get_video_info(url: str) -> dict:
    """Fetch metadata without downloading."""
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    return await loop.run_in_executor(None, _extract)


def _parse_vtt(raw: str) -> str:
    """Strip WebVTT to plain text. Auto-generated tracks render as a scrolling
    2-line window where each cue repeats part of the previous one -- skipping exact
    consecutive duplicates handles that without needing real cue-diffing."""
    lines_out = []
    prev = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE", "STYLE")):
            continue
        if _VTT_TIMESTAMP_RE.match(line) or line.isdigit():
            continue
        text = _VTT_TAG_RE.sub("", line).strip()
        if not text or text == prev:
            continue
        lines_out.append(text)
        prev = text
    return " ".join(lines_out)


def _parse_json3(raw: str) -> str:
    """Parse YouTube's json3 caption format -- a flat list of timed word/phrase
    segments, not the rolling display window vtt uses, so no dedup needed."""
    data = json.loads(raw)
    parts = []
    for event in data.get("events", []):
        for seg in event.get("segs", []):
            text = seg.get("utf8", "")
            if text and text != "\n":
                parts.append(text)
    return "".join(parts).replace("\n", " ").strip()


async def get_captions(info: dict) -> Optional[str]:
    """Fetch YouTube's own caption track as plain text -- manually-uploaded
    preferred, auto-generated as fallback -- so transcription is free instead of
    a Whisper call. Returns None if no usable English track exists, so the caller
    can fall back to downloading audio and transcribing it."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    track, is_auto = None, False
    for lang in _PREFERRED_CAPTION_LANGS:
        if lang in manual:
            track = manual[lang]
            break
    if track is None:
        for lang in _PREFERRED_CAPTION_LANGS:
            if lang in auto:
                track = auto[lang]
                is_auto = True
                break
    if not track:
        return None

    # json3 gives clean, non-overlapping segments for auto-captions; vtt is fine
    # (and simpler) for manually-uploaded tracks, which don't have that artifact.
    fmt_order = ("json3", "vtt") if is_auto else ("vtt", "json3")
    entry = next((f for fmt in fmt_order for f in track if f.get("ext") == fmt), None) or track[0]

    raw = await _fetch_caption_track(entry["url"])
    if raw is None:
        logging.getLogger(__name__).warning(
            "YouTube kept rate-limiting the caption track for %s; falling back to audio transcription", entry["url"][:80]
        )
        return None
    text = _parse_json3(raw) if entry.get("ext") == "json3" else _parse_vtt(raw)
    return text if len(text) >= _MIN_CAPTION_LENGTH else None


# YouTube's timedtext endpoint rate-limits an IP with 429s once it has served a
# couple dozen tracks in a short span, and the block can persist for a while.
# Space requests out and back off a few times; if it still refuses, return None so
# the caller falls back to downloading audio and transcribing it rather than
# failing the video outright.
_CAPTION_MIN_GAP_SECONDS = 3.0
_CAPTION_RETRY_WAITS = (10, 30, 60)
_caption_lock = asyncio.Lock()
_last_caption_fetch = 0.0


async def _fetch_caption_track(url: str) -> Optional[str]:
    global _last_caption_fetch
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for wait in (0,) + _CAPTION_RETRY_WAITS:
            if wait:
                await asyncio.sleep(wait)
            async with _caption_lock:
                gap = _CAPTION_MIN_GAP_SECONDS - (time.monotonic() - _last_caption_fetch)
                if gap > 0:
                    await asyncio.sleep(gap)
                response = await client.get(url)
                _last_caption_fetch = time.monotonic()
            if response.status_code == 429:
                continue
            response.raise_for_status()
            return response.text
    return None


async def download_audio(url: str, output_path: str) -> str:
    """Download a YouTube video's audio as 16kHz mono 32kbps mp3 -- the same encode
    podcast episodes get, so ~100 minutes fits under Whisper's 25MB upload cap
    (Whisper resamples to 16kHz mono internally anyway)."""
    os.makedirs(settings.temp_dir, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio[abr<=64]/bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "32",
            }
        ],
        "postprocessor_args": {"FFmpegExtractAudio": ["-ac", "1", "-ar", "16000"]},
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    await loop.run_in_executor(None, _download)

    mp3_path = output_path + ".mp3"
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found after download: {mp3_path}")

    return mp3_path


def parse_video_metadata(info: dict) -> dict:
    """Extract relevant fields from yt-dlp info dict."""
    return {
        "title": info.get("title"),
        "channel": info.get("uploader") or info.get("channel"),
        "duration_seconds": info.get("duration"),
        "published_at": info.get("upload_date"),  # YYYYMMDD string
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "description": (info.get("description") or "")[:500],
    }


async def resolve_channel(url_or_handle: str) -> Optional[dict]:
    """Resolve a YouTube channel URL/@handle, OR a specific playlist URL within a
    channel, to its uploads/playlist RSS feed URL -- so a user can subscribe to a
    whole channel, or to just one show on a shared network channel (e.g. Bloomberg
    Podcasts' "Odd Lots" playlist instead of every Bloomberg Podcasts upload), the
    same way they'd subscribe to a podcast RSS feed. Returns None if the input
    doesn't resolve to either."""
    target = url_or_handle.strip()
    if not target:
        return None
    if not target.startswith("http"):
        target = f"https://www.youtube.com/{target.lstrip('/')}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
    except Exception:
        return None

    raw_id = str(info.get("id") or "")
    if raw_id.startswith(("PL", "UU", "OL", "FL")):
        # A specific playlist, not a whole channel -- e.g. one show among many
        # on a shared network channel.
        title = info.get("title") or info.get("channel")
        return {
            "channel_id": raw_id,
            "title": title,
            "feed_url": f"https://www.youtube.com/feeds/videos.xml?playlist_id={raw_id}",
        }

    channel_id = info.get("channel_id") or (raw_id if raw_id.startswith("UC") else None)
    title = info.get("channel") or info.get("title") or info.get("uploader")
    if not channel_id:
        return None

    return {
        "channel_id": channel_id,
        "title": title,
        "feed_url": f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
    }


async def parse_channel_feed(feed_url: str) -> list[dict]:
    """Parse a YouTube channel's uploads Atom feed, returning videos newest-first
    with their watch URL, title, and publish date. No duration here -- YouTube's feed
    doesn't include it; process_youtube_source backfills real duration from video
    metadata during processing, same as one-off YouTube ingestion already does."""
    loop = asyncio.get_event_loop()
    parsed = await loop.run_in_executor(None, feedparser.parse, feed_url)

    videos = []
    for entry in parsed.entries:
        video_url = entry.get("link")
        if not video_url or "/shorts/" in video_url:
            # Shorts are a few seconds of content -- not worth a poll slot, and
            # rarely (if ever) carry substantive financial commentary.
            continue
        videos.append(
            {
                "url": video_url,
                "title": entry.get("title", "Untitled video"),
                "published_at": entry.get("published_parsed"),
                "duration_seconds": None,
            }
        )
    return videos
