"""Unit tests for MCP server logic — no Docker or live SearXNG required."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
    HOP_BY_HOP,
)


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
        mock_fetch.return_value = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        result = await fetch_url(url="https://example.com")
    # markdownify converts HTML headings and paragraphs to markdown
    assert "Hello" in result
    assert "World" in result
    assert "<html>" not in result


@pytest.mark.asyncio
async def test_fetch_url_propagates_errors():
    """fetch_url lets exceptions propagate — FastMCP converts them to MCP errors."""
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("timeout")
        with pytest.raises(Exception, match="timeout"):
            await fetch_url(url="https://example.com")


@pytest.mark.asyncio
async def test_fetch_url_strips_script_tags():
    html = "<html><body><p>Keep this</p><script>evil()</script></body></html>"
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = html
        result = await fetch_url(url="https://example.com")
    assert "Keep this" in result
    assert "evil()" not in result
    assert "<script>" not in result


@pytest.mark.asyncio
async def test_fetch_url_strips_nav_and_footer():
    html = (
        "<html><body>"
        "<nav>Site nav</nav>"
        "<p>Main content</p>"
        "<footer>Footer text</footer>"
        "</body></html>"
    )
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = html
        result = await fetch_url(url="https://example.com")
    assert "Main content" in result
    assert "Site nav" not in result
    assert "Footer text" not in result


@pytest.mark.asyncio
async def test_fetch_url_converts_headings_to_markdown():
    html = "<html><body><h1>Big Title</h1><h2>Subtitle</h2></body></html>"
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = html
        result = await fetch_url(url="https://example.com")
    assert "Big Title" in result
    assert "Subtitle" in result
    # markdownify uses setext (underline) style for h1/h2 by default,
    # or ATX (#) style — either way, no raw <h1> tags remain
    assert "<h1>" not in result
    assert "<h2>" not in result


@pytest.mark.asyncio
async def test_fetch_url_converts_links_to_markdown():
    html = '<html><body><a href="https://example.com">Example</a></body></html>'
    with patch.object(
        server.searxng_client, "fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = html
        result = await fetch_url(url="https://example.com")
    assert "Example" in result
    assert "https://example.com" in result
    assert "<a " not in result


# ---------------------------------------------------------------------------
# config — env var defaults and overrides
# ---------------------------------------------------------------------------


def test_config_mcp_defaults():
    """MCP_HOST/PORT/PATH should have sensible defaults when env vars are absent."""
    assert config.MCP_HOST == "0.0.0.0"
    assert config.MCP_PORT == 8000
    assert config.MCP_PATH == "/mcp/"


def test_config_mcp_port_from_env(monkeypatch):
    """MCP_PORT env var is parsed as int."""
    monkeypatch.setenv("MCP_PORT", "9000")
    import importlib

    importlib.reload(config)
    try:
        assert config.MCP_PORT == 9000
    finally:
        monkeypatch.delenv("MCP_PORT", raising=False)
        importlib.reload(config)


def test_config_transport_default():
    assert config.TRANSPORT == "stdio"


# ---------------------------------------------------------------------------
# search_web — missing score field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_web_no_score_field():
    """Results without a 'score' key should have score=None (not crash)."""
    fake_results = [{"title": "No score", "url": "https://x.com", "content": "text"}]
    with patch.object(
        server.searxng_client, "search", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = {"results": fake_results}
        result = await search_web(query="test")
    assert result.results[0].score is None
    assert "[score:" not in str(result)


# ---------------------------------------------------------------------------
# HOP_BY_HOP constant
# ---------------------------------------------------------------------------


def test_hop_by_hop_constant():
    for header in ("connection", "host", "transfer-encoding", "upgrade"):
        assert header in HOP_BY_HOP


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


@pytest.mark.asyncio
async def test_proxy_forwards_request():
    mock_resp = httpx.Response(200, content=b"ok")
    req = _make_request({"path": "search"}, query="q=test")

    with patch.object(
        searxng_client, "proxy_request", new=AsyncMock(return_value=mock_resp)
    ):
        result = await _proxy(req)

    assert result.status_code == 200
    assert result.body == b"ok"


@pytest.mark.asyncio
async def test_proxy_strips_hop_by_hop_headers():
    hop_headers = {
        "transfer-encoding": "chunked",
        "connection": "keep-alive",
        "host": "example.com",
        "x-custom": "keep",
    }
    mock_resp = httpx.Response(200, content=b"", headers=hop_headers)
    req = _make_request({"path": "search"})

    with patch.object(
        searxng_client, "proxy_request", new=AsyncMock(return_value=mock_resp)
    ):
        result = await _proxy(req)

    result_header_keys = {k.lower() for k in result.headers.keys()}
    for hop in ("transfer-encoding", "connection", "host"):
        assert hop not in result_header_keys
    assert "x-custom" in result_header_keys


@pytest.mark.asyncio
async def test_proxy_root_path():
    mock_resp = httpx.Response(200, content=b"root")
    req = _make_request({})  # empty path_params — root route

    mock_proxy = AsyncMock(return_value=mock_resp)
    with patch.object(searxng_client, "proxy_request", new=mock_proxy):
        await _proxy(req)

    called_url: str = mock_proxy.call_args.kwargs["url"]
    assert called_url == config.SEARXNG_URL.rstrip("/") + "/"
    assert "//" not in called_url.replace("://", "")


@pytest.mark.asyncio
async def test_proxy_passes_query_string():
    mock_resp = httpx.Response(200, content=b"")
    req = _make_request({"path": "search"}, query="q=hello&format=json")

    mock_proxy = AsyncMock(return_value=mock_resp)
    with patch.object(searxng_client, "proxy_request", new=mock_proxy):
        await _proxy(req)

    called_url: str = mock_proxy.call_args.kwargs["url"]
    assert called_url.endswith("?q=hello&format=json")
