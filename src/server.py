"""FastMCP server exposing SearXNG search and URL fetching as MCP tools."""

import sys
import logging
import config
import searxng_client
from fastmcp import FastMCP

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)

mcp = FastMCP("searxng-mcp")


def _format_results(results: list, query: str, total: int | None = None) -> str:
    """Format SearXNG result dicts into a readable string."""
    if not results:
        return f"No results found for: {query}"

    shown = len(results)
    count_note = f"{shown} of {total}" if total and total > shown else str(shown)
    header = f"Search results for '{query}' ({count_note} results):\n\n"

    entries = []
    for i, r in enumerate(results):
        score = r.get("score")
        score_str = f" [score: {score:.2f}]" if score is not None else ""
        entry = (
            f"{i + 1}. {r.get('title', 'No title')}{score_str}\n"
            f"   URL: {r.get('url', '')}\n"
            f"   {r.get('content', '').strip()}"
        )
        entries.append(entry)

    return header + "\n\n".join(entries)


@mcp.tool
async def search_web(
    query: str,
    categories: str = "general",
    engines: str | None = None,
    language: str = "auto",
    pageno: int = 1,
    time_range: str | None = None,
    safesearch: int = 0,
    max_results: int = 10,
) -> str:
    """Search the web using SearXNG. Returns titles, URLs, content snippets, and relevance scores."""
    params = {
        "q": query,
        "categories": categories,
        "language": language,
        "pageno": pageno,
        "safesearch": safesearch,
    }
    if engines is not None:
        params["engines"] = engines
    if time_range is not None:
        params["time_range"] = time_range

    try:
        data = await searxng_client.search(params)
        all_results = data.get("results", [])
        results = all_results[:max_results]
        return _format_results(results, query, total=len(all_results))
    except Exception as e:
        return f"Search failed: {type(e).__name__}: {e}"


@mcp.tool
async def fetch_url(url: str) -> str:
    """Fetch the content of a URL and return it as text. Useful for reading pages found via search_web."""
    try:
        return await searxng_client.fetch(url)
    except Exception as e:
        return f"Fetch failed: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run(transport=config.TRANSPORT)
