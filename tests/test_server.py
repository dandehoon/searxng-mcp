"""Unit tests for MCP server logic — no Docker or live SearXNG required."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import config
import searxng_client
import server
from server import (
    SearchResponse,
    SearchResult,
    search_web,
    fetch_url,
    _proxy,
)


# ---------------------------------------------------------------------------
# SearchResponse.__str__ — formatting tests (synchronous)
# ---------------------------------------------------------------------------


def test_response_empty():
    resp = SearchResponse(query="test", total=0, shown=0, results=[])
    assert str(resp) == "No results found for: test"


def test_response_single_with_score():
    """Single result with a score: covers basic formatting and score display."""
    resp = SearchResponse(
        query="hello",
        total=1,
        shown=1,
        results=[
            SearchResult(
                title="Test",
                url="https://example.com",
                snippet="Some content",
                score=0.85,
            )
        ],
    )
    text = str(resp)
    assert "Test" in text
    assert "https://example.com" in text
    assert "Some content" in text
    assert "1." in text
    assert "0.85" in text
    # Not truncated — should not show "X of Y"
    assert " of " not in text


def test_response_truncated():
    """When total > shown, the header includes 'X of Y'."""
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


# ---------------------------------------------------------------------------
# search_web — async tool tests
# ---------------------------------------------------------------------------


async def test_search_web_propagates_errors():
    """search_web lets exceptions propagate — FastMCP converts them to MCP errors."""
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.side_effect = Exception("connection refused")
        with pytest.raises(Exception, match="connection refused"):
            await search_web(query="test")


async def test_search_web_max_results_with_scores():
    """Covers truncation, score rounding, and missing-score handling in one test."""
    fake_results = [
        {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": ""}
        for i in range(20)
    ]
    # First result has a score that needs rounding; rest have no score
    fake_results[0]["score"] = 2.090909090909091

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
    # Score rounding: 2.090909... → 2.091
    assert result.results[0].score == 2.091
    # Missing score → None, not displayed
    assert result.results[1].score is None
    assert "[score:" not in str(result).split("\n\n")[2]  # second result entry


# ---------------------------------------------------------------------------
# fetch_url — async tool tests
# ---------------------------------------------------------------------------


async def test_fetch_url_strips_unwanted_tags():
    """All tags in _STRIP_TAGS are removed; main content is preserved."""
    html = (
        "<html><head><title>T</title></head><body>"
        "<nav>Site nav</nav>"
        "<p>Main content</p>"
        "<script>evil()</script>"
        "<style>.x{}</style>"
        "<footer>Footer text</footer>"
        "<aside>Sidebar</aside>"
        "</body></html>"
    )
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = html
        result = await fetch_url(url="https://example.com")

    # Kept
    assert "Main content" in result
    # Stripped tags
    assert "Site nav" not in result
    assert "evil()" not in result
    assert ".x{}" not in result
    assert "Footer text" not in result
    assert "Sidebar" not in result
    # No raw HTML
    assert "<html>" not in result
    assert "<script>" not in result
    assert "<nav>" not in result


async def test_fetch_url_propagates_errors():
    """fetch_url lets exceptions propagate — FastMCP converts them to MCP errors."""
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("timeout")
        with pytest.raises(Exception, match="timeout"):
            await fetch_url(url="https://example.com")


# ---------------------------------------------------------------------------
# _proxy — unit tests (no live SearXNG)
# ---------------------------------------------------------------------------


def _make_request(
    path_params: dict, query: str = "", method: str = "GET", headers: dict | None = None
) -> MagicMock:
    req = MagicMock()
    req.path_params = path_params
    req.url.query = query
    req.method = method
    req.headers.items.return_value = (headers or {}).items()
    req.body = AsyncMock(return_value=b"")
    return req


async def test_proxy_forwards_request():
    """Proxy forwards to SearXNG, handles root path and query strings."""
    mock_resp = httpx.Response(200, content=b"ok")
    req = _make_request({"path": "search"}, query="q=hello&format=json")

    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=mock_resp)
    with patch.object(searxng_client, "get_fetch_client", return_value=mock_client):
        result = await _proxy(req)

    assert result.status_code == 200
    assert result.body == b"ok"
    called_url: str = mock_client.request.call_args.kwargs["url"]
    assert called_url.endswith("?q=hello&format=json")

    # Also verify root path (empty path_params) builds a clean URL
    root_req = _make_request({})
    mock_client.request = AsyncMock(return_value=httpx.Response(200, content=b"root"))
    with patch.object(searxng_client, "get_fetch_client", return_value=mock_client):
        await _proxy(root_req)

    root_url: str = mock_client.request.call_args.kwargs["url"]
    assert root_url == config.SEARXNG_URL + "/"
    assert "//" not in root_url.replace("://", "")


async def test_proxy_strips_hop_by_hop_headers():
    """Hop-by-hop headers are filtered from the proxied response."""
    hop_headers = {
        "transfer-encoding": "chunked",
        "connection": "keep-alive",
        "host": "example.com",
        "x-custom": "keep",
    }
    mock_resp = httpx.Response(200, content=b"", headers=hop_headers)
    req = _make_request({"path": "search"})

    mock_client = MagicMock()
    mock_client.request = AsyncMock(return_value=mock_resp)
    with patch.object(searxng_client, "get_fetch_client", return_value=mock_client):
        result = await _proxy(req)

    result_header_keys = {k.lower() for k in result.headers.keys()}
    for hop in ("transfer-encoding", "connection", "host"):
        assert hop not in result_header_keys
    assert "x-custom" in result_header_keys
