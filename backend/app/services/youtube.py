import asyncio
import os
from typing import Optional
import yt_dlp
from app.config import settings


async def get_video_info(url: str) -> dict:
    """Fetch metadata without downloading."""
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    return await loop.run_in_executor(None, _extract)


async def download_audio(url: str, output_path: str) -> str:
    """Download audio from YouTube URL, return path to mp3 file."""
    os.makedirs(settings.temp_dir, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio[abr<=64]/bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }
        ],
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
