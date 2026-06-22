import asyncio
import json
import re
import openai
from app.config import settings

_RETRY_SECONDS_RE = re.compile(r"try again in ([\d.]+)s")


async def _create_with_retry(client: openai.AsyncOpenAI, max_retries: int = 8, **kwargs):
    """gpt-4o on this account is capped at a low tokens-per-minute tier, so bulk
    backfills routinely hit 429s. Retry using the wait time OpenAI tells us to use."""
    for attempt in range(max_retries):
        try:
            return await client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            match = _RETRY_SECONDS_RE.search(str(e))
            wait = float(match.group(1)) + 1 if match else 2 ** attempt
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(wait)

EXTRACTION_PROMPT = """You are a financial analyst AI. Analyze this financial media transcript and extract investment-relevant information.

Source title: {title}

Return a JSON object with EXACTLY this structure (no extra fields):
{{
  "stocks": [
    {{"ticker": "NVDA", "company": "NVIDIA Corporation", "sentiment": 85, "context": "brief context quote under 200 chars"}}
  ],
  "themes": [
    {{"name": "Artificial Intelligence", "sentiment": 75, "context": "brief context under 200 chars"}}
  ],
  "summary": "2-3 sentence investment-focused summary highlighting key bullish/bearish calls"
}}

Rules:
- Sentiment: -100 (extremely bearish) to +100 (extremely bullish), 0 = neutral
- Only include stocks explicitly mentioned; infer tickers when company name is clear
- Normalize theme names to standard categories: Artificial Intelligence, Machine Learning, Cloud Computing, Semiconductors, Nuclear Energy, Renewable Energy, Cybersecurity, Digital Payments, Fintech, Biotechnology, Pharmaceutical, Defense & Aerospace, Real Estate, Inflation & Macro, Interest Rates, Federal Reserve Policy, Supply Chain, Data Centers, Electric Vehicles, Autonomous Driving, Consumer Discretionary, Energy Transition, Commodities
- Include a theme even if mentioned briefly; sentiment reflects overall tone
- Summary must focus on specific investment theses, not general topics

Transcript:
{transcript}"""


async def extract_from_transcript(transcript: str, title: str = "") -> dict:
    """Use GPT-4o to extract stocks, themes, and generate summary."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    truncated = transcript[:12000] if len(transcript) > 12000 else transcript

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    title=title or "Financial Media Content",
                    transcript=truncated,
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)

    # Validate and sanitize
    stocks = []
    for s in result.get("stocks", []):
        if isinstance(s, dict) and s.get("ticker"):
            stocks.append(
                {
                    "ticker": str(s["ticker"]).upper().strip()[:10],
                    "company": str(s.get("company", ""))[:200],
                    "sentiment": float(max(-100, min(100, s.get("sentiment", 0)))),
                    "context": str(s.get("context", ""))[:300],
                }
            )

    themes = []
    for t in result.get("themes", []):
        if isinstance(t, dict) and t.get("name"):
            themes.append(
                {
                    "name": str(t["name"])[:100],
                    "sentiment": float(max(-100, min(100, t.get("sentiment", 0)))),
                    "context": str(t.get("context", ""))[:300],
                }
            )

    return {
        "stocks": stocks,
        "themes": themes,
        "summary": str(result.get("summary", ""))[:1000],
    }


async def condense_company_description(company: str, business_summary: str) -> str:
    """Condense Yahoo Finance's long business summary into a 4-sentence description."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Condense this company description of {company} into EXACTLY 4 sentences, "
                    "covering what the company does, its main products/segments, and its market "
                    f"position. Plain prose, no bullet points.\n\n{business_summary[:4000]}"
                ),
            }
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


async def generate_narrative_summary(
    ticker: str,
    company: str,
    filing_sentiment: float,
    filing_contexts: list[str],
    media_sentiment: float,
    media_contexts: list[str],
) -> str:
    """Synthesize what's actually being said about a stock across filings vs. media,
    and explain whether it reads as a bullish or bearish signal, for the stock landing page."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    filing_block = "\n".join(f"- {c}" for c in filing_contexts) or "(no filing mentions yet)"
    media_block = "\n".join(f"- {c}" for c in media_contexts) or "(no media mentions yet)"

    prompt = (
        f"You are a financial analyst. Below are excerpts mentioning {company} ({ticker}) "
        f"pulled from two sources: SEC filings/earnings releases (avg sentiment {filing_sentiment:.0f} "
        f"on a -100 to +100 scale) and financial media coverage (avg sentiment {media_sentiment:.0f}).\n\n"
        f"Filing/earnings excerpts:\n{filing_block}\n\n"
        f"Media excerpts:\n{media_block}\n\n"
        "In EXACTLY 3-4 sentences, summarize what is actually being said about this company "
        "across these sources, and explain whether the narrative reads as a bullish or bearish "
        "signal and why. Be specific and reference the actual claims/themes above rather than "
        "speaking generically. Plain prose, no bullet points."
    )

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


async def generate_theme_description(theme_name: str) -> str:
    """Generate a 2-3 sentence definition of an investment theme for the theme landing page."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": (
                    f"In EXACTLY 2-3 sentences, define the investment theme '{theme_name}' for "
                    "a financial analyst audience: what it covers, why investors track it, and "
                    "what kinds of companies are exposed to it. Plain prose, no bullet points."
                ),
            }
        ],
        temperature=0.2,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()
