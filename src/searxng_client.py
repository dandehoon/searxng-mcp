"""Async HTTP client for SearXNG search API and URL fetching."""

from typing import Any

import httpx
import config

_search_client: httpx.AsyncClient | None = None
_fetch_client: httpx.AsyncClient | None = None

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; searxng-mcp/1.0; +https://github.com/searxng/searxng-mcp)"
    )
}


def init(search_client: httpx.AsyncClient, fetch_client: httpx.AsyncClient) -> None:
    """Called once at server startup to set the shared HTTP clients."""
    global _search_client, _fetch_client
    _search_client = search_client
    _fetch_client = fetch_client


async def search(params: dict[str, str | int]) -> dict[str, Any]:
    """Call SearXNG /search and return parsed JSON. Always forces format=json."""
    if _search_client is None:
        raise RuntimeError("searxng_client not initialized")
    url = config.SEARXNG_URL + "/search"
    response = await _search_client.get(url, params={**params, "format": "json"})
    response.raise_for_status()
    return response.json()


async def fetch(url: str) -> str:
    """Fetch a URL and return the response text."""
    if _fetch_client is None:
        raise RuntimeError("searxng_client not initialized")
    response = await _fetch_client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.text


def get_fetch_client() -> httpx.AsyncClient:
    """Return the shared fetch client (for HTTP proxying in server.py)."""
    if _fetch_client is None:
        raise RuntimeError("searxng_client not initialized")
    return _fetch_client
