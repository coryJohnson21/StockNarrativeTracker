import asyncio
import json
import re
import openai
from app.config import settings

_RETRY_SECONDS_RE = re.compile(r"try again in ([\d.]+)s")

_TICKER_ALIASES: dict[str, str] = {
    "J&J": "JNJ",
    "BRK.A": "BRK-A",
    "BRK.B": "BRK-B",
    "BRK/A": "BRK-A",
    "BRK/B": "BRK-B",
    "BRKA": "BRK-A",
    "BRKB": "BRK-B",
    # Block Inc changed its ticker from SQ to XYZ -- normalize the old symbol so
    # stray extractions don't re-split the company back into two stock rows.
    "SQ": "XYZ",
    "SQUARE": "XYZ",
    # SpaceX is public now; HXSCL was never a real symbol (SK Hynix's actual
    # US OTC ticker is SKHY). SPCE is deliberately NOT aliased here -- that's
    # Virgin Galactic's real ticker, a different company.
    "SPACEX": "SPCX",
    "HXSCL": "SKHY",
    # NextEra Energy and its wholly-owned utility subsidiary trade under one
    # ticker; "NEX" isn't real. TerraWulf's actual ticker is WULF, not TWL.
    "NEX": "NEE",
    "FPL": "NEE",
    "TWL": "WULF",
}

_INDEX_RE = re.compile(
    r"S&P|DOW\s*JONES|NASDAQ\s*COMPOSITE|NYSE\s*COMPOSITE|RUSSELL\s*\d|^VIX$",
    re.IGNORECASE,
)

_VALID_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{0,8}(-[A-Z])?$")


def _normalize_ticker(raw: str) -> str | None:
    """Normalize a GPT-extracted ticker to a clean Yahoo Finance-compatible symbol.
    Returns None if the string is not a valid ticker (index, has spaces, etc.)."""
    t = raw.upper().strip()

    # Check known aliases first (before any other transforms)
    if t in _TICKER_ALIASES:
        return _TICKER_ALIASES[t]

    # Reject indexes (S&P 500, Dow Jones, etc.)
    if _INDEX_RE.search(t):
        return None

    # Reject anything with a space — GPT sometimes emits "SK HYNIX" or "S&P 500"
    if " " in t:
        return None

    # Normalize share-class dot notation to dash: BRK.A → BRK-A
    t = re.sub(r"\.([A-Z])$", r"-\1", t)

    # Must match a plausible ticker pattern after normalization
    if not _VALID_TICKER_RE.match(t):
        return None

    return t


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

EXTRACTION_PROMPT = """You are a senior financial analyst reviewing a financial media transcript. Your job is thorough extraction — completeness matters more than brevity.

Source: {title}

Step 1 — Before writing any JSON, read the full transcript and make a mental list of EVERY company or stock ticker mentioned anywhere, even once in passing.

Step 2 — Return a JSON object with EXACTLY this structure (no extra fields):
{{
  "stocks": [
    {{
      "ticker": "NVDA",
      "company": "NVIDIA Corporation",
      "sentiment": 75,
      "context": "1-2 sentence paraphrase of what was specifically said about this stock"
    }}
  ],
  "themes": [
    {{
      "name": "Artificial Intelligence",
      "sentiment": 70,
      "context": "1-2 sentence paraphrase of the key point made about this theme"
    }}
  ],
  "calls": [
    {{
      "ticker": "NVDA",
      "call": "buy",
      "price_target": null,
      "reasoning": "1-2 sentence explanation of the investment thesis or catalyst cited"
    }}
  ],
  "summary": "12-sentence summary following the structure below"
}}

STOCKS FIELD — this is the most important field. Rules:
  - Include every single company or ticker named in the transcript, regardless of how briefly
  - Examples of what to include: stocks mentioned as gaining/falling, index components named, stocks used as comparisons, earnings reports discussed, analyst mentions, portfolio holdings named
  - Infer tickers from company names: "Alphabet" → GOOGL, "Meta" → META, "Advanced Micro" or "AMD" → AMD, "Micron" → MU, "FedEx" → FDX, "IBM" → IBM, "Tesla" → TSLA
  - A stock appearing 3 times and one appearing once both belong in the array
  - Do NOT limit to the "main" story — capture everything

TICKER FORMAT — always use the official US exchange ticker symbol:
  - Johnson & Johnson / J&J → JNJ
  - Berkshire Hathaway Class A → BRK-A (use dash, never dot: NOT BRK.A)
  - Berkshire Hathaway Class B → BRK-B (use dash, never dot: NOT BRK.B)
  - Alphabet → GOOGL, Meta → META, NextEra Energy → NEE, Block (formerly Square) → XYZ, SpaceX → SPCX, SK Hynix → SKHY
  - For foreign companies listed in the US as ADRs, use the ADR ticker (e.g. Toyota → TM, Alibaba → BABA, ASML → ASML)
  - For foreign companies with no US ADR/OTC ticker, still include them but note in company field that they are foreign-listed, and omit the ticker rather than guessing one
  - NEVER use spaces in a ticker — "SK HYNIX" is wrong, use SKHY
  - NEVER include stock market indexes as stocks (S&P 500, Dow Jones, Nasdaq Composite, Russell 2000 are indexes, not stocks — omit them entirely)
  - NEVER include ETFs or mutual funds as individual stocks unless the transcript is specifically discussing the ETF itself
  - Genuinely private companies (OpenAI, Anthropic, etc.) should still be included — just use a reasonable ticker abbreviation (OPENAI, ANTHROPIC). Don't assume a company is private without being sure -- SpaceX, for example, is public (SPCX).

SUMMARY — write exactly 12 sentences in this order:
  Sentences 1-2: Overall market backdrop and macro environment discussed in this episode
  Sentences 3-4: Major investment themes and sectors that received significant airtime
  Sentences 5-7: Key bullish stock calls and the specific reasoning or catalysts cited for each
  Sentences 8-9: Bearish concerns, risks flagged, or stocks explicitly cautioned against
  Sentences 10-11: Notable forward-looking predictions — price targets, earnings estimates, Fed/rate calls, specific timelines
  Sentence 12: One-sentence takeaway on the overall investment tone and actionability of this episode

SENTIMENT SCALE:
  +80 to +100 — Explicit strong buy, extremely bullish thesis
  +50 to +79  — Moderately bullish, positive coverage with clear upside cited
  +20 to +49  — Mildly positive, mentioned favorably
  -19 to +19  — Neutral, informational mention with no directional bias
  -20 to -49  — Mildly negative, concerns raised
  -50 to -79  — Moderately bearish, negative thesis
  -80 to -100 — Explicit sell / strongly bearish

CALLS RULES:
  - Only include explicit recommendations (buy, sell, hold, avoid, watch)
  - "call" must be exactly one of: buy, sell, hold, avoid, watch
  - "price_target" is a number or null — only populate if a specific dollar figure was stated
  - Return empty array if no explicit calls were made

THEMES: normalize to one of these tracked themes whenever the content reasonably matches — {themes}. Only introduce a new theme name if the transcript covers a genuinely distinct major theme that doesn't fit any of these.

Transcript:
{transcript}"""

# Used only if the tracked-themes table is somehow empty when a source is processed.
_FALLBACK_THEMES = (
    "Artificial Intelligence, Machine Learning, Cloud Computing, Semiconductors, Nuclear Energy, "
    "Renewable Energy, Cybersecurity, Digital Payments, Financial Technology, Biotechnology, "
    "Pharmaceutical, Defense & Aerospace, Real Estate, Inflation & Macro, Interest Rates, "
    "Federal Reserve Policy, Supply Chain, Data Centers, Electric Vehicles, Autonomous Driving, "
    "Consumer Discretionary, Commodities"
)


async def extract_from_transcript(transcript: str, title: str = "", known_themes: list[str] | None = None) -> dict:
    """Use GPT-4o to extract stocks, themes, and generate summary. known_themes is the
    user's current tracked-theme list, passed in so extraction stays aligned with what
    they've asked to follow rather than drifting into ad hoc naming."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    truncated = transcript[:100000] if len(transcript) > 100000 else transcript
    themes_str = ", ".join(known_themes) if known_themes else _FALLBACK_THEMES

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    title=title or "Financial Media Content",
                    transcript=truncated,
                    themes=themes_str,
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        # A single JSON blob has to hold the full 12-sentence summary plus every
        # stock/theme/call entry with its own context string -- 4000 was tight enough
        # that extraction-rich transcripts could get cut off mid-string, producing
        # invalid JSON (hard failure) or a truncated-but-parseable response missing
        # entries (silent partial extraction).
        max_tokens=8000,
    )

    return _sanitize_extraction(json.loads(response.choices[0].message.content))


CALL_TYPES = ("buy", "sell", "hold", "avoid", "watch")


def _clamp_sentiment(value) -> float:
    try:
        return float(max(-100, min(100, float(value))))
    except (TypeError, ValueError):
        return 0.0


def _sanitize_extraction(result: dict) -> dict:
    """Validate and normalize a raw GPT extraction. Tickers go through the same
    normalization everywhere (stocks and calls) so a call on "brk.b" lands on the
    same Stock row as a mention of BRK-B."""
    stocks = []
    for s in result.get("stocks", []) or []:
        if isinstance(s, dict) and s.get("ticker"):
            ticker = _normalize_ticker(str(s["ticker"]))
            if ticker is None:
                continue
            stocks.append(
                {
                    "ticker": ticker,
                    "company": str(s.get("company", ""))[:200],
                    "sentiment": _clamp_sentiment(s.get("sentiment", 0)),
                    "context": str(s.get("context", ""))[:300],
                }
            )

    themes = []
    for t in result.get("themes", []) or []:
        if isinstance(t, dict) and t.get("name"):
            themes.append(
                {
                    "name": str(t["name"])[:100],
                    "sentiment": _clamp_sentiment(t.get("sentiment", 0)),
                    "context": str(t.get("context", ""))[:300],
                }
            )

    calls = []
    seen_call_tickers: set[str] = set()
    for c in result.get("calls", []) or []:
        if not (isinstance(c, dict) and c.get("ticker") and c.get("call") in CALL_TYPES):
            continue
        ticker = _normalize_ticker(str(c["ticker"]))
        if ticker is None or ticker in seen_call_tickers:
            continue
        seen_call_tickers.add(ticker)
        price_target = _as_number(c.get("price_target"))
        calls.append({
            "ticker": ticker,
            "call": c["call"],
            "price_target": price_target if price_target is not None and price_target > 0 else None,
            "reasoning": str(c.get("reasoning", ""))[:400],
        })

    return {
        "stocks": stocks,
        "themes": themes,
        "calls": calls,
        "summary": str(result.get("summary") or "")[:3000],
    }


FILING_DETAILS_PROMPT = """You are a financial analyst reviewing an SEC filing or earnings press release.

Title: {title}

Return a JSON object with EXACTLY this structure (no extra fields):
{{
  "period": "the fiscal quarter and year this document reports on, exactly as stated near the top of the document (e.g. \\"Q1 2026\\", \\"Q3 2026\\", or \\"FY2026\\" for an annual report) -- or null if no period is clearly stated",
  "teaser": "one specific sentence, max 18 words, capturing the single most notable headline point of this document -- e.g. the key financial result, guidance change, or major announcement",
  "summary": "4-8 sentence summary of THIS earnings report specifically, per the SUMMARY rules below",
  "metrics": {{
    "revenue": "revenue for the period in raw USD dollars, no abbreviations (e.g. 81600000000 for $81.6 billion), as a number, or null if not stated",
    "revenue_yoy_pct": "year-over-year revenue growth as a number (e.g. 85 for +85%, -12 for -12%), or null if not stated or not computable",
    "revenue_qoq_pct": "sequential (quarter-over-quarter, vs. the immediately preceding quarter) revenue growth as a number -- ONLY for 10-Q filings, never for a 10-K/annual report (no prior quarter to compare); null if not stated or not applicable",
    "eps": "diluted earnings per share in USD as a number (GAAP if both GAAP and non-GAAP are given), or null if not stated",
    "eps_yoy_pct": "year-over-year EPS growth as a number, or null if not stated or not computable",
    "eps_qoq_pct": "sequential (quarter-over-quarter) EPS growth as a number -- ONLY for 10-Q filings, never for a 10-K/annual report; null if not stated or not applicable",
    "net_income": "net income for the period in raw USD dollars, no abbreviations, as a number, or null if not stated",
    "guidance_direction": "exactly one of \\"raised\\", \\"lowered\\", \\"maintained\\", \\"initiated\\" if the filing discusses forward guidance relative to a prior outlook or issues new guidance -- or null if no forward guidance is discussed at all"
  }},
  "capital_returns": "one sentence on share buybacks and/or dividend actions (authorization, increase, suspension, amount) if disclosed in this document, else null",
  "strategic_actions": "one sentence on M&A, divestitures, or major strategic pivots (new segment, restructuring, major partnership) if disclosed in this document, else null"
}}

SUMMARY — 4-8 sentences covering, in order, ONLY the categories that actually apply (do not pad with generic filler if a category doesn't apply to this document):
  1. Headline financial results: revenue and EPS (or other top-line figures) with year-over-year or quarter-over-quarter comparison
  2. The main driver(s) behind those results -- which segment, product, or trend
  3-4. Any other notable results by segment/geography, margin trends, or operational highlights
  5. Capital returns (buybacks/dividends) if disclosed
  6. M&A or strategic actions if disclosed
  7. Forward-looking guidance -- explicitly state whether it was raised, lowered, maintained, or newly initiated, and the outlook commentary
  8. Risks, headwinds, or concerns explicitly disclosed in the document, if any
Plain prose, no bullet points, written for an investor audience. The summary and the dedicated fields above (metrics, capital_returns, strategic_actions) should agree with each other.

Document:
{document}"""


_GUIDANCE_DIRECTIONS = ("raised", "lowered", "maintained", "initiated")


def _as_number(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def extract_filing_details(document_text: str, title: str = "") -> dict:
    """Filing-specific extraction: fiscal period, one-line teaser, a proper
    earnings-report summary (distinct from the generic 12-sentence media summary
    extract_from_transcript produces), headline financial metrics as structured
    fields, and explicit capital-return/M&A/guidance-direction callouts. Used both
    when a new SEC filing is ingested and when backfilling filings that predate
    these fields."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": FILING_DETAILS_PROMPT.format(title=title or "Financial Filing", document=document_text[:12000]),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=700,
    )

    result = json.loads(response.choices[0].message.content)
    period = result.get("period")
    period = str(period).strip()[:20] if period else None

    metrics = result.get("metrics") or {}
    guidance_direction = metrics.get("guidance_direction")
    guidance_direction = guidance_direction if guidance_direction in _GUIDANCE_DIRECTIONS else None

    capital_returns = result.get("capital_returns")
    strategic_actions = result.get("strategic_actions")

    return {
        "period": period or None,
        "teaser": str(result.get("teaser", ""))[:200].strip(),
        "summary": str(result.get("summary", ""))[:2000].strip(),
        "revenue": _as_number(metrics.get("revenue")),
        "revenue_yoy_pct": _as_number(metrics.get("revenue_yoy_pct")),
        "revenue_qoq_pct": _as_number(metrics.get("revenue_qoq_pct")),
        "eps": _as_number(metrics.get("eps")),
        "eps_yoy_pct": _as_number(metrics.get("eps_yoy_pct")),
        "eps_qoq_pct": _as_number(metrics.get("eps_qoq_pct")),
        "net_income": _as_number(metrics.get("net_income")),
        "guidance_direction": guidance_direction,
        "capital_returns": str(capital_returns)[:300].strip() if capital_returns else None,
        "strategic_actions": str(strategic_actions)[:300].strip() if strategic_actions else None,
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


_IMPACT_LABELS = (
    "Positive correlation",
    "Negative correlation",
    "Neutral",
    "Historically correlated",
    "Currently diverging",
)


async def generate_theme_impact_analysis(theme_name: str, known_themes: list[str]) -> dict:
    """Generate a directional ripple-effect analysis for a theme: if this theme rises, and
    separately if it falls, which other themes/the overall market/occasionally a specific
    stock tend to move, in which direction, and why. This is a macro-reasoning exercise
    grounded in general market knowledge -- not a statistical correlation computed from our
    own ingestion volume, which is too thin/short-lived to support that."""
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    theme_list = ", ".join(known_themes)
    label_list = ", ".join(f'"{l}"' for l in _IMPACT_LABELS)

    prompt = (
        f"You are a macro strategist explaining second-order effects for the investment theme "
        f"'{theme_name}'.\n\n"
        f"Return a JSON object with EXACTLY this structure:\n"
        "{\n"
        '  "rising": [ {"target": "...", "target_type": "theme|market|stock", "direction": "up|down", '
        '"label": "...", "rationale": "one sentence"} ],\n'
        '  "falling": [ {"target": "...", "target_type": "theme|market|stock", "direction": "up|down", '
        '"label": "...", "rationale": "one sentence"} ]\n'
        "}\n\n"
        f"\"rising\" describes what tends to happen elsewhere if '{theme_name}' is rising/strengthening. "
        f"\"falling\" describes what tends to happen elsewhere if '{theme_name}' is falling/weakening.\n\n"
        f"Rules:\n"
        f"- 3-4 entries per array, ranked by how strong/well-known the relationship is.\n"
        f"- Prefer target_type \"theme\" and reuse one of these existing tracked themes verbatim when it fits: "
        f"{theme_list}. Only invent a theme name if nothing above fits.\n"
        f"- At most one entry per array may use target_type \"market\" (target: \"Overall Market\"), "
        f"and at most one entry per array may use target_type \"stock\" (a real ticker) as a concrete example.\n"
        f"- \"label\" must be EXACTLY one of: {label_list}.\n"
        f"- \"direction\" is the target's expected direction, not {theme_name}'s.\n"
        f"- rationale is ONE short sentence, plain prose, specific to this relationship (no generic filler).\n"
        f"- Do not include '{theme_name}' itself as a target."
    )

    response = await _create_with_retry(
        client,
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=900,
    )

    result = json.loads(response.choices[0].message.content)

    def _sanitize(entries) -> list[dict]:
        cleaned = []
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or not e.get("target"):
                continue
            label = str(e.get("label", ""))
            if label not in _IMPACT_LABELS:
                continue
            target_type = str(e.get("target_type", "theme")).lower()
            if target_type not in ("theme", "market", "stock"):
                target_type = "theme"
            direction = str(e.get("direction", "")).lower()
            if direction not in ("up", "down"):
                continue
            cleaned.append(
                {
                    "target": str(e["target"])[:100],
                    "target_type": target_type,
                    "direction": direction,
                    "label": label,
                    "rationale": str(e.get("rationale", ""))[:300],
                }
            )
            if len(cleaned) == 4:
                break
        return cleaned

    return {
        "rising": _sanitize(result.get("rising")),
        "falling": _sanitize(result.get("falling")),
    }
