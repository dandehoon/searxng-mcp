# searxng-mcp

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) and a [Model Context Protocol](https://modelcontextprotocol.io) server, exposing web search and page fetching as MCP tools.

No separate SearXNG container needed — just run the image.

## Usage

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "searxng": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "dandehoon/searxng-mcp:latest"]
    }
  }
}
```

### Cursor

`.cursor/mcp.json` (or `~/.cursor/mcp.json` for global):

```json
{
  "mcpServers": {
    "searxng": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "dandehoon/searxng-mcp:latest"]
    }
  }
}
```

### HTTP Streamable (remote / multi-client)

```bash
docker run --rm -p 8000:8000 -e TRANSPORT=http dandehoon/searxng-mcp:latest
# MCP endpoint: http://localhost:8000/mcp/
```

## Build

```bash
docker build -t searxng-mcp:latest .
```

Then use `searxng-mcp:latest` instead of the registry image above.

## Tools

| Tool | Description |
|------|-------------|
| `search-web` | Search the web via SearXNG. Returns titles, URLs, snippets, and relevance scores. |
| `fetch-url` | Fetch a URL and return its content as readable Markdown text. |

### `search-web` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | — | Search query (required) |
| `categories` | string | `general` | SearXNG category (e.g. `news`, `images`) |
| `engines` | string | — | Comma-separated engine list |
| `language` | string | `auto` | Language code |
| `pageno` | int | `1` | Result page number |
| `time_range` | string | — | `day`, `month`, or `year` |
| `safesearch` | int | `0` | `0` = off, `1` = moderate, `2` = strict |
| `max_results` | int | `10` | Maximum results to return |

### `fetch-url` parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | URL to fetch (required) |

HTML is converted to Markdown before returning — `<script>`, `<style>`, `<nav>`, `<footer>`, and `<aside>` tags are stripped.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT` | `stdio` | Transport mode: `stdio`, `http`, or `streamable-http` |
| `LOG_LEVEL` | `WARNING` | Python log level for the MCP server |
| `SEARXNG_URL` | `http://127.0.0.1:8080` | SearXNG base URL (internal) |
| `SEARXNG_TIMEOUT` | `30.0` | Search HTTP timeout in seconds |
| `FETCH_TIMEOUT` | `60.0` | URL fetch HTTP timeout in seconds |
| `MCP_HOST` | `0.0.0.0` | Bind host (HTTP transport only) |
| `MCP_PORT` | `8000` | Bind port (HTTP transport only) |
| `MCP_PATH` | `/mcp/` | URL path (HTTP transport only) |

## Architecture

```
docker run --rm -i searxng-mcp
    │
    ├── entrypoint.sh
    │       ├── starts granian (SearXNG WSGI server) on 127.0.0.1:8080
    │       ├── waits for /healthz
    │       └── exec → MCP server (STDIO or HTTP)
    │
    └── MCP server (fastmcp)
            ├── search-web → httpx → SearXNG JSON API
            └── fetch-url  → httpx → remote URL → markdownify
```

Built on top of `docker.io/searxng/searxng:latest` — no C extension recompilation needed. Updating SearXNG is a single `docker pull` away.

## Development

```bash
make install-dev   # install dev dependencies
make test          # unit tests (no Docker)
make test-all      # build image + E2E MCP handshake test
make lint          # ruff + mypy
```

## License

[MIT](LICENSE)
