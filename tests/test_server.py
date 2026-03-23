"""Unit tests for MCP server logic — no Docker or live SearXNG required."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, patch

import pytest

import server
from server import _format_results, search_web, fetch_url


# ---------------------------------------------------------------------------
# _format_results — pure-function tests (synchronous)
# ---------------------------------------------------------------------------


def test_format_results_empty():
    result = _format_results([], "test query")
    assert result == "No results found for: test query"


def test_format_results_single():
    results = [
        {"title": "Test", "url": "https://example.com", "content": "Some content"}
    ]
    output = _format_results(results, "hello")
    assert "Test" in output
    assert "https://example.com" in output
    assert "Some content" in output
    assert "1." in output


def test_format_results_multiple():
    results = [
        {"title": f"Title {i}", "url": f"https://example.com/{i}", "content": ""}
        for i in range(3)
    ]
    output = _format_results(results, "multi")
    assert "1." in output
    assert "2." in output
    assert "3." in output


def test_format_results_header():
    results = [
        {"title": "A", "url": "https://a.com", "content": ""},
        {"title": "B", "url": "https://b.com", "content": ""},
    ]
    output = _format_results(results, "my query")
    assert "my query" in output
    assert "2" in output


def test_format_results_score_shown():
    results = [
        {"title": "Scored", "url": "https://x.com", "content": "", "score": 0.85}
    ]
    output = _format_results(results, "q")
    assert "0.85" in output


def test_format_results_total_count():
    """Shows 'X of Y' when total exceeds shown results."""
    results = [
        {"title": f"R{i}", "url": f"https://x.com/{i}", "content": ""} for i in range(3)
    ]
    output = _format_results(results, "q", total=20)
    assert "3 of 20" in output


def test_format_results_no_total_when_equal():
    """Shows plain count when all results are shown."""
    results = [{"title": "R", "url": "https://x.com", "content": ""}]
    output = _format_results(results, "q", total=1)
    assert "of" not in output


# ---------------------------------------------------------------------------
# search_web — async tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_web_error_handling():
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.side_effect = Exception("connection refused")
        result = await search_web(query="test")
    assert result.startswith("Search failed:")


@pytest.mark.asyncio
async def test_search_web_max_results():
    fake_results = [
        {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": ""}
        for i in range(20)
    ]
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = {"results": fake_results}
        result = await search_web(query="test", max_results=5)

    for n in range(1, 6):
        assert f"{n}." in result
    assert "6." not in result
    # Should show "5 of 20"
    assert "5 of 20" in result


# ---------------------------------------------------------------------------
# fetch_url — async tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_url_returns_content():
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = "<html>hello</html>"
        result = await fetch_url(url="https://example.com")
    assert result == "<html>hello</html>"


@pytest.mark.asyncio
async def test_fetch_url_error_handling():
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("timeout")
        result = await fetch_url(url="https://example.com")
    assert result.startswith("Fetch failed:")
