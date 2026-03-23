"""Async HTTP client for SearXNG search API and URL fetching."""

import httpx
import config

SEARXNG_SEARCH_URL = config.SEARXNG_URL + "/search"

# Persistent client with connection pooling — reused across all tool calls.
_client = httpx.AsyncClient(timeout=config.SEARXNG_TIMEOUT)


async def search(params: dict) -> dict:
    """Call SearXNG /search and return parsed JSON. Always forces format=json."""
    response = await _client.get(
        SEARXNG_SEARCH_URL, params={"format": "json", **params}
    )
    response.raise_for_status()
    return response.json()


async def fetch(url: str) -> str:
    """Fetch a URL and return the response text."""
    response = await _client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.text
