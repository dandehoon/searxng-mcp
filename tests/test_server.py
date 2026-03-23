"""Unit tests for MCP server logic — no Docker or live SearXNG required."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, patch

import pytest

import server
from server import _format_results, search_web


# ---------------------------------------------------------------------------
# _format_results — pure-function tests (synchronous)
# ---------------------------------------------------------------------------


def test_format_results_empty():
    result = _format_results([], "test query")
    assert result == "No results found for: test query"


def test_format_results_single():
    results = [
        {
            "title": "Test",
            "url": "https://example.com",
            "content": "Some content",
        }
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
    assert "2" in output  # result count appears in header


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

    # Only entries "1." through "5." should appear; "6." must not
    for n in range(1, 6):
        assert f"{n}." in result
    assert "6." not in result
