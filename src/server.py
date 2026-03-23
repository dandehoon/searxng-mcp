"""FastMCP server exposing SearXNG search and URL fetching as MCP tools."""

import sys
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal, cast

import httpx
from markdownify import markdownify

import config
import searxng_client
from fastmcp import FastMCP

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage shared HTTP clients: create on startup, close on shutdown."""
    search_client = httpx.AsyncClient(timeout=config.SEARXNG_TIMEOUT)
    fetch_client = httpx.AsyncClient(
        timeout=config.SEARXNG_TIMEOUT,
        headers=searxng_client.FETCH_HEADERS,
    )
    searxng_client.init(search_client, fetch_client)
    try:
        yield
    finally:
        await search_client.aclose()
        await fetch_client.aclose()


mcp = FastMCP("searxng-mcp", lifespan=lifespan)


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
            score_str = f" [score: {r.score}]" if r.score is not None else ""
            entries.append(
                f"{i + 1}. {r.title}{score_str}\n   URL: {r.url}\n   {r.snippet}"
            )

        return header + "\n\n".join(entries)


@mcp.tool(name="search-web")
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

    data = await searxng_client.search(params)
    all_results = data.get("results", [])
    results = [
        SearchResult(
            title=r.get("title", "No title"),
            url=r.get("url", ""),
            snippet=r.get("content", "").strip(),
            score=round(r["score"], 3) if r.get("score") is not None else None,
        )
        for r in all_results[:max_results]
    ]
    return SearchResponse(
        query=query, total=len(all_results), shown=len(results), results=results
    )


@mcp.tool(name="fetch-url")
async def fetch_url(url: str) -> str:
    """Fetch the content of a URL and return it as readable Markdown text."""
    html = await searxng_client.fetch(url)
    return markdownify(
        html, strip=["script", "style", "head", "nav", "footer", "aside"]
    )


_TransportLiteral = Literal["stdio", "http", "sse", "streamable-http"]

if __name__ == "__main__":
    transport = cast(_TransportLiteral, config.TRANSPORT)
    if config.TRANSPORT in ("http", "streamable-http"):
        mcp.run(
            transport=transport,
            host=config.MCP_HOST,
            port=config.MCP_PORT,
            path=config.MCP_PATH,
        )
    else:
        mcp.run(transport=transport)
