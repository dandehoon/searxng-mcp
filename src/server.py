"""FastMCP server exposing SearXNG search as an MCP tool."""

import sys
import logging
import config
import searxng_client
from fastmcp import FastMCP

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)

mcp = FastMCP("searxng-mcp")


def _format_results(results: list, query: str) -> str:
    """Format a list of SearXNG result dicts into a readable string."""
    if not results:
        return f"No results found for: {query}"

    header = f"Search results for '{query}' ({len(results)} results):\n\n"
    entries = [
        f"{i + 1}. {result.get('title', 'No title')}\n"
        f"   URL: {result.get('url', '')}\n"
        f"   {result.get('content', '').strip()}"
        for i, result in enumerate(results)
    ]
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
    """Search the web using SearXNG. Returns a formatted list of results with titles, URLs, and content snippets."""
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
        results = data.get("results", [])[:max_results]
        return _format_results(results, query)
    except Exception as e:
        return f"Search failed: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run(transport=config.TRANSPORT)
