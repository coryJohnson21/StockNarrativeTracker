from app.services.reddit import _html_to_text


def test_html_to_text_strips_tags_and_entities():
    html = "<!-- SC_OFF --><div class=\"md\"><p>NVDA earnings &amp; guidance look <strong>strong</strong>.</p>\n<p>Thoughts?</p></div><!-- SC_ON -->"
    assert _html_to_text(html) == "NVDA earnings & guidance look strong . Thoughts?"


def test_html_to_text_collapses_whitespace():
    assert _html_to_text("<p>a</p>\n\n\n<p>   b   </p>") == "a b"


def test_html_to_text_empty():
    assert _html_to_text("") == ""
    assert _html_to_text(None) == ""
