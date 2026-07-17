import asyncio
import os
import feedparser
import httpx
from app.config import settings

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


async def search_podcasts(query: str, limit: int = 10) -> list[dict]:
    """Look up podcasts by name via Apple's iTunes Search API (free, no key required)
    and return each result's actual RSS feed URL, so the user can subscribe by show
    name instead of hunting down the raw feed URL themselves."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            ITUNES_SEARCH_URL,
            params={"term": query, "media": "podcast", "entity": "podcast", "limit": limit},
        )
        response.raise_for_status()
        data = response.json()

    results = []
    for entry in data.get("results", []):
        feed_url = entry.get("feedUrl")
        if not feed_url:
            # Some iTunes entries lack a feed URL (delisted/podcast-only-on-Apple) --
            # useless for RSS-based subscription, so skip rather than show a dead end.
            continue
        results.append(
            {
                "title": entry.get("collectionName") or entry.get("trackName") or "Untitled podcast",
                "publisher": entry.get("artistName"),
                "artwork_url": entry.get("artworkUrl100"),
                "feed_url": feed_url,
            }
        )
    return results


def _parse_itunes_duration(raw: str) -> int | None:
    """Parse an <itunes:duration> value, which publishers inconsistently format as
    plain seconds ("5400"), "MM:SS", or "HH:MM:SS"."""
    raw = raw.strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    if not all(p.isdigit() for p in parts):
        return None
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    return None


async def parse_feed(feed_url: str) -> list[dict]:
    """Fetch and parse a podcast RSS feed, returning episodes newest-first with
    their audio enclosure URL, title, publish date, and duration (when the feed
    provides <itunes:duration>, which most podcast feeds do)."""
    loop = asyncio.get_event_loop()
    parsed = await loop.run_in_executor(None, feedparser.parse, feed_url)

    episodes = []
    for entry in parsed.entries:
        audio_url = None
        for link in entry.get("links", []):
            if link.get("type", "").startswith("audio/") or link.get("rel") == "enclosure":
                audio_url = link.get("href")
                break
        if not audio_url:
            continue

        duration_seconds = None
        raw_duration = entry.get("itunes_duration")
        if raw_duration:
            duration_seconds = _parse_itunes_duration(str(raw_duration))

        episodes.append(
            {
                "url": audio_url,
                "title": entry.get("title", "Untitled episode"),
                "published_at": entry.get("published_parsed"),
                "duration_seconds": duration_seconds,
            }
        )
    return episodes


async def download_episode_audio(audio_url: str, output_path: str) -> str:
    """Download a podcast episode's audio enclosure, then transcode to a low-bitrate
    mono mp3 with ffmpeg. Publishers' original enclosures (often 128kbps+ stereo)
    routinely blow past Whisper's 25MB upload limit -- 16kHz mono 32kbps is well
    within what Whisper needs for speech (it resamples everything to 16kHz mono
    internally anyway) and roughly doubles the episode length that fits in 25MB
    versus a naive 64kbps encode (~55 min -> ~109 min)."""
    os.makedirs(settings.temp_dir, exist_ok=True)
    raw_path = output_path + ".raw"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        async with client.stream("GET", audio_url) as response:
            response.raise_for_status()
            with open(raw_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", raw_path, "-vn", "-ac", "1", "-ar", "16000", "-ab", "32k", output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    try:
        os.remove(raw_path)
    except OSError:
        pass

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg transcode failed: {stderr.decode(errors='ignore')[-500:]}")

    return output_path
