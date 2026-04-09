# searxng-mcp

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) (self-hosted meta-search engine) and a Python [MCP](https://modelcontextprotocol.io) server.

Wire it into Claude Code, Cursor, GitHub Copilot, or OpenCode with one `docker run` line — no separate SearXNG container needed.

## Quick start

```bash
# STDIO (Claude Code / Cursor / Copilot / OpenCode)
docker run --rm -i dandehoon/searxng-mcp:latest

# HTTP Streamable (remote / multi-client)
docker run --rm -p 8000:8000 -e SEARXNG_MCP_TRANSPORT=http dandehoon/searxng-mcp:latest
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
| `categories` | string | `$SEARXNG_CATEGORIES` | SearXNG category (e.g. `news`, `images`) |
| `language` | string | `$SEARXNG_LANGUAGE` | Language code (e.g. `en`, `fr`). `auto` to detect. |
| `pageno` | int | `1` | Result page number |
| `max_results` | int | `$SEARXNG_MCP_MAX_RESULTS` | Maximum results to return |

`safesearch`, `time_range`, and `engines` are not exposed as tool parameters — configure them via environment variables instead.

### `fetch-web`

Fetch a URL and return its content as readable Markdown. Scripts, nav, footer, and sidebar elements are stripped automatically.

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | URL to fetch (required) |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_MCP_TRANSPORT` | `stdio` | `stdio`, `http`, or `streamable-http` |
| `SEARXNG_MCP_LOG_LEVEL` | `WARNING` | Python log level |
| `SEARXNG_TIMEOUT` | `30.0` | Search HTTP timeout (seconds) |
| `SEARXNG_MCP_FETCH_TIMEOUT` | `60.0` | URL fetch HTTP timeout (seconds) |
| `SEARXNG_MCP_HOST` | `0.0.0.0` | Bind host (HTTP transport only) |
| `SEARXNG_MCP_PORT` | `8000` | Bind port (HTTP transport only) |
| `SEARXNG_MCP_PATH` | `/mcp/` | URL path (HTTP transport only) |
| `SEARXNG_CATEGORIES` | `general` | Default search category |
| `SEARXNG_LANGUAGE` | `auto` | Default language code |
| `SEARXNG_MCP_MAX_RESULTS` | `20` | Default maximum results to return |
| `SEARXNG_SAFESEARCH` | `0` | Safe search: `0` = off, `1` = moderate, `2` = strict |
| `SEARXNG_TIME_RANGE` | — | Filter by recency: `day`, `week`, `month`, or `year` |
| `SEARXNG_ENGINES` | — | Comma-separated engines to force (e.g. `google,bing`) |

## Source

[github.com/dandehoon/searxng-mcp](https://github.com/dandehoon/searxng-mcp)
