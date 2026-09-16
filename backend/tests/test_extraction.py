import pytest

from app.services.extraction import _as_number, _normalize_ticker


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
