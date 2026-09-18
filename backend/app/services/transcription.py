import openai
from app.config import settings


# A ~100-minute file at the 32kbps encode normally transcribes in a couple of
# minutes. The SDK default (10 minutes, retried twice) let a single hung request
# stall an ingest for half an hour; but the audio endpoint also drops uploads
# with a bare "Connection error" often enough that one retry loses real videos.
_TRANSCRIBE_TIMEOUT_SECONDS = 300.0
_TRANSCRIBE_RETRIES = 3


async def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file using OpenAI Whisper API."""
    client = openai.AsyncOpenAI(
        api_key=settings.openai_api_key, timeout=_TRANSCRIBE_TIMEOUT_SECONDS, max_retries=_TRANSCRIBE_RETRIES
    )

    with open(audio_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )

    return transcript


async def transcribe_from_text(text: str) -> str:
    """Pass-through for pre-transcribed text."""
    return text.strip()
