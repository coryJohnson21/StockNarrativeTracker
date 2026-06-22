import asyncio
import re
from typing import List
import openai
from app.config import settings

_RETRY_SECONDS_RE = re.compile(r"try again in ([\d.]+)s")


async def generate_embedding(text: str) -> List[float]:
    """Generate a 1536-dim embedding via OpenAI text-embedding-3-small."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    truncated = text[:8000]

    max_retries = 8
    for attempt in range(max_retries):
        try:
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=truncated,
            )
            return response.data[0].embedding
        except openai.RateLimitError as e:
            match = _RETRY_SECONDS_RE.search(str(e))
            wait = float(match.group(1)) + 1 if match else 2 ** attempt
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(wait)
