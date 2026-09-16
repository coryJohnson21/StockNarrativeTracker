from app.services.sec_edgar import _strip_html_to_text


def test_strips_tags_and_collapses_whitespace():
    html = "<html><body><h1>Q3   Results</h1>\n\n<p>Revenue   grew\n15%.</p></body></html>"
    assert _strip_html_to_text(html) == "Q3 Results Revenue grew 15%."


def test_removes_script_and_style_content():
    html = (
        "<html><head><style>body { color: red; }</style></head>"
        "<body><script>var x = 1;</script><p>Net income</p></body></html>"
    )
    assert _strip_html_to_text(html) == "Net income"


def test_adjacent_cells_do_not_merge_into_one_token():
    html = "<table><tr><td>Revenue</td><td>$81.6B</td></tr></table>"
    assert _strip_html_to_text(html) == "Revenue $81.6B"


def test_empty_document():
    assert _strip_html_to_text("") == ""
    assert _strip_html_to_text("<html><body></body></html>") == ""
