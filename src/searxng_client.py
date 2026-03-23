"""Async HTTP client for SearXNG search API."""

import httpx
import config

SEARXNG_SEARCH_URL = config.SEARXNG_URL + config.SEARXNG_SEARCH_PATH


async def search(params: dict) -> dict:
    """Call SearXNG /search and return parsed JSON. Always forces format=json."""
    query_params = {"format": "json", **params}
    async with httpx.AsyncClient(timeout=config.SEARXNG_TIMEOUT) as client:
        response = await client.get(SEARXNG_SEARCH_URL, params=query_params)
        response.raise_for_status()
        return response.json()
