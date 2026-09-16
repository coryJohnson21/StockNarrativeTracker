import pytest

from app.services.signals import crowding_signal, management_vs_media_signal, narrative_vs_price_signal


# --- management vs media -----------------------------------------------------


def test_guidance_raised_against_negative_coverage_is_an_alert():
    s = management_vs_media_signal(60, 3, -25, 5, "raised")
    assert s["severity"] == "alert" and "raised" in s["title"].lower()


def test_guidance_lowered_against_bullish_coverage_is_an_alert():
    s = management_vs_media_signal(-10, 3, 40, 5, "lowered")
    assert s["severity"] == "alert" and "cut" in s["title"].lower()


def test_guidance_signal_needs_media_sample():
    assert management_vs_media_signal(60, 3, -25, 1, "raised") is None


def test_tone_gap_positive_and_negative():
    up = management_vs_media_signal(50, 4, 10, 6, None)
    assert up["severity"] == "watch" and up["title"].startswith("Management more upbeat")
    down = management_vs_media_signal(-10, 4, 30, 6, "maintained")
    assert down["title"].startswith("Market more upbeat")
    assert down["metrics"]["gap"] == -40.0


def test_tone_gap_below_threshold_or_thin_sample_is_silent():
    assert management_vs_media_signal(50, 4, 25, 6, None) is None
    assert management_vs_media_signal(80, 1, 0, 6, None) is None
    assert management_vs_media_signal(80, 4, 0, 1, None) is None


# --- narrative vs price --------------------------------------------------------


def test_narrative_up_price_down():
    s = narrative_vs_price_signal(30, 4, 0, 6, -0.08)
    assert s is not None and "improving" in s["title"]
    assert s["metrics"] == {"sentiment_shift": 30.0, "price_return_pct": -8.0}


def test_narrative_down_price_up():
    s = narrative_vs_price_signal(-10, 4, 20, 6, 0.12)
    assert s is not None and "sours" in s["title"]


@pytest.mark.parametrize(
    "recent, rn, prior, pn, ret",
    [
        (30, 4, 0, 6, -0.02),     # price didn't really move
        (10, 4, 0, 6, -0.10),     # sentiment didn't really shift
        (30, 1, 0, 6, -0.10),     # too few recent mentions
        (30, 4, 0, 1, -0.10),     # too few prior mentions
        (30, 4, 0, 6, None),      # no price data
        (None, 0, 0, 6, -0.10),   # no recent sentiment
        (30, 4, 0, 6, 0.10),      # both up: agreement, not divergence
    ],
)
def test_narrative_vs_price_silent_cases(recent, rn, prior, pn, ret):
    assert narrative_vs_price_signal(recent, rn, prior, pn, ret) is None


# --- crowding ------------------------------------------------------------------


def test_crowded_bullish():
    s = crowding_signal(0.92, 70, 0.15, 12)
    assert s["severity"] == "alert" and s["title"] == "Crowded bullish narrative"
    assert "Top 8%" in s["detail"]


def test_crowded_bearish():
    assert crowding_signal(0.85, -60, 0.2, 8)["title"] == "Crowded bearish narrative"


@pytest.mark.parametrize(
    "pct, sent, nov, n7",
    [
        (0.5, 70, 0.1, 12),    # not enough attention
        (0.9, 20, 0.1, 12),    # not one-sided
        (0.9, 70, 0.6, 12),    # people are saying new things
        (0.9, 70, None, 12),   # novelty unknown -> don't guess
        (0.9, 70, 0.1, 3),     # too few mentions to be a crowd
        (None, 70, 0.1, 12),   # no attention rank
    ],
)
def test_crowding_silent_cases(pct, sent, nov, n7):
    assert crowding_signal(pct, sent, nov, n7) is None
