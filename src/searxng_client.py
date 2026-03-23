"""Async HTTP client for SearXNG search API and URL fetching."""

import httpx
import config

SEARXNG_SEARCH_URL = config.SEARXNG_URL + "/search"

# Persistent client for SearXNG API calls — initialized via lifespan in server.py.
# Replaced by a real client instance on server startup.
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


async def search(params: dict) -> dict:
    """Call SearXNG /search and return parsed JSON. Always forces format=json."""
    assert _search_client is not None, "searxng_client not initialized"
    response = await _search_client.get(
        SEARXNG_SEARCH_URL, params={"format": "json", **params}
    )
    response.raise_for_status()
    return response.json()


async def fetch(url: str) -> str:
    """Fetch a URL and return the response text."""
    assert _fetch_client is not None, "searxng_client not initialized"
    response = await _fetch_client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.text
