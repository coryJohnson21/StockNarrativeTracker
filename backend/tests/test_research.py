from datetime import date, datetime, timedelta

import pytest

from app.services.research import (
    MentionSeries, Observation, PriceSeries, average_ranks, bucketize, factor_ic, spearman, summarize_backtest,
)

D0 = date(2026, 6, 1)


def _m(days_ago: int, sentiment: float = 0.0, is_self: bool = False, source: str = None):
    ts = datetime.combine(D0 - timedelta(days=days_ago), datetime.min.time()) + timedelta(hours=12)
    return (ts, sentiment, is_self, source or f"src-{days_ago}")


# --- MentionSeries ----------------------------------------------------------


def test_stats_as_of_windows_only_count_mentions_on_or_before_the_day():
    series = MentionSeries([_m(0), _m(3), _m(10), _m(40), _m(-2)])  # one in the future
    s = series.stats_as_of(D0)
    assert s.total == 4
    assert s.recent_7d == 2         # days 0 and 3
    assert s.recent_30d == 3        # + day 10
    assert s.prior_23d == 1         # day 10 only
    assert s.unique_sources == 4


def test_stats_as_of_earlier_day_excludes_later_mentions():
    series = MentionSeries([_m(0), _m(3), _m(10)])
    s = series.stats_as_of(D0 - timedelta(days=5))
    assert s.total == 1 and s.recent_7d == 1


def test_stats_as_of_weights_self_mentions():
    series = MentionSeries([_m(1, 80, is_self=True), _m(2, 20)])
    s = series.stats_as_of(D0)
    assert s.w_total == pytest.approx(1.3)
    assert s.avg_sentiment == 50.0
    assert s.w_avg_sentiment == pytest.approx((80 * 0.3 + 20) / 1.3)


def test_stats_as_of_distinct_sources_are_cumulative():
    series = MentionSeries([_m(1, source="a"), _m(2, source="a"), _m(3, source="b")])
    assert series.stats_as_of(D0).unique_sources == 2


def test_empty_series():
    s = MentionSeries([]).stats_as_of(D0)
    assert s.total == 0 and s.w_total == 0.0 and s.avg_sentiment == 0.0


# --- PriceSeries ------------------------------------------------------------


def _prices(start: date, closes: list[float], skip_weekends: bool = True) -> PriceSeries:
    pts, d = [], start
    for c in closes:
        while skip_weekends and d.weekday() >= 5:
            d += timedelta(days=1)
        pts.append((d, c))
        d += timedelta(days=1)
    return PriceSeries(pts)


def test_forward_return_uses_trading_day_offsets():
    ps = _prices(date(2026, 6, 1), [100, 101, 102, 103, 104, 110, 120])  # Mon-Fri, then Mon Tue
    assert ps.forward_return(date(2026, 6, 1), 1) == pytest.approx(0.01)
    assert ps.forward_return(date(2026, 6, 1), 5) == pytest.approx(0.10)  # Mon -> next Mon


def test_forward_return_enters_on_next_trading_day_after_a_weekend():
    ps = _prices(date(2026, 6, 1), [100, 101, 102, 103, 104, 110])
    # Saturday June 6 -> entry is Monday June 8 at 110, no exit available yet.
    assert ps.forward_return(date(2026, 6, 6), 1) is None
    ps2 = _prices(date(2026, 6, 1), [100, 101, 102, 103, 104, 110, 121])
    assert ps2.forward_return(date(2026, 6, 6), 1) == pytest.approx(0.10)


def test_forward_return_none_when_unrealized_or_gap():
    ps = _prices(date(2026, 6, 1), [100, 101, 102])
    assert ps.forward_return(date(2026, 6, 1), 5) is None
    assert ps.forward_return(date(2026, 5, 1), 1) is None  # entry 31 days late -> gap
    assert ps.forward_return(date(2026, 7, 1), 1) is None  # after the series ends


def test_return_since_runs_to_the_latest_close():
    ps = _prices(date(2026, 6, 1), [100, 101, 102, 103, 104, 110, 120])
    ret, as_of, days = ps.return_since(date(2026, 6, 1))
    assert ret == pytest.approx(0.20)          # 100 -> 120, the last close we hold
    assert as_of == date(2026, 6, 9)
    assert days == 6


def test_return_since_shares_the_entry_rule_with_forward_return():
    ps = _prices(date(2026, 6, 1), [100, 101, 102, 103, 104, 110])
    # Saturday June 6 enters Monday June 8 at 110, same as forward_return.
    ret, _, days = ps.return_since(date(2026, 6, 6))
    assert ret == pytest.approx(0.0)
    assert days == 0
    assert ps.return_since(date(2026, 5, 1)) is None    # entry 31 days late -> gap
    assert ps.return_since(date(2026, 7, 1)) is None    # after the series ends


def test_return_since_is_available_before_a_horizon_completes():
    ps = _prices(date(2026, 6, 1), [100, 101, 102])
    # Nothing scorable over 5 days yet, but where it stands today is known.
    assert ps.forward_return(date(2026, 6, 1), 5) is None
    ret, _, days = ps.return_since(date(2026, 6, 1))
    assert ret == pytest.approx(0.02)
    assert days == 2


# --- rank statistics --------------------------------------------------------


def test_average_ranks_handles_ties():
    assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_spearman_perfect_and_inverse():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_is_rank_based_not_linear():
    assert spearman([1, 2, 3, 4], [1, 10, 100, 1000]) == pytest.approx(1.0)


def test_spearman_degenerate_inputs():
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert spearman([1, 2, 3], [1, 2]) is None


# --- buckets & IC -----------------------------------------------------------


def _obs(score, ret, excess=None, day=D0, n7=1, sent=0.0, sov=0.0):
    return Observation(stock_id=score, date=day, score=score, avg_sentiment=sent, mention_count_7d=n7,
                       share_of_voice=sov, ret=ret, excess=excess)


def test_bucketize_equal_counts_lowest_first():
    # excess runs from -0.4 (score 10) to +0.5 (score 100), crossing zero mid-range
    obs = [_obs(s, ret=s / 100, excess=s / 100 - 0.5) for s in range(10, 110, 10)]
    rows = bucketize(obs, 5)
    assert [r["n"] for r in rows] == [2, 2, 2, 2, 2]
    assert rows[0]["score_min"] == 10 and rows[-1]["score_max"] == 100
    assert rows[0]["mean_excess_pct"] < rows[-1]["mean_excess_pct"]
    assert rows[0]["hit_rate"] == 0.0 and rows[-1]["hit_rate"] == 1.0


def test_bucketize_caps_buckets_at_observation_count():
    assert len(bucketize([_obs(1, 0.0), _obs(2, 0.0)], 5)) == 2
    assert bucketize([], 5) == []


def test_bucketize_falls_back_to_raw_return_without_benchmark():
    rows = bucketize([_obs(1, 0.02), _obs(2, 0.04)], 1)
    assert rows[0]["mean_return_pct"] == 3.0 and rows[0]["mean_excess_pct"] is None


def test_factor_ic_reports_daily_mean_and_t_stat():
    obs = []
    for k in range(6):  # six dates, each with 5 stocks where score perfectly ranks excess
        day = D0 + timedelta(days=k)
        obs += [_obs(s, ret=0.0, excess=s * 0.001, day=day) for s in (1, 2, 3, 4, 5)]
    ic = factor_ic(obs, lambda o: o.score)
    assert ic["ic"] == pytest.approx(1.0)
    assert ic["mean_daily_ic"] == pytest.approx(1.0)
    assert ic["n_dates"] == 6
    assert ic["t_stat"] is None  # zero variance across dates -> undefined, not infinite


def test_factor_ic_skips_thin_dates():
    obs = [_obs(1, 0.0, 0.01), _obs(2, 0.0, 0.02)]  # one date, too few for a daily IC
    ic = factor_ic(obs, lambda o: o.score)
    assert ic["n_dates"] == 0 and ic["mean_daily_ic"] is None and ic["ic"] is None


def test_factor_ic_drops_observations_where_the_factor_is_undefined():
    # Only 3 of 6 stock-days have an insider factor; those 3 shouldn't be scored as 0.
    obs = []
    for k in range(6):
        day = D0 + timedelta(days=k)
        obs += [_obs(s, ret=0.0, excess=s * 0.001, day=day) for s in (1, 2, 3, 4, 5)]
    for i, o in enumerate(obs):
        o.insider_net_90d = None if i % 2 else 1.0 - o.score / 10
    ic = factor_ic(obs, lambda o: o.insider_net_90d)
    assert ic["n"] == len(obs) // 2
    assert ic["ic"] is not None and ic["ic"] < 0  # constructed inverse relationship


def test_summarize_backtest_shape_and_spread():
    obs = [_obs(s, ret=s / 1000, excess=s / 1000 - 0.03) for s in range(10, 110, 10)]
    out = summarize_backtest(obs, horizon=20, buckets=5, min_mentions_7d=1, benchmark_available=True)
    assert out["n_observations"] == 10 and out["n_dates"] == 1
    assert out["spread_excess_pct"] == pytest.approx(out["buckets"][-1]["mean_excess_pct"] - out["buckets"][0]["mean_excess_pct"])
    assert {f["factor"] for f in out["factor_ic"]} == {
        "score", "avg_sentiment", "mention_count_7d", "share_of_voice", "insider_net_90d",
    }


def test_summarize_backtest_empty():
    out = summarize_backtest([], horizon=5, buckets=5, min_mentions_7d=1, benchmark_available=False)
    assert out["n_observations"] == 0 and out["buckets"] == [] and out["spread_excess_pct"] is None


# --- RSI (Wilder) ---

def _series(closes: list[float]):
    """A PriceSeries over consecutive days, for the price-shape tests below."""
    from datetime import date, timedelta

    from app.services.research import PriceSeries

    return PriceSeries([(date(2024, 1, 1) + timedelta(days=i), c) for i, c in enumerate(closes)])


# Wilder's own worked example from New Concepts in Technical Trading Systems --
# the reference vector every charting package is checked against.
WILDER_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
    45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
]


def test_rsi_matches_wilders_published_example():
    assert _series(WILDER_CLOSES).rsi(14) == 70.5


def test_rsi_uses_wilder_smoothing_not_a_span_14_ema():
    """alpha = 1/14, not 2/15. A span-14 EMA gives a visibly different number, and
    the difference is enough to move a reading across the 70 line."""
    closes = WILDER_CLOSES + [46.00, 46.03, 46.41, 46.22, 45.64]
    wilder = _series(closes).rsi(14)

    deltas = [b - a for a, b in zip(closes, closes[1:])]
    alpha = 2 / 15  # the wrong smoothing
    avg_gain = avg_loss = None
    for d in deltas:
        gain, loss = max(d, 0.0), max(-d, 0.0)
        avg_gain = gain if avg_gain is None else avg_gain + alpha * (gain - avg_gain)
        avg_loss = loss if avg_loss is None else avg_loss + alpha * (loss - avg_loss)
    ema_version = round(100 - 100 / (1 + avg_gain / avg_loss), 1)

    assert wilder != ema_version


def test_rsi_needs_one_more_close_than_periods():
    """n deltas require n+1 closes; below that there is no seed to smooth from."""
    assert _series([100 + i for i in range(14)]).rsi(14) is None
    assert _series([100 + i for i in range(15)]).rsi(14) is not None


def test_rsi_saturates_without_dividing_by_zero():
    """An all-gains window has no downside to divide by -- 100 by definition."""
    assert _series([100 + i for i in range(30)]).rsi(14) == 100.0
    assert _series([200 - i for i in range(30)]).rsi(14) == 0.0


def test_rsi_of_a_flat_series_is_neutral():
    """No gains and no losses is 0/0. Report the neutral midpoint rather than
    inheriting the all-gains branch's 100."""
    assert _series([100.0] * 30).rsi(14) == 50.0


def test_rsi_is_bounded_and_rejects_nonsense_periods():
    value = _series([100, 102, 101, 105, 103, 108, 107, 110, 109, 112,
                     111, 115, 113, 118, 117, 120]).rsi(14)
    assert value is not None and 0.0 <= value <= 100.0
    assert _series([100 + i for i in range(30)]).rsi(0) is None
