import asyncio
import os
import feedparser
import httpx
from app.config import settings


async def parse_feed(feed_url: str) -> list[dict]:
    """Fetch and parse a podcast RSS feed, returning episodes newest-first with
    their audio enclosure URL, title, and publish date."""
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

        episodes.append(
            {
                "audio_url": audio_url,
                "title": entry.get("title", "Untitled episode"),
                "published_at": entry.get("published_parsed"),
            }
        )
    return episodes


async def download_episode_audio(audio_url: str, output_path: str) -> str:
    """Download a podcast episode's audio enclosure, then transcode to 64kbps mp3
    with ffmpeg — same bitrate cap the YouTube pipeline applies via yt-dlp, since
    publishers' original enclosures (often 128kbps+) routinely blow past Whisper's
    25MB upload limit on anything longer than ~25 minutes."""
    os.makedirs(settings.temp_dir, exist_ok=True)
    raw_path = output_path + ".raw"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        async with client.stream("GET", audio_url) as response:
            response.raise_for_status()
            with open(raw_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", raw_path, "-vn", "-ar", "44100", "-ab", "64k", output_path,
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
