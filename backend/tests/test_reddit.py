from app.services.reddit import _html_to_text


def test_html_to_text_strips_tags_and_entities():
    html = "<!-- SC_OFF --><div class=\"md\"><p>NVDA earnings &amp; guidance look <strong>strong</strong>.</p>\n<p>Thoughts?</p></div><!-- SC_ON -->"
    assert _html_to_text(html) == "NVDA earnings & guidance look strong . Thoughts?"


def test_html_to_text_collapses_whitespace():
    assert _html_to_text("<p>a</p>\n\n\n<p>   b   </p>") == "a b"


def test_html_to_text_empty():
    assert _html_to_text("") == ""
    assert _html_to_text(None) == ""


# --- Landing page wiring ---

def test_channel_matches_what_the_poller_stamps():
    """The landing page's post list, top tickers, and track record all key off this
    string, and tasks/reddit_poll.py stamps Sources with the same shape. If the two
    drift apart every panel on the page silently goes empty."""
    from app.routers.reddit import _channel

    assert _channel("wallstreetbets") == "r/wallstreetbets"
    assert _channel("stocks") == "r/stocks"


def test_channel_is_the_key_reliability_groups_by():
    """channel_track_record() looks calls up by channel_key(), so a subreddit's
    track record is only non-empty when _channel() agrees with it."""
    from app.routers.reddit import _channel
    from app.services.reliability import channel_key

    assert channel_key("reddit", _channel("stocks")) == _channel("stocks")
