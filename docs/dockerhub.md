# searxng-mcp

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) (self-hosted meta-search engine) and a Python [MCP](https://modelcontextprotocol.io) server.

Wire it into Claude Code, Cursor, GitHub Copilot, or OpenCode with one `docker run` line — no separate SearXNG container needed.

## Quick start

```bash
# STDIO (Claude Code / Cursor / Copilot / OpenCode)
docker run --rm -i dandehoon/searxng-mcp:latest

# HTTP Streamable (remote / multi-client)
docker run --rm -p 8000:8000 -e TRANSPORT=http dandehoon/searxng-mcp:latest
```

**Claude Code**:

```bash
claude mcp add --transport stdio searxng -- docker run --rm -i dandehoon/searxng-mcp:latest
```

**OpenCode**:

```bash
opencode mcp add searxng -- docker run --rm -i dandehoon/searxng-mcp:latest
```

**Cursor** — `.cursor/mcp.json`:

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

**GitHub Copilot (VS Code)** — `.vscode/mcp.json`:

```json
{
  "servers": {
    "searxng": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "dandehoon/searxng-mcp:latest"]
    }
  }
}
```

## MCP tools

### `search-web`

Search the web via SearXNG. Returns titles, URLs, snippets, and relevance scores.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | — | Search query (required) |
| `categories` | string | `general` | SearXNG category (e.g. `news`, `science`) |
| `engines` | string | — | Comma-separated engine list |
| `language` | string | `auto` | Language code |
| `pageno` | int | `1` | Result page number |
| `time_range` | string | — | `day`, `month`, or `year` |
| `safesearch` | int | `0` | `0` = off, `1` = moderate, `2` = strict |
| `max_results` | int | `10` | Maximum results to return |

### `fetch-url`

Fetch a URL and return its content as readable Markdown. Scripts, nav, footer, and sidebar elements are stripped automatically.

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | URL to fetch (required) |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT` | `stdio` | `stdio`, `http`, or `streamable-http` |
| `LOG_LEVEL` | `WARNING` | Python log level |
| `SEARXNG_TIMEOUT` | `30.0` | Search HTTP timeout (seconds) |
| `FETCH_TIMEOUT` | `60.0` | URL fetch HTTP timeout (seconds) |
| `MCP_HOST` | `0.0.0.0` | Bind host (HTTP transport only) |
| `MCP_PORT` | `8000` | Bind port (HTTP transport only) |
| `MCP_PATH` | `/mcp/` | URL path (HTTP transport only) |

## Source

[github.com/dandehoon/searxng-mcp](https://github.com/dandehoon/searxng-mcp)
