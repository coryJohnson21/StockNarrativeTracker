import pytest

from app.services.calls import call_consensus


@pytest.mark.parametrize(
    "counts, expected",
    [
        ({}, None),
        ({"buy": 4}, 1.0),
        ({"sell": 2, "avoid": 2}, -1.0),
        ({"buy": 2, "sell": 2}, 0.0),
        ({"buy": 3, "hold": 1}, 0.75),
        ({"buy": 1, "watch": 3}, 0.25),
        ({"buy": 1, "sell": 1, "hold": 2}, 0.0),
        ({"strong_buy": 5}, None),
    ],
)
def test_call_consensus(counts, expected):
    assert call_consensus(counts) == expected
