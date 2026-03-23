"""FastMCP server exposing SearXNG search and URL fetching as MCP tools."""

import sys
import logging
from dataclasses import dataclass, field

import config
import searxng_client
from fastmcp import FastMCP

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)

mcp = FastMCP("searxng-mcp")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float | None = None


@dataclass
class SearchResponse:
    query: str
    total: int
    shown: int
    results: list[SearchResult] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.results:
            return f"No results found for: {self.query}"

        count = (
            f"{self.shown} of {self.total}"
            if self.total > self.shown
            else str(self.shown)
        )
        header = f"Search results for '{self.query}' ({count} results):\n\n"

        entries = []
        for i, r in enumerate(self.results):
            score_str = f" [score: {r.score:.2f}]" if r.score is not None else ""
            entries.append(
                f"{i + 1}. {r.title}{score_str}\n   URL: {r.url}\n   {r.snippet}"
            )

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
) -> SearchResponse:
    """Search the web using SearXNG. Returns titles, URLs, content snippets, and relevance scores."""
    params: dict = {
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
    except Exception as e:
        return SearchResponse(
            query=query,
            total=0,
            shown=0,
            results=[
                SearchResult(
                    title="Error",
                    url="",
                    snippet=f"Search failed: {type(e).__name__}: {e}",
                )
            ],
        )

    all_results = data.get("results", [])
    results = [
        SearchResult(
            title=r.get("title", "No title"),
            url=r.get("url", ""),
            snippet=r.get("content", "").strip(),
            score=r.get("score"),
        )
        for r in all_results[:max_results]
    ]
    return SearchResponse(
        query=query, total=len(all_results), shown=len(results), results=results
    )


@mcp.tool
async def fetch_url(url: str) -> str:
    """Fetch the content of a URL and return it as text. Useful for reading pages found via search_web."""
    try:
        return await searxng_client.fetch(url)
    except Exception as e:
        return f"Fetch failed: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run(transport=config.TRANSPORT)
