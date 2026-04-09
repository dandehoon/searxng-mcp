"""Unit tests for html_utils — no network or Docker required."""

from bs4 import BeautifulSoup

import html_utils


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# extract_title
# ---------------------------------------------------------------------------


def test_extract_title_from_title_tag():
    soup = _soup("<html><head><title>My Page</title></head><body></body></html>")
    assert html_utils.extract_title(soup, "fallback") == "My Page"


def test_extract_title_falls_back_to_h1():
    soup = _soup("<html><body><h1>Article Heading</h1><p>text</p></body></html>")
    assert html_utils.extract_title(soup, "fallback") == "Article Heading"


def test_extract_title_falls_back_to_url():
    soup = _soup("<html><body><p>no heading here</p></body></html>")
    assert (
        html_utils.extract_title(soup, "https://example.com") == "https://example.com"
    )


def test_extract_title_prefers_title_tag_over_h1():
    soup = _soup(
        "<html><head><title>Title Tag</title></head><body><h1>H1</h1></body></html>"
    )
    assert html_utils.extract_title(soup, "fallback") == "Title Tag"


# ---------------------------------------------------------------------------
# extract_title_from_markdown
# ---------------------------------------------------------------------------


def test_extract_title_from_markdown_frontmatter():
    md = "---\ntitle: Frontmatter Title\n---\n\n# Body\n"
    assert html_utils.extract_title_from_markdown(md, "fallback") == "Frontmatter Title"


def test_extract_title_from_markdown_frontmatter_quoted():
    md = 'title: "Quoted Title"\n\n# Body\n'
    assert html_utils.extract_title_from_markdown(md, "fallback") == "Quoted Title"


def test_extract_title_from_markdown_h1():
    md = "Some intro\n\n# The Real Title\n\nContent here."
    assert html_utils.extract_title_from_markdown(md, "fallback") == "The Real Title"


def test_extract_title_from_markdown_fallback():
    md = "Just plain text with no heading or frontmatter."
    assert (
        html_utils.extract_title_from_markdown(md, "https://x.com") == "https://x.com"
    )


def test_extract_title_from_markdown_frontmatter_before_h1():
    md = "title: FM Title\n\n# H1 Title\n"
    assert html_utils.extract_title_from_markdown(md, "fallback") == "FM Title"


# ---------------------------------------------------------------------------
# find_main_content
# ---------------------------------------------------------------------------


def test_find_main_content_main_element():
    soup = _soup(
        "<body><header>nav</header><main><p>Content</p></main><footer>f</footer></body>"
    )
    node = html_utils.find_main_content(soup)
    assert node.name == "main"
    assert "Content" in node.get_text()


def test_find_main_content_article_element():
    soup = _soup("<body><article><p>Article body</p></article></body>")
    node = html_utils.find_main_content(soup)
    assert node.name == "article"


def test_find_main_content_role_main():
    soup = _soup('<body><div role="main"><p>Role main content</p></div></body>')
    node = html_utils.find_main_content(soup)
    assert node.get_text(strip=True) == "Role main content"


def test_find_main_content_id_main():
    soup = _soup('<body><div id="main"><p>ID main</p></div></body>')
    node = html_utils.find_main_content(soup)
    assert "ID main" in node.get_text()


def test_find_main_content_body_fallback():
    soup = _soup("<body><p>Only body, no landmarks</p></body>")
    node = html_utils.find_main_content(soup)
    assert node.name == "body"


def test_find_main_content_prefers_main_over_article():
    """<main> is listed before <article> in _MAIN_SELECTORS — it wins."""
    soup = _soup(
        "<body><main><p>Main</p></main><article><p>Article</p></article></body>"
    )
    node = html_utils.find_main_content(soup)
    assert node.name == "main"


# ---------------------------------------------------------------------------
# clean_markdown
# ---------------------------------------------------------------------------


def test_clean_markdown_strips_trailing_spaces():
    assert html_utils.clean_markdown("hello   \nworld  \n") == "hello\nworld"


def test_clean_markdown_strips_trailing_tabs():
    assert html_utils.clean_markdown("line\t\nend") == "line\nend"


def test_clean_markdown_collapses_excess_blank_lines():
    text = "a\n\n\n\nb"
    assert html_utils.clean_markdown(text) == "a\n\nb"


def test_clean_markdown_preserves_double_blank_line():
    assert html_utils.clean_markdown("a\n\nb") == "a\n\nb"


def test_clean_markdown_strips_leading_trailing_whitespace():
    assert html_utils.clean_markdown("\n\nhello\n\n") == "hello"


def test_clean_markdown_empty_string():
    assert html_utils.clean_markdown("") == ""


def test_clean_markdown_combined():
    text = "\n  \nfirst line   \n\n\n\nsecond line  \n\n"
    result = html_utils.clean_markdown(text)
    assert result == "first line\n\nsecond line"
