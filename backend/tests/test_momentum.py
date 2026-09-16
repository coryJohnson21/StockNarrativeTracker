import pytest

from app.services.momentum import _compute_score, sentiment_to_label


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


def test_score_is_bounded_and_maxes_out():
    score = _compute_score(
        total_mentions=10, recent_7d=5, older_30d=0,
        avg_sentiment=100, unique_sources=5, max_total_mentions=10,
    )
    assert score == 100.0


def test_score_for_no_activity_is_neutral_baseline():
    # No mentions at all: freq 0, growth 0.5 (undefined -> neutral),
    # sentiment 0 -> 0.5, diversity 0.
    score = _compute_score(0, 0, 0, 0.0, 0, max_total_mentions=10)
    assert score == pytest.approx(0.30 * 0.5 * 100 + 0.25 * 0.5 * 100)


def test_score_never_exceeds_bounds_on_extreme_inputs():
    assert 0 <= _compute_score(1000, 1000, 1, 100, 1000, 1) <= 100
    assert 0 <= _compute_score(0, 0, 1000, -100, 0, 1) <= 100


def test_growth_component_neutral_when_recent_matches_trend():
    # 8 mentions over 30 days -> 2 expected per week. Exactly 2 in the last 7 days
    # is flat, so growth should sit at 0.5 -- same as a stock with no history at all.
    flat = _compute_score(8, 2, 8, 0.0, 0, 8)
    no_history = _compute_score(8, 0, 0, 0.0, 0, 8)
    assert flat == no_history


def test_growth_component_is_monotonic_in_recent_mentions():
    scores = [_compute_score(8, recent, 8, 0.0, 0, 8) for recent in (0, 1, 2, 3, 4)]
    assert scores == sorted(scores)
    # Accelerating (4 vs. expected 2) saturates growth at 1.0; collapsing (0) floors at 0.
    assert scores[-1] - scores[0] == pytest.approx(30.0)


def test_frequency_normalized_against_max():
    low = _compute_score(1, 0, 0, 0.0, 0, max_total_mentions=10)
    high = _compute_score(10, 0, 0, 0.0, 0, max_total_mentions=10)
    assert high - low == pytest.approx(0.30 * 0.9 * 100)


def test_frequency_handles_zero_max_without_dividing_by_zero():
    assert _compute_score(0, 0, 0, 0.0, 0, max_total_mentions=0) >= 0


def test_diversity_saturates_at_five_sources():
    five = _compute_score(1, 0, 0, 0.0, 5, 1)
    fifty = _compute_score(1, 0, 0, 0.0, 50, 1)
    assert five == fifty


def test_sentiment_moves_score_by_at_most_25_points():
    bearish = _compute_score(1, 0, 0, -100, 0, 1)
    bullish = _compute_score(1, 0, 0, 100, 0, 1)
    assert bullish - bearish == pytest.approx(25.0)
