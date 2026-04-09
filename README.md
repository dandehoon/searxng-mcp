# searxng-mcp

A single Docker image that bundles [SearXNG](https://github.com/searxng/searxng) and a [Model Context Protocol](https://modelcontextprotocol.io) server, exposing web search and page fetching as MCP tools.

No separate SearXNG container needed — just run the image.

## Usage

```bash
# STDIO (Claude Code / Cursor / Copilot / OpenCode)
docker run --rm -i dandehoon/searxng-mcp:latest

# HTTP Streamable (remote / multi-client)
docker run --rm -p 8000:8000 -e SEARXNG_MCP_TRANSPORT=http dandehoon/searxng-mcp:latest
```

<details>
<summary>Claude Code</summary>

```bash
claude mcp add --transport stdio searxng -- docker run --rm -i dandehoon/searxng-mcp:latest
```

Or add to `.mcp.json` in your project root (project-scoped) or `~/.claude.json` (user-scoped):

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

</details>

<details>
<summary>GitHub Copilot</summary>

`.vscode/mcp.json` (or `MCP: Open User Configuration` for global):

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

</details>

<details>
<summary>Cursor</summary>

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

</details>

<details>
<summary>OpenCode</summary>

```bash
opencode mcp add searxng -- docker run --rm -i dandehoon/searxng-mcp:latest
```

Or add to `opencode.json` in your project root (or `~/.config/opencode/opencode.json` for global):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "searxng": {
      "type": "local",
      "command": ["docker", "run", "--rm", "-i", "dandehoon/searxng-mcp:latest"]
    }
  }
}
```

</details>

## Build

```bash
# Build with the latest SearXNG image (default)
docker build -t searxng-mcp:latest .

# Pin to a specific SearXNG version
docker build --build-arg SEARXNG_VERSION=2026.3.24-02ba38786 -t searxng-mcp:latest .
```

Then use `searxng-mcp:latest` instead of the registry image in any client config above.

## Tools

| Tool         | Description                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| `search-web` | Search the web via SearXNG. Returns titles, URLs, snippets, and relevance scores. |
| `fetch-web`  | Fetch a URL and return its content as readable Markdown text.                     |

### `search-web` parameters

| Parameter     | Type   | Default              | Description                                           |
| ------------- | ------ | -------------------- | ----------------------------------------------------- |
| `query`       | string | —                    | Search query (required)                               |
| `categories`  | string | `$SEARXNG_CATEGORIES` | SearXNG category (e.g. `news`, `images`)             |
| `language`    | string | `$SEARXNG_LANGUAGE`  | Language code (e.g. `en`, `fr`). `auto` to detect.   |
| `pageno`      | int    | `1`                  | Result page number                                    |
| `max_results` | int    | `$SEARXNG_MCP_MAX_RESULTS` | Maximum results to return                           |

`safesearch`, `time_range`, and `engines` are not exposed as tool parameters — configure them via environment variables instead.

### `fetch-web` parameters

| Parameter | Type   | Description             |
| --------- | ------ | ----------------------- |
| `url`     | string | URL to fetch (required) |

HTML is converted to Markdown before returning — `<script>`, `<style>`, `<nav>`, `<footer>`, and `<aside>` tags are stripped.

## Environment variables

| Variable               | Default                 | Description                                           |
| ---------------------- | ----------------------- | ----------------------------------------------------- |
| `SEARXNG_MCP_TRANSPORT`            | `stdio`                 | Transport mode: `stdio`, `http`, or `streamable-http` |
| `SEARXNG_MCP_LOG_LEVEL`            | `WARNING`               | Python log level for the MCP server                   |
| `SEARXNG_URL`          | `http://127.0.0.1:8080` | SearXNG base URL (internal)                           |
| `SEARXNG_TIMEOUT`      | `30.0`                  | Search HTTP timeout in seconds                        |
| `SEARXNG_MCP_FETCH_TIMEOUT`        | `60.0`                  | URL fetch HTTP timeout in seconds                     |
| `SEARXNG_MCP_HOST`             | `0.0.0.0`               | Bind host (HTTP transport only)                       |
| `SEARXNG_MCP_PORT`             | `8000`                  | Bind port (HTTP transport only)                       |
| `SEARXNG_MCP_PATH`             | `/mcp/`                 | URL path (HTTP transport only)                        |
| `SEARXNG_CATEGORIES`   | `general`               | Default search category                               |
| `SEARXNG_LANGUAGE`     | `auto`                  | Default language code                                 |
| `SEARXNG_MCP_MAX_RESULTS`  | `20`                    | Default maximum results to return                     |
| `SEARXNG_SAFESEARCH`   | `0`                     | Safe search: `0` = off, `1` = moderate, `2` = strict  |
| `SEARXNG_TIME_RANGE`   | —                       | Filter by recency: `day`, `week`, `month`, or `year`  |
| `SEARXNG_ENGINES`      | —                       | Comma-separated engines to force (e.g. `google,bing`) |
| `SEARXNG_MCP_DISABLE_SERVER`   | `false`                 | Skip MCP server; run SearXNG only (container as search backend) |
| `SEARXNG_MCP_DISABLE_FETCH_WEB`    | `false`                 | Remove the `fetch-web` tool from the MCP server       |

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
            └── fetch-web  → httpx → remote URL → markdownify
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
