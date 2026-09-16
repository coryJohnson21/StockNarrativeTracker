import pytest

from app.services.extraction import _as_number, _normalize_ticker, _sanitize_extraction


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("NVDA", "NVDA"),
        ("nvda", "NVDA"),
        ("  aapl  ", "AAPL"),
        ("A", "A"),
        ("BRK.B", "BRK-B"),
        ("BRK/A", "BRK-A"),
        ("brkb", "BRK-B"),
        ("BF.B", "BF-B"),
        ("J&J", "JNJ"),
        ("SQ", "XYZ"),
        ("SQUARE", "XYZ"),
        ("SPACEX", "SPCX"),
        ("HXSCL", "SKHY"),
        ("NEX", "NEE"),
        ("FPL", "NEE"),
        ("TWL", "WULF"),
        ("OPENAI", "OPENAI"),
        ("ABC123", "ABC123"),
    ],
)
def test_normalize_ticker_accepts_and_normalizes(raw, expected):
    assert _normalize_ticker(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "S&P 500",
        "S&P",
        "Dow Jones",
        "NASDAQ Composite",
        "Russell 2000",
        "VIX",
        "SK HYNIX",
        "$AAPL",
        "MSFT.",
        "3M",
        "ABCDEFGHIJ",
        "BRK.BB",
        "",
    ],
)
def test_normalize_ticker_rejects_invalid(raw):
    assert _normalize_ticker(raw) is None


def test_normalize_ticker_aliases_take_precedence_over_validation():
    # "J&J" would fail the ticker regex, but the alias table is consulted first.
    assert _normalize_ticker("j&j") == "JNJ"


def test_spce_is_not_aliased_to_spacex():
    assert _normalize_ticker("SPCE") == "SPCE"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (42, 42.0),
        (3.5, 3.5),
        ("81600000000", 81600000000.0),
        ("-12", -12.0),
        ("n/a", None),
        ("", None),
        ([], None),
    ],
)
def test_as_number(value, expected):
    assert _as_number(value) == expected


# --- whole-extraction sanitization ---------------------------------------


def test_sanitize_normalizes_call_tickers_like_stock_tickers():
    result = _sanitize_extraction({
        "stocks": [{"ticker": "brk.b", "company": "Berkshire", "sentiment": 60}],
        "calls": [{"ticker": "BRK/B", "call": "buy", "price_target": "500", "reasoning": "cheap"}],
    })
    assert result["stocks"][0]["ticker"] == "BRK-B"
    assert result["calls"][0] == {"ticker": "BRK-B", "call": "buy", "price_target": 500.0, "reasoning": "cheap"}


def test_sanitize_drops_invalid_calls():
    result = _sanitize_extraction({
        "calls": [
            {"ticker": "S&P 500", "call": "buy"},            # index, not a stock
            {"ticker": "NVDA", "call": "strong buy"},         # not a recognized call type
            {"ticker": "", "call": "sell"},                   # no ticker
            "not a dict",
            {"ticker": "AAPL", "call": "hold"},
        ],
    })
    assert [c["ticker"] for c in result["calls"]] == ["AAPL"]


def test_sanitize_dedupes_calls_per_ticker_keeping_first():
    result = _sanitize_extraction({
        "calls": [
            {"ticker": "NVDA", "call": "buy"},
            {"ticker": "nvda", "call": "sell"},
        ],
    })
    assert len(result["calls"]) == 1 and result["calls"][0]["call"] == "buy"


@pytest.mark.parametrize("raw, expected", [(150, 150.0), ("150.5", 150.5), (None, None), ("n/a", None), (0, None), (-5, None)])
def test_sanitize_price_target(raw, expected):
    result = _sanitize_extraction({"calls": [{"ticker": "AAPL", "call": "buy", "price_target": raw}]})
    assert result["calls"][0]["price_target"] == expected


def test_sanitize_clamps_and_coerces_sentiment():
    result = _sanitize_extraction({
        "stocks": [
            {"ticker": "A", "sentiment": 250},
            {"ticker": "B", "sentiment": "-400"},
            {"ticker": "C", "sentiment": "very bullish"},
        ],
        "themes": [{"name": "AI", "sentiment": None}],
    })
    assert [s["sentiment"] for s in result["stocks"]] == [100.0, -100.0, 0.0]
    assert result["themes"][0]["sentiment"] == 0.0


def test_sanitize_tolerates_missing_and_null_sections():
    result = _sanitize_extraction({"stocks": None, "summary": None})
    assert result == {"stocks": [], "themes": [], "calls": [], "summary": ""}
