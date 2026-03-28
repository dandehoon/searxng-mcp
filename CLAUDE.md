# CLAUDE.md — searxng-mcp

Project context for AI assistants working in this repo.

## What this is

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) (self-hosted meta-search engine) and a Python MCP server. Users wire it into Claude Desktop or Cursor with one `docker run` line — no separate SearXNG container needed.

MCP transport defaults to **STDIO** (for Claude Desktop / Cursor). Set `TRANSPORT=http` for an HTTP Streamable endpoint instead.

## Repository layout

```
src/
  config.py           — all env-var config constants (SEARXNG_URL, TRANSPORT, MCP_HOST, …)
  searxng_client.py   — async HTTP client module; init() called once at lifespan start
  server.py           — FastMCP server, tool definitions, lifespan, mcp.run()
config/
  settings.yml        — SearXNG config (JSON API enabled, limiter off, binds 127.0.0.1:8080)
docker/
  entrypoint.sh       — starts granian (SearXNG), waits for /healthz, exec → MCP server
tests/
  test_server.py      — 11 unit tests (no Docker, no live SearXNG)
  test_e2e.py         — 1 E2E test: builds image, runs container, MCP handshake over STDIO
Dockerfile            — FROM searxng/searxng:latest; uv pip install into .venv; cleanup
Makefile              — build, run, dev, lint, test, test-all
pyproject.toml        — deps: fastmcp, httpx, markdownify; dev: ruff, mypy, pytest
```

## MCP tools

| Tool name | Function | Description |
|-----------|----------|-------------|
| `search-web` | `search_web` | Search via SearXNG JSON API; returns `SearchResponse` dataclass |
| `fetch-url` | `fetch_url` | Fetch a URL; converts HTML → Markdown via `markdownify` |

Tool names are **kebab-case** (set via `@mcp.tool(name="...")`).

`SearchResponse` is a dataclass — FastMCP emits both human-readable text (`__str__`) and `structured_content` JSON automatically.

## Key architecture decisions

- **Base image**: `FROM docker.io/searxng/searxng:latest` (Void Linux, Python 3.14). Inherits pre-compiled venv at `/usr/local/searxng/.venv/`. Avoids recompiling C extensions.
- **Package install**: `uv pip install --python /usr/local/searxng/.venv/bin/python` — installs into SearXNG's existing venv.
- **uv/pip cleanup**: Both removed in the same `RUN` layer after install to save ~58MB.
- **Process model**: `entrypoint.sh` starts granian in background, waits for `/healthz`, then `exec`s Python (replacing the shell). In STDIO mode this gives Claude clean stdin/stdout.
- **Granian stdout**: Redirected to stderr (`>&2`) to avoid polluting MCP STDIO stream.
- **HTTP client**: Two persistent `httpx.AsyncClient` instances (search + fetch), created/closed via FastMCP lifespan.
- **Error handling**: Exceptions propagate from tools; FastMCP converts them to MCP error responses.

## Transport modes

**STDIO (default)** — for Claude Desktop / Cursor:
```
docker run --rm -i searxng-mcp:latest
```

**HTTP Streamable** — for remote/multi-client use:
```
docker run --rm -p 8000:8000 -e TRANSPORT=http searxng-mcp:latest
# MCP endpoint: http://localhost:8000/mcp/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT` | `stdio` | `stdio`, `http`, or `streamable-http` |
| `LOG_LEVEL` | `WARNING` | Python log level |
| `SEARXNG_URL` | `http://127.0.0.1:8080` | Internal SearXNG base URL |
| `SEARXNG_TIMEOUT` | `30.0` | HTTP timeout (seconds) |
| `MCP_HOST` | `0.0.0.0` | Bind host for HTTP transport |
| `MCP_PORT` | `8000` | Bind port for HTTP transport |
| `MCP_PATH` | `/mcp/` | URL path for HTTP transport |
| `SEARXNG_CATEGORIES` | `general` | Default search category |
| `SEARXNG_LANGUAGE` | `auto` | Default language code |
| `SEARXNG_MAX_RESULTS` | `20` | Default maximum results to return |
| `SEARXNG_SAFESEARCH` | `0` | Safe search: `0` = off, `1` = moderate, `2` = strict |
| `SEARXNG_TIME_RANGE` | — | Filter by recency: `day`, `week`, `month`, or `year` |
| `SEARXNG_ENGINES` | — | Comma-separated engines to force (e.g. `google,bing`) |

## Development commands

```bash
make install-dev   # uv sync --group dev
make test          # unit tests only (fast, no Docker)
make test-all      # build image + E2E MCP handshake test
make lint          # ruff check + ruff format --check + mypy
make build         # docker build
make run           # build + docker run --rm -i
make dev           # run server locally (needs external SearXNG at SEARXNG_URL)
```

## Gotchas

- The official SearXNG image has `wget` but **not** `curl` — health checks use `wget`.
- Python version in the venv is **3.14** (Void Linux bleeding-edge). Don't hard-code `python3.14` paths; use the venv binary.
- `config/settings.yml` **must** include `search.formats: [html, json]` — without it SearXNG rejects JSON API requests.
- When `exec` replaces the entrypoint shell, the `trap cleanup EXIT` does NOT fire. Granian becomes an orphan but Docker kills all processes on container stop anyway.
- `markdownify` strips `script`, `style`, `head`, `nav`, `footer`, `aside` tags from fetched pages. Adjust the `strip=` list in `server.py:fetch_url` if needed.
- FastMCP version in the image: **3.1.1** (check with `uv pip show fastmcp` inside the venv). The `@mcp.tool(name="...")` decorator syntax requires FastMCP ≥ 2.0.
