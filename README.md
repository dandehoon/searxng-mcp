# searxng-mcp

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) and a [Model Context Protocol](https://modelcontextprotocol.io) server, exposing web search as an MCP tool.

No separate SearXNG container needed — just run the image.

## Usage

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "searxng": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "ghcr.io/YOUR_USER/searxng-mcp:latest"]
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
      "args": ["run", "--rm", "-i", "ghcr.io/YOUR_USER/searxng-mcp:latest"]
    }
  }
}
```

## Build

```bash
docker build -t searxng-mcp:latest .
```

Then use `searxng-mcp:latest` instead of the registry image above.

## Tool

The image exposes one MCP tool:

| Tool | Description |
|------|-------------|
| `search_web` | Search the web via SearXNG. Returns titles, URLs, and content snippets. |

Parameters: `query` (required), `categories`, `engines`, `language`, `pageno`, `time_range`, `safesearch`, `max_results`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `WARNING` | Python log level for the MCP server |
| `SEARXNG_URL` | `http://127.0.0.1:8080` | SearXNG base URL (internal) |
| `SEARXNG_TIMEOUT` | `30.0` | HTTP timeout in seconds |

## Architecture

```
docker run --rm -i searxng-mcp
    │
    ├── entrypoint.sh
    │       ├── starts granian (SearXNG WSGI server) on 127.0.0.1:8080
    │       ├── waits for /healthz
    │       └── exec → MCP server (STDIO)
    │
    └── MCP server (fastmcp)
            └── search_web tool → httpx → SearXNG JSON API
```

Built on top of `docker.io/searxng/searxng:latest` — no C extension recompilation needed. Updating SearXNG is a single `docker pull` away.

## Development

```bash
make test        # unit tests (no Docker)
make test-all    # build image + E2E test
make lint        # ruff + mypy
```

## License

[MIT](LICENSE)
