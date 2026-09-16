import pytest

from app.services.reliability import (
    call_alpha, channel_key, posterior_hit_rate, reliability_weight, wilson_lower,
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
