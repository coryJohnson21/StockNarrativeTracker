import asyncio
import re
from typing import List
import openai
from app.config import settings

_RETRY_SECONDS_RE = re.compile(r"try again in ([\d.]+)s")


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
_BATCH = 100


async def _create_with_retry(client: openai.AsyncOpenAI, inputs: List[str]) -> List[List[float]]:
    max_retries = 8
    for attempt in range(max_retries):
        try:
            response = await client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
            return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]
        except openai.RateLimitError as e:
            match = _RETRY_SECONDS_RE.search(str(e))
            wait = float(match.group(1)) + 1 if match else 2 ** attempt
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(wait)
    return []


async def generate_embedding(text: str) -> List[float]:
    """Generate a 1536-dim embedding via OpenAI text-embedding-3-small."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    return (await _create_with_retry(client, [text[:8000]]))[0]


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Batch variant for many short texts (mention contexts); preserves order."""
    if not texts:
        return []
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    out: List[List[float]] = []
    for i in range(0, len(texts), _BATCH):
        out.extend(await _create_with_retry(client, [t[:8000] for t in texts[i:i + _BATCH]]))
    return out
