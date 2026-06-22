import openai
from app.config import settings


async def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file using OpenAI Whisper API."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

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
