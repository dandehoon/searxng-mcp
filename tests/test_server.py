"""Unit tests for MCP server logic — no Docker or live SearXNG required."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock, patch

import pytest

import server
from server import SearchResponse, SearchResult, search_web, fetch_url


# ---------------------------------------------------------------------------
# SearchResponse.__str__ — formatting tests (synchronous)
# ---------------------------------------------------------------------------


def test_response_empty():
    resp = SearchResponse(query="test", total=0, shown=0, results=[])
    assert str(resp) == "No results found for: test"


def test_response_single():
    resp = SearchResponse(
        query="hello",
        total=1,
        shown=1,
        results=[
            SearchResult(
                title="Test", url="https://example.com", snippet="Some content"
            )
        ],
    )
    text = str(resp)
    assert "Test" in text
    assert "https://example.com" in text
    assert "Some content" in text
    assert "1." in text


def test_response_multiple():
    resp = SearchResponse(
        query="multi",
        total=3,
        shown=3,
        results=[
            SearchResult(title=f"Title {i}", url=f"https://example.com/{i}", snippet="")
            for i in range(3)
        ],
    )
    text = str(resp)
    assert "1." in text
    assert "2." in text
    assert "3." in text


def test_response_score_shown():
    resp = SearchResponse(
        query="q",
        total=1,
        shown=1,
        results=[
            SearchResult(title="Scored", url="https://x.com", snippet="", score=0.85)
        ],
    )
    assert "0.85" in str(resp)


def test_response_total_count_truncated():
    resp = SearchResponse(
        query="q",
        total=20,
        shown=3,
        results=[
            SearchResult(title=f"R{i}", url=f"https://x.com/{i}", snippet="")
            for i in range(3)
        ],
    )
    assert "3 of 20" in str(resp)


def test_response_no_of_when_not_truncated():
    resp = SearchResponse(
        query="q",
        total=1,
        shown=1,
        results=[SearchResult(title="R", url="https://x.com", snippet="")],
    )
    assert " of " not in str(resp)


# ---------------------------------------------------------------------------
# search_web — async tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_web_propagates_errors():
    """search_web lets exceptions propagate — FastMCP converts them to MCP errors."""
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.side_effect = Exception("connection refused")
        with pytest.raises(Exception, match="connection refused"):
            await search_web(query="test")


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

    assert isinstance(result, SearchResponse)
    assert result.shown == 5
    assert result.total == 20
    assert len(result.results) == 5
    assert "5 of 20" in str(result)


@pytest.mark.asyncio
async def test_search_web_score_rounded():
    fake_results = [
        {
            "title": "X",
            "url": "https://x.com",
            "content": "",
            "score": 2.090909090909091,
        }
    ]
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = {"results": fake_results}
        result = await search_web(query="test")

    assert result.results[0].score == 2.091


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
async def test_fetch_url_propagates_errors():
    """fetch_url lets exceptions propagate — FastMCP converts them to MCP errors."""
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("timeout")
        with pytest.raises(Exception, match="timeout"):
            await fetch_url(url="https://example.com")
