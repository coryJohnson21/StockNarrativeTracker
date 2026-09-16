import pytest

from app.services.momentum import (
    MentionStats,
    _compute_score,
    confidence_label,
    growth_component,
    sentiment_to_label,
    share_of_voice_percentile,
    shrunk_sentiment,
)


@pytest.mark.parametrize(
    "sentiment, label",
    [
        (100, "positive"),
        (50, "positive"),
        (49.9, "building"),
        (20, "building"),
        (19.9, "mixed"),
        (0, "mixed"),
        (-19.9, "mixed"),
        (-20, "fading"),
        (-49.9, "fading"),
        (-50, "negative"),
        (-100, "negative"),
    ],
)
def test_sentiment_to_label_boundaries(sentiment, label):
    assert sentiment_to_label(sentiment) == label


@pytest.mark.parametrize(
    "total, unique, expected",
    [
        (0, 0, "low"),
        (2, 2, "low"),
        (3, 1, "low"),
        (3, 2, "medium"),
        (9, 5, "medium"),
        (10, 2, "medium"),
        (10, 3, "high"),
        (100, 40, "high"),
    ],
)
def test_confidence_label(total, unique, expected):
    assert confidence_label(total, unique) == expected


# --- growth ---------------------------------------------------------------


def test_growth_flat_activity_is_neutral():
    # 23 mentions over the prior 23 days -> 7 expected this week. Exactly 7 is flat.
    assert growth_component(7, 23) == pytest.approx(0.5)


def test_growth_no_history_no_mentions_is_neutral():
    assert growth_component(0, 0) == pytest.approx(0.5)


def test_growth_single_mention_from_nothing_does_not_saturate():
    # The old formula gave 1.0 here. One Reddit post is not a maxed-out spike.
    g = growth_component(1, 0)
    assert 0.5 < g < 0.85


def test_growth_saturates_on_real_acceleration():
    # 20 mentions in the prior window (~6/week expected) -> 80 this week.
    assert growth_component(80, 20) == 1.0


def test_growth_floors_on_collapse():
    assert growth_component(0, 230) == 0.0


def test_growth_is_monotonic_in_recent_mentions():
    values = [growth_component(r, 23) for r in range(0, 40, 3)]
    assert values == sorted(values)


def test_growth_shrinkage_scales_with_sample_size():
    # Same 2x ratio, but the large sample should be trusted more than the small one.
    small = growth_component(2, 23 / 7)  # expected 1/week, got 2
    large = growth_component(40, 23 * 20 / 7)  # expected 20/week, got 40
    assert large > small


# --- sentiment ------------------------------------------------------------


def test_shrunk_sentiment_zero_mentions_is_zero():
    assert shrunk_sentiment(90, 0) == 0.0


def test_shrunk_sentiment_pulls_small_samples_toward_zero():
    one = shrunk_sentiment(90, 1)
    many = shrunk_sentiment(90, 100)
    assert one < many / 2
    assert many == pytest.approx(90, abs=3)


def test_shrunk_sentiment_is_relative_to_market():
    # +40 when everything averages +40 is not a signal.
    assert shrunk_sentiment(40, 100, market_avg_sentiment=40) == 0.0
    assert shrunk_sentiment(40, 100, market_avg_sentiment=0) > 0
    assert shrunk_sentiment(40, 100, market_avg_sentiment=80) < 0


# --- share of voice -------------------------------------------------------


def test_share_percentile_ranks_within_universe():
    shares = [0.1, 0.2, 0.3, 0.4]
    assert share_of_voice_percentile(0.4, shares) == pytest.approx(0.875)
    assert share_of_voice_percentile(0.1, shares) == pytest.approx(0.125)


def test_share_percentile_midrank_on_ties():
    assert share_of_voice_percentile(0.25, [0.25, 0.25, 0.25, 0.25]) == pytest.approx(0.5)


def test_share_percentile_empty_universe():
    assert share_of_voice_percentile(0.5, []) == 0.0


def test_share_percentile_is_scale_invariant():
    # Ingesting twice as many sources shouldn't change anyone's relative position.
    shares = [0.1, 0.3, 0.6]
    doubled = [s * 2 for s in shares]
    assert share_of_voice_percentile(0.3, shares) == share_of_voice_percentile(0.6, doubled)


# --- composite score ------------------------------------------------------


def _score(**overrides):
    base = dict(
        freq_percentile=0.0, recent_7d=0, prior_23d=0, avg_sentiment=0.0,
        total_mentions=0, unique_sources=0, market_avg_sentiment=0.0,
    )
    base.update(overrides)
    return _compute_score(**base)


def test_score_is_bounded_and_maxes_out():
    assert _score(freq_percentile=1.0, recent_7d=50, prior_23d=0, avg_sentiment=100,
                  total_mentions=1000, unique_sources=5) == pytest.approx(100.0, abs=0.5)


def test_score_for_no_activity_is_neutral_baseline():
    # growth 0.5 (undefined -> neutral) and sentiment 0 -> 0.5; frequency/diversity 0.
    assert _score() == pytest.approx(0.30 * 0.5 * 100 + 0.25 * 0.5 * 100)


def test_score_never_exceeds_bounds_on_extreme_inputs():
    assert 0 <= _score(freq_percentile=5.0, recent_7d=10**6, avg_sentiment=100, total_mentions=10**6, unique_sources=10**6) <= 100
    assert 0 <= _score(freq_percentile=-1.0, prior_23d=10**6, avg_sentiment=-100, total_mentions=10**6) <= 100


def test_diversity_saturates_at_five_sources():
    assert _score(unique_sources=5) == _score(unique_sources=50)


def test_sentiment_moves_score_by_at_most_25_points():
    bearish = _score(avg_sentiment=-100, total_mentions=10**6)
    bullish = _score(avg_sentiment=100, total_mentions=10**6)
    assert bullish - bearish == pytest.approx(25.0, abs=0.1)


def test_one_bullish_mention_barely_moves_score():
    # Confidence is earned: a single +90 mention should be worth only a few points.
    assert _score(avg_sentiment=90, total_mentions=1) - _score() < 6


# --- MentionStats ---------------------------------------------------------


def test_growth_rate_uses_non_overlapping_baseline():
    # 23 in the prior window (7/week expected), 14 this week -> +100%.
    s = MentionStats(recent_7d=14, prior_23d=23)
    assert s.growth_rate == pytest.approx(1.0)


def test_growth_rate_with_no_history():
    assert MentionStats(recent_7d=3, prior_23d=0).growth_rate == 1.0
    assert MentionStats(recent_7d=0, prior_23d=0).growth_rate == 0.0


def test_weighted_avg_sentiment_handles_zero_weight():
    assert MentionStats().w_avg_sentiment == 0.0
    assert MentionStats(w_total=2.0, w_sentiment_sum=100.0).w_avg_sentiment == 50.0
