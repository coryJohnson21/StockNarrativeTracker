"""Does this extracted ticker name a real, tradeable security?

_normalize_ticker in services/extraction.py only checks *shape* -- "PJM" and "FERC"
look exactly like "NVDA". The aliases there fix symbols we have seen go wrong by
hand, one at a time. This resolves the rest against Yahoo, which is the same source
the price and momentum feeds use, so a ticker that validates here is one those feeds
can actually price.

Three outcomes, kept distinct because they want different handling:

  ok        -- resolves to an equity/ETF with a price. Track it.
  unknown   -- Yahoo has never heard of it (404). Either a private company the
               transcript named (OpenAI, Stripe) or a hallucinated symbol (LILY,
               FERC). Either way there is nothing to price.
  mismatch  -- resolves, but to something that is not a tradeable company: an
               index, a currency, an ECN quote. "AWS" hits an ECNQUOTE and "PJM"
               an unrelated ETF -- the dangerous case, because the row looks
               healthy while pointing at the wrong security.

A network failure is never a verdict. It returns None, and the caller leaves the
ticker alone rather than recording a judgement it could not make.
"""
import asyncio
import logging
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Yahoo instrumentTypes that represent something a person can hold and we can price.
# ETFs count (BND, SMH are legitimately tracked despite having no market cap), and so
# does crypto -- BTC-USD carries a real price series the momentum code already uses.
# Deliberately excluded: INDEX, CURRENCY, FUTURE, and ECNQUOTE, which is what a
# hallucinated acronym like "AWS" or "XAI" resolves to.
_TRADEABLE = {"EQUITY", "ETF", "MUTUALFUND", "ADRC", "CRYPTOCURRENCY"}

Verdict = Literal["ok", "unknown", "mismatch"]


async def resolve_symbol(ticker: str, client: Optional[httpx.AsyncClient] = None) -> Optional[dict]:
    """Look one symbol up. Returns {verdict, symbol, instrument_type, price} or None
    if the lookup itself failed (timeout, rate limit, transport error)."""
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        r = await client.get(
            CHART_URL.format(ticker=ticker),
            headers=_HEADERS,
            params={"range": "5d", "interval": "1d"},
            timeout=12.0,
        )
        if r.status_code == 404:
            return {"verdict": "unknown", "symbol": None, "instrument_type": None, "price": None}
        if r.status_code != 200:
            # 429s and 5xxs say nothing about the symbol, only about Yahoo.
            return None
        chart = (r.json().get("chart") or {})
        if chart.get("error"):
            code = (chart["error"] or {}).get("code", "")
            return (
                {"verdict": "unknown", "symbol": None, "instrument_type": None, "price": None}
                if "not" in str(code).lower() or "found" in str(code).lower()
                else None
            )
        results = chart.get("result") or []
        if not results:
            return {"verdict": "unknown", "symbol": None, "instrument_type": None, "price": None}
        meta = results[0].get("meta") or {}
        itype = (meta.get("instrumentType") or "").upper()
        price = meta.get("regularMarketPrice")
        verdict: Verdict = "ok" if itype in _TRADEABLE and price is not None else "mismatch"
        return {
            "verdict": verdict,
            "symbol": meta.get("symbol"),
            "instrument_type": itype or None,
            "price": price,
        }
    except Exception as e:  # network/parse failure -- not a verdict about the symbol
        logger.debug("symbol lookup failed for %s: %s", ticker, e)
        return None
    finally:
        if own_client:
            await client.aclose()


async def resolve_symbols(tickers: list[str], delay: float = 0.25) -> dict[str, dict]:
    """Resolve several symbols, spaced out so Yahoo does not rate-limit us. Symbols
    whose lookup failed are omitted, so callers can tell 'no verdict' from a verdict."""
    out: dict[str, dict] = {}
    async with httpx.AsyncClient() as client:
        for i, t in enumerate(tickers):
            result = await resolve_symbol(t, client)
            if result is not None:
                out[t] = result
            if i < len(tickers) - 1:
                await asyncio.sleep(delay)
    return out
