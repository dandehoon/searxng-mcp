"""FastMCP server exposing SearXNG search and URL fetching as MCP tools."""

import asyncio
import signal
import sys
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal, cast

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from starlette.requests import Request
from starlette.responses import Response

import config
import searxng_client
from fastmcp import FastMCP

HOP_BY_HOP = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    ]
)

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage shared HTTP clients: create on startup, close on shutdown."""
    search_client = httpx.AsyncClient(timeout=config.SEARXNG_TIMEOUT)
    fetch_client = httpx.AsyncClient(
        timeout=config.FETCH_TIMEOUT,
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
    params: dict[str, str | int] = {
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


_STRIP_TAGS = ["script", "style", "head", "nav", "footer", "aside"]


@mcp.tool(name="fetch-url")
async def fetch_url(url: str) -> str:
    """Fetch the content of a URL and return it as readable Markdown text."""
    html = await searxng_client.fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    return markdownify(str(soup))


_TransportLiteral = Literal["stdio", "http", "sse", "streamable-http"]


async def _proxy(request: Request) -> Response:
    path = request.path_params.get("path", "")
    target_url = config.SEARXNG_URL.rstrip("/") + "/" + path
    if request.url.query:
        target_url += "?" + request.url.query

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    body = await request.body()

    resp = await searxng_client.proxy_request(
        method=request.method,
        url=target_url,
        headers=headers,
        content=body,
    )

    resp_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP
    }
    return Response(
        content=resp.content, status_code=resp.status_code, headers=resp_headers
    )


def _register_routes() -> None:
    mcp.custom_route("/", methods=["GET", "POST", "HEAD"])(_proxy)
    mcp.custom_route("/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])(_proxy)


async def _run() -> None:
    if config.TRANSPORT in ("http", "streamable-http", "sse"):
        _register_routes()
    transport = cast(_TransportLiteral, config.TRANSPORT)
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    try:
        if config.TRANSPORT in ("http", "streamable-http", "sse"):
            await mcp.run_async(
                transport=transport,
                host=config.MCP_HOST,
                port=config.MCP_PORT,
                path=config.MCP_PATH,
            )
        else:
            await mcp.run_async(transport=transport)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        pass
