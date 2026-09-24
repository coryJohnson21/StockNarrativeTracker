import asyncio

import httpx
import pytest

from app.services.symbols import _TRADEABLE, resolve_symbol


def _resolve(ticker: str, handler) -> dict | None:
    """Run one lookup against a mocked Yahoo. The project has no pytest-asyncio, so
    tests drive the coroutine directly the way test_insiders.py does."""
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await resolve_symbol(ticker, c)

    return asyncio.run(run())


def _chart(instrument_type: str, price):
    return {
        "chart": {
            "result": [
                {"meta": {"symbol": "X", "instrumentType": instrument_type, "regularMarketPrice": price}}
            ]
        }
    }


@pytest.mark.parametrize("itype", sorted(_TRADEABLE))
def test_tradeable_instruments_with_a_price_are_ok(itype):
    out = _resolve("X", lambda r: httpx.Response(200, json=_chart(itype, 10.5)))
    assert out["verdict"] == "ok"


def test_404_is_unknown():
    """A symbol Yahoo has never heard of: a private company or a hallucinated ticker."""
    out = _resolve("LILY", lambda r: httpx.Response(404, json={}))
    assert out["verdict"] == "unknown"
    assert out["price"] is None


@pytest.mark.parametrize("itype", ["ECNQUOTE", "INDEX", "CURRENCY", "FUTURE"])
def test_non_company_instruments_are_mismatch(itype):
    """"AWS" and "XAI" resolve to ECN quotes -- the row would look healthy while
    pointing at something that is not the company the transcript named."""
    out = _resolve("AWS", lambda r: httpx.Response(200, json=_chart(itype, 10.0)))
    assert out["verdict"] == "mismatch"


def test_tradeable_without_a_price_is_mismatch():
    """PJM resolves to an unrelated ETF carrying no price."""
    out = _resolve("PJM", lambda r: httpx.Response(200, json=_chart("ETF", None)))
    assert out["verdict"] == "mismatch"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transport_errors_are_not_a_verdict(status):
    """A rate limit says nothing about the symbol -- callers must not record one."""
    assert _resolve("NVDA", lambda r: httpx.Response(status, json={})) is None


def test_network_failure_is_not_a_verdict():
    def boom(request):
        raise httpx.ConnectError("no route to host")

    assert _resolve("NVDA", boom) is None


def test_empty_result_is_unknown():
    out = _resolve("NOPE", lambda r: httpx.Response(200, json={"chart": {"result": []}}))
    assert out["verdict"] == "unknown"


def test_crypto_is_tradeable():
    """BTC-USD carries a real price series the momentum code already tracks."""
    assert "CRYPTOCURRENCY" in _TRADEABLE
