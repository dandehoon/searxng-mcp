"""FastMCP server exposing SearXNG search and URL fetching as MCP tools."""

import asyncio
import signal
import sys
import logging
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from pydantic import Field
from starlette.requests import Request
from starlette.responses import Response

import config
import html_utils
import searxng_client
from fastmcp import FastMCP

HOP_BY_HOP = frozenset(
    {
        "connection",
        "content-encoding",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)

_VALID_TRANSPORTS = frozenset({"stdio", "http", "streamable-http"})

logging.basicConfig(level=config.LOG_LEVEL, stream=sys.stderr)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage shared HTTP clients: create on startup, close on shutdown."""
    search_client = httpx.AsyncClient(timeout=config.SEARXNG_TIMEOUT)
    fetch_client = httpx.AsyncClient(
        timeout=config.FETCH_TIMEOUT,
        headers=config.FETCH_HEADERS,
    )
    try:
        searxng_client.init(search_client, fetch_client)
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
    query: Annotated[str, Field(description="The search query string.")],
    categories: Annotated[
        str,
        Field(
            description=f"SearXNG search category. Dynamic — depends on enabled engines (e.g. 'general', 'news', 'images', etc.). Default: '{config.SEARXNG_CATEGORIES}'."
        ),
    ] = config.SEARXNG_CATEGORIES,
    language: Annotated[
        str,
        Field(
            description=f"Language code for results (e.g. 'en', 'fr', 'de'). Use 'auto' to detect from the query. Default: '{config.SEARXNG_LANGUAGE}'."
        ),
    ] = config.SEARXNG_LANGUAGE,
    pageno: Annotated[
        int, Field(description="Page number for pagination, starting at 1.")
    ] = 1,
    max_results: Annotated[
        int,
        Field(
            description=f"Maximum number of results to return. Applied client-side after fetching. Default: {config.SEARXNG_MAX_RESULTS}."
        ),
    ] = config.SEARXNG_MAX_RESULTS,
) -> str:
    """Search the web via SearXNG and return ranked results with titles, URLs, snippets, and relevance scores."""
    params: dict[str, str | int] = {
        "q": query,
        "categories": categories,
        "language": language,
        "pageno": pageno,
        "safesearch": config.SEARXNG_SAFESEARCH,
    }
    if config.SEARXNG_ENGINES is not None:
        params["engines"] = config.SEARXNG_ENGINES
    if config.SEARXNG_TIME_RANGE is not None:
        params["time_range"] = config.SEARXNG_TIME_RANGE

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
    return str(
        SearchResponse(
            query=query, total=len(all_results), shown=len(results), results=results
        )
    )


@dataclass
class FetchResponse:
    url: str
    title: str
    content: str

    def __str__(self) -> str:
        return f"Title: {self.title}\nURL: {self.url}\n\n{self.content}"


@mcp.tool(name="fetch-web")
async def fetch_web(
    url: Annotated[str, Field(description="The URL to fetch.")],
) -> str:
    """Fetch a URL and return its title, URL, and main content as clean Markdown."""
    body, content_type = await searxng_client.fetch(url)
    if "text/markdown" in content_type:
        title = html_utils.extract_title_from_markdown(body, url)
        content = html_utils.clean_markdown(body)
    else:
        soup = BeautifulSoup(body, "html.parser")
        title = html_utils.extract_title(soup, url)
        for tag in soup(html_utils.STRIP_TAGS):
            tag.decompose()
        for tag in soup.select(html_utils.STRIP_SELECTORS_STR):
            tag.decompose()
        content_node = html_utils.find_main_content(soup)
        content = html_utils.clean_markdown(
            MarkdownConverter().convert_soup(content_node)
        )
    return str(FetchResponse(url=url, title=title, content=content))


if config.DISABLE_FETCH_WEB:
    mcp.local_provider.remove_tool("fetch-web")


def _build_target_url(request: Request) -> str:
    path = request.path_params.get("path", "")
    url = config.SEARXNG_URL + "/" + path
    if request.url.query:
        url += "?" + request.url.query
    return url


def _filter_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}


async def _proxy(request: Request) -> Response:
    resp = await searxng_client.get_fetch_client().request(
        method=request.method,
        url=_build_target_url(request),
        headers=_filter_headers(request.headers),
        content=await request.body(),
        follow_redirects=True,
    )
    return Response(resp.content, resp.status_code, _filter_headers(resp.headers))


def _register_routes() -> None:
    mcp.custom_route("/", methods=["GET", "POST", "HEAD"])(_proxy)
    mcp.custom_route("/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])(_proxy)


async def _run() -> None:
    if config.TRANSPORT not in _VALID_TRANSPORTS:
        raise ValueError(
            f"Unknown TRANSPORT={config.TRANSPORT!r}, must be one of {sorted(_VALID_TRANSPORTS)}"
        )
    is_http = config.TRANSPORT in ("http", "streamable-http")
    if is_http:
        _register_routes()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    try:
        if is_http:
            await mcp.run_async(
                transport=config.TRANSPORT,  # type: ignore[arg-type]
                host=config.MCP_HOST,
                port=config.MCP_PORT,
                path=config.MCP_PATH,
            )
        else:
            await mcp.run_async(transport=config.TRANSPORT)  # type: ignore[arg-type]
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        pass
