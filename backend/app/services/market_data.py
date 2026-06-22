import time
from datetime import datetime
from typing import Optional, TypedDict

import httpx

QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
MODULES = "summaryDetail,defaultKeyStatistics,assetProfile,price"

# Yahoo blocks requests without a browser-like User-Agent, and as of 2024+ the
# quoteSummary endpoint also requires a session cookie + CSRF "crumb" obtained
# via an unauthenticated handshake (no API key needed, just these two requests).
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NarrativeTracker/1.0)"}

_crumb_cache: dict = {"crumb": None, "cookies": None, "fetched_at": 0.0}
_CRUMB_TTL = 3600  # crumbs/cookies are long-lived but refresh hourly defensively


async def _get_crumb(client: httpx.AsyncClient) -> tuple[Optional[str], Optional[httpx.Cookies]]:
    if _crumb_cache["crumb"] and time.monotonic() - _crumb_cache["fetched_at"] < _CRUMB_TTL:
        return _crumb_cache["crumb"], _crumb_cache["cookies"]

    await client.get("https://fc.yahoo.com", headers=_HEADERS, timeout=10.0)
    crumb_response = await client.get(CRUMB_URL, headers=_HEADERS, timeout=10.0)
    if crumb_response.status_code != 200:
        return None, None

    crumb = crumb_response.text.strip()
    _crumb_cache.update(crumb=crumb, cookies=client.cookies, fetched_at=time.monotonic())
    return crumb, client.cookies


def _raw(value) -> Optional[float]:
    if isinstance(value, dict):
        return value.get("raw")
    return None


class MarketData(TypedDict):
    open_price: Optional[float]
    current_price: Optional[float]
    currency: Optional[str]
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    price_to_book: Optional[float]
    price_to_sales: Optional[float]
    business_summary: Optional[str]


class PricePoint(TypedDict):
    date: str
    close: float


async def fetch_price_history(ticker: str, range_: str = "6mo", interval: str = "1d") -> list[PricePoint]:
    """Fetch historical daily closes from Yahoo's chart endpoint (no crumb/auth needed)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            CHART_URL.format(ticker=ticker),
            params={"range": range_, "interval": interval},
            headers=_HEADERS,
            timeout=15.0,
        )

    if response.status_code != 200:
        return []

    result = response.json().get("chart", {}).get("result")
    if not result:
        return []

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    closes = (chart.get("indicators", {}).get("quote") or [{}])[0].get("close") or []

    points = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        points.append(
            PricePoint(date=datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"), close=round(close, 2))
        )
    return points


async def fetch_market_data(ticker: str) -> Optional[MarketData]:
    """Fetch live price + fundamentals from Yahoo Finance's unofficial APIs."""
    async with httpx.AsyncClient() as client:
        crumb, cookies = await _get_crumb(client)
        if not crumb:
            return None

        response = await client.get(
            QUOTE_SUMMARY_URL.format(ticker=ticker),
            params={"modules": MODULES, "crumb": crumb},
            headers=_HEADERS,
            cookies=cookies,
            timeout=15.0,
        )

    if response.status_code != 200:
        return None

    results = response.json().get("quoteSummary", {}).get("result")
    if not results:
        return None

    data = results[0]
    summary_detail = data.get("summaryDetail", {})
    key_stats = data.get("defaultKeyStatistics", {})
    profile = data.get("assetProfile", {})
    price = data.get("price", {})

    return MarketData(
        open_price=_raw(price.get("regularMarketOpen")) or _raw(summary_detail.get("open")),
        current_price=_raw(price.get("regularMarketPrice")),
        currency=price.get("currency"),
        market_cap=_raw(summary_detail.get("marketCap")) or _raw(price.get("marketCap")),
        pe_ratio=_raw(summary_detail.get("trailingPE")),
        price_to_book=_raw(key_stats.get("priceToBook")),
        price_to_sales=_raw(summary_detail.get("priceToSalesTrailing12Months")),
        business_summary=profile.get("longBusinessSummary"),
    )
