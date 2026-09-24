from datetime import date

import pytest

from app.services.reliability import (
    call_alpha, channel_key, posterior_hit_rate, reliability_weight, score_call_outcome,
    wilson_lower,
)


@pytest.mark.parametrize(
    "source_type, channel, expected",
    [
        ("podcast", "Odd Lots", "Odd Lots"),
        ("youtube", "  CNBC Television ", "CNBC Television"),
        ("reddit", None, "reddit"),
        ("news", "", "news"),
        ("upload", "   ", "upload"),
    ],
)
def test_channel_key(source_type, channel, expected):
    assert channel_key(source_type, channel) == expected


@pytest.mark.parametrize(
    "call, excess, expected",
    [
        ("buy", 0.05, 0.05),
        ("buy", -0.05, -0.05),
        ("sell", -0.05, 0.05),
        ("avoid", -0.02, 0.02),
        ("sell", 0.03, -0.03),
        ("hold", 0.10, None),
        ("watch", -0.10, None),
        ("strong buy", 0.1, None),
    ],
)
def test_call_alpha_is_signed_by_direction(call, excess, expected):
    assert call_alpha(call, excess) == expected


def test_posterior_hit_rate_shrinks_toward_coin_flip():
    assert posterior_hit_rate(0, 0) == 0.5
    assert 0.5 < posterior_hit_rate(3, 3) < 0.7          # perfect but tiny sample
    assert posterior_hit_rate(70, 100) == pytest.approx(75 / 110)
    assert posterior_hit_rate(700, 1000) == pytest.approx(0.7, abs=0.005)


def test_reliability_weight_neutral_without_evidence():
    assert reliability_weight(0, 0) == 1.0


def test_reliability_weight_rewards_and_penalizes_real_records():
    good = reliability_weight(70, 100)
    bad = reliability_weight(30, 100)
    coin = reliability_weight(50, 100)
    assert good > 1.1 and bad < 0.9
    assert coin == pytest.approx(1.0, abs=0.01)
    assert good - 1.0 == pytest.approx(1.0 - bad, abs=0.01)


def test_reliability_weight_small_perfect_sample_barely_moves():
    assert 1.0 < reliability_weight(3, 3) < 1.15


def test_wilson_lower_bound():
    assert wilson_lower(0, 0) == 0.0
    assert wilson_lower(3, 3) < 0.5                        # 3/3 is not proof of skill
    assert wilson_lower(70, 100) == pytest.approx(0.604, abs=0.01)
    assert 0.0 <= wilson_lower(0, 10) < 0.05
    assert wilson_lower(1000, 1000) > 0.99


def test_score_call_outcome_judges_against_the_benchmark():
    # Up 8% while SPY did 3%: a buy beat the market by 5 points and was right.
    out = score_call_outcome("buy", 0.08, 0.03)
    assert out["return_pct"] == 8.0
    assert out["benchmark_return_pct"] == 3.0
    assert out["excess_return_pct"] == 5.0
    assert out["alpha_pct"] == 5.0
    assert out["correct"] is True
    assert out["directional"] is True


def test_score_call_outcome_flips_sign_for_bearish_calls():
    # A stock that rose while the market rose more: the sell still beat the benchmark.
    sell = score_call_outcome("sell", 0.02, 0.05)
    assert sell["excess_return_pct"] == -3.0
    assert sell["alpha_pct"] == 3.0
    assert sell["correct"] is True

    # Beating the market is what makes a sell wrong, not the raw return being positive.
    bad_sell = score_call_outcome("sell", 0.08, 0.03)
    assert bad_sell["alpha_pct"] == -5.0
    assert bad_sell["correct"] is False


@pytest.mark.parametrize("call", ["hold", "watch"])
def test_score_call_outcome_leaves_non_bets_unjudged(call):
    out = score_call_outcome(call, 0.10, 0.02)
    assert out["directional"] is False
    assert out["alpha_pct"] is None
    assert out["correct"] is None
    # The move itself is still reported, just not scored as right or wrong.
    assert out["return_pct"] == 10.0


def test_score_call_outcome_pending_when_no_realized_return():
    out = score_call_outcome("buy", None, 0.03)
    assert out["directional"] is True
    assert out["return_pct"] is None
    assert out["alpha_pct"] is None
    # Distinguishable from a wrong call, which has correct is False.
    assert out["correct"] is None


def test_score_call_outcome_falls_back_to_raw_return_without_benchmark():
    out = score_call_outcome("buy", 0.04, None)
    assert out["benchmark_return_pct"] is None
    assert out["excess_return_pct"] == 4.0
    assert out["correct"] is True


def test_score_call_outcome_keeps_unrounded_alpha_for_averaging():
    out = score_call_outcome("buy", 0.12345, 0.001)
    assert out["alpha"] == pytest.approx(0.12245)
    assert out["alpha_pct"] == 12.25


def test_score_call_outcome_reports_return_since_without_scoring_it():
    # The call is wrong over its fixed window but has recovered since; the verdict
    # must follow the window, not the open-ended number beside it.
    out = score_call_outcome("buy", -0.04, 0.01, since=(0.15, date(2026, 9, 22), 47))
    assert out["alpha_pct"] == -5.0
    assert out["correct"] is False
    assert out["return_since_pct"] == 15.0
    assert out["since_as_of"] == date(2026, 9, 22)
    assert out["since_trading_days"] == 47


def test_score_call_outcome_shows_return_since_for_pending_calls():
    # Too recent to judge, but we can still say where it stands today.
    out = score_call_outcome("buy", None, None, since=(0.03, date(2026, 9, 22), 4))
    assert out["correct"] is None
    assert out["return_since_pct"] == 3.0
    assert out["since_trading_days"] == 4


def test_score_call_outcome_since_fields_absent_without_prices():
    out = score_call_outcome("buy", None, None)
    assert out["return_since_pct"] is None
    assert out["since_as_of"] is None
    assert out["since_trading_days"] is None


def test_score_call_outcome_reports_return_since_for_non_bets():
    # Hold takes no side, but the stock still moved and that is worth showing.
    out = score_call_outcome("hold", 0.05, 0.02, since=(0.09, date(2026, 9, 22), 30))
    assert out["directional"] is False
    assert out["correct"] is None
    assert out["return_since_pct"] == 9.0
