from datetime import date, timedelta

import pytest

from app.services.research import PriceSeries
from app.services.theme_index import build_equal_weight_index, lead_lag, weekly_buckets

MON = date(2026, 6, 1)  # a Monday


def _ps(start: date, closes: list[float]) -> PriceSeries:
    pts, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        pts.append((d, c))
        d += timedelta(days=1)
    return PriceSeries(pts)


# --- index ---------------------------------------------------------------------


def test_index_starts_at_100_and_averages_constituent_returns():
    a = _ps(MON, [100, 110, 121])       # +10%, +10%
    b = _ps(MON, [50, 50, 55])          # 0%, +10%
    idx = build_equal_weight_index({"A": a, "B": b}, MON)
    assert [p["value"] for p in idx] == [100.0, 105.0, pytest.approx(115.5)]
    assert all(p["constituents"] == 2 for p in idx)


def test_index_ignores_a_constituent_on_days_it_has_no_close():
    a = _ps(MON, [100, 110, 121])
    b = PriceSeries([(MON, 50), (MON + timedelta(days=2), 60)])   # missing Tuesday
    idx = build_equal_weight_index({"A": a, "B": b}, MON)
    # Tue: only A has both days -> +10%. Wed: only A has Tue & Wed -> +10% (B has no Tue).
    assert [p["value"] for p in idx] == [100.0, 110.0, pytest.approx(121.0)]
    assert [p["constituents"] for p in idx] == [2, 1, 2]


def test_index_uses_lead_in_so_first_window_day_has_a_return_base():
    a = _ps(MON - timedelta(days=7), [100, 100, 100, 100, 100, 200, 220])  # prior week flat, then window
    idx = build_equal_weight_index({"A": a}, MON)
    # Base is 100 on the first in-window day regardless of the pre-window move; next day +10%.
    assert idx[0]["date"] == MON.isoformat() and idx[0]["value"] == 100.0
    assert idx[1]["value"] == pytest.approx(110.0)


def test_index_empty():
    assert build_equal_weight_index({}, MON) == []
    assert build_equal_weight_index({"A": _ps(MON - timedelta(days=30), [1, 2])}, MON) == []


# --- weekly buckets ------------------------------------------------------------


def test_weekly_buckets_join_index_and_narrative():
    index = [
        {"date": MON.isoformat(), "value": 100.0},
        {"date": (MON + timedelta(days=4)).isoformat(), "value": 104.0},
        {"date": (MON + timedelta(days=11)).isoformat(), "value": 98.8},
    ]
    narrative = [
        {"date": (MON + timedelta(days=1)).isoformat(), "mention_count": 3, "avg_sentiment": 60},
        {"date": (MON + timedelta(days=3)).isoformat(), "mention_count": 1, "avg_sentiment": -20},
        {"date": (MON + timedelta(days=14)).isoformat(), "mention_count": 2, "avg_sentiment": 0},  # week with no index
    ]
    weeks = weekly_buckets(index, narrative)
    assert [w["week"] for w in weeks] == [MON.isoformat(), (MON + timedelta(days=7)).isoformat(), (MON + timedelta(days=14)).isoformat()]
    assert weeks[0]["index_value"] == 104.0 and weeks[0]["index_return_pct"] is None
    assert weeks[0]["mention_count"] == 4 and weeks[0]["avg_sentiment"] == 40.0   # (3*60 + 1*-20) / 4
    assert weeks[1]["index_return_pct"] == -5.0 and weeks[1]["mention_count"] == 0 and weeks[1]["avg_sentiment"] is None
    assert weeks[2]["index_value"] is None and weeks[2]["mention_count"] == 2


# --- lead / lag ----------------------------------------------------------------


def _weeks(sentiment: list[float], returns: list[float]) -> list[dict]:
    return [
        {"week": (MON + timedelta(days=7 * i)).isoformat(), "index_return_pct": r, "mention_count": 5, "avg_sentiment": s}
        for i, (s, r) in enumerate(zip(sentiment, returns))
    ]


def test_lead_lag_detects_narrative_leading_price():
    sentiment = [10, 50, -30, 70, -60, 20, 90, -10, 40, 0]
    returns = [0.0] + [s / 10 for s in sentiment[:-1]]  # this week's return = last week's sentiment
    ll = lead_lag(_weeks(sentiment, returns))["avg_sentiment"]
    assert ll["leads"] == pytest.approx(1.0) and ll["verdict"] == "leads"
    assert abs(ll["coincident"]) < 0.7


def test_lead_lag_detects_narrative_chasing_price():
    returns = [1.0, -2.0, 3.0, -1.0, 2.5, -3.0, 0.5, 1.5, -2.5, 2.0]
    sentiment = [0.0] + [r * 10 for r in returns[:-1]]  # this week's sentiment = last week's return
    ll = lead_lag(_weeks(sentiment, returns))["avg_sentiment"]
    assert ll["lags"] == pytest.approx(1.0) and ll["verdict"] == "lags"


def test_lead_lag_needs_enough_weeks():
    ll = lead_lag(_weeks([1, 2, 3, 4], [1, 2, 3, 4]))["avg_sentiment"]
    assert ll["leads"] is None and ll["coincident"] is None and ll["verdict"] is None


def test_lead_lag_weak_relationship_is_none_verdict():
    sentiment = [10, -10, 10, -10, 10, -10, 10, -10, 10, -10]
    returns = [1, 1, -1, -1, 1, 1, -1, -1, 1, 1]
    assert lead_lag(_weeks(sentiment, returns))["avg_sentiment"]["verdict"] in ("none", None)
