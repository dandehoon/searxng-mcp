"""End-to-end tests: build Docker image, start containers, verify MCP protocol
over both STDIO and HTTP transports.

Prerequisites:
  - Docker daemon is running
  - Image `searxng-mcp:latest` has already been built (`make build`)

Run via:
  make test-all
"""

import http.client
import json
import socket
import subprocess
import time

import pytest


def _send(proc: subprocess.Popen, message: dict) -> None:
    """Write a single JSON-RPC message (NDJSON) to the container's stdin."""
    assert proc.stdin is not None
    line = json.dumps(message) + "\n"
    proc.stdin.write(line.encode())
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, timeout: float = 120.0) -> dict:
    """Read lines from stdout until a JSON object with an 'id' field is found."""
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("Container stdout closed unexpectedly")
        line = line.decode().strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in msg:
            return msg
    raise TimeoutError(f"No JSON-RPC response received within {timeout}s")


def _wait_for_port(host: str, port: int, timeout: float = 60.0) -> None:
    """Poll until a TCP port accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"Port {host}:{port} did not open within {timeout}s")


def _http_retry(
    host: str, port: int, method: str, path: str, *, timeout: float = 30.0, **kwargs
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    """Retry an HTTP request until it succeeds or the timeout expires."""
    deadline = time.monotonic() + timeout
    exc: Exception = OSError("Deadline passed before first attempt")
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.request(method, path, **kwargs)
            return conn, conn.getresponse()
        except (http.client.RemoteDisconnected, ConnectionResetError, OSError) as e:
            exc = e
            conn.close()
            time.sleep(0.5)
    raise RuntimeError(f"HTTP {host}:{port}{path} never responded") from exc


def _terminate(proc: subprocess.Popen) -> None:
    """Gracefully stop a container process."""
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stdio_container():
    """STDIO-mode container for MCP protocol tests."""
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", "searxng-mcp:latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    _terminate(proc)


@pytest.fixture(scope="module")
def http_container():
    """Single HTTP-transport container shared across all HTTP E2E tests."""
    host = "127.0.0.1"
    port = 18000
    proc = subprocess.Popen(
        [
            "docker",
            "run",
            "--rm",
            "-p",
            f"{port}:8000",
            "-e",
            "TRANSPORT=http",
            "searxng-mcp:latest",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_port(host, port, timeout=120.0)
    except Exception:
        _terminate(proc)
        raise
    yield host, port, proc
    _terminate(proc)


# ---------------------------------------------------------------------------
# STDIO transport
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_stdio_e2e(stdio_container):
    """Full E2E: MCP handshake + search-web + fetch-web over STDIO transport."""
    proc = stdio_container

    # 1. MCP initialize handshake
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        },
    )

    init_response = _read_response(proc, timeout=120.0)
    assert (
        init_response.get("result", {}).get("serverInfo", {}).get("name")
        == "searxng-mcp"
    ), f"Unexpected initialize response: {init_response}"

    # 2. Send initialized notification (no response expected)
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )

    # 3. search-web tool call
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search-web",
                "arguments": {"query": "python programming language", "max_results": 3},
            },
        },
    )

    search_response = _read_response(proc, timeout=120.0)
    assert "error" not in search_response, (
        f"tools/call returned an error: {search_response['error']}"
    )
    content = search_response.get("result", {}).get("content", [])
    assert content, f"tools/call result has no content: {search_response}"
    text = content[0].get("text", "")
    assert text, "Response content text is empty"
    assert not text.startswith("Search failed"), f"Search returned an error: {text}"

    # 4a. fetch-web: HTML path — web-scraping.dev is a dedicated scraper test site
    #     with a stable product page, proper <main> element, and known content.
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "fetch-web",
                "arguments": {"url": "https://web-scraping.dev/product/1"},
            },
        },
    )

    fetch_response = _read_response(proc, timeout=30.0)
    assert "error" not in fetch_response, (
        f"fetch-web (HTML) returned an error: {fetch_response.get('error')}"
    )
    fetch_content = fetch_response.get("result", {}).get("content", [])
    assert fetch_content, f"fetch-web (HTML) result has no content: {fetch_response}"
    fetch_text = fetch_content[0].get("text", "")
    assert fetch_text, "fetch-web (HTML) response text is empty"
    assert "<html>" not in fetch_text, "Raw HTML leaked into fetch-web output"
    assert "Box of Chocolate" in fetch_text, (
        "Expected product content not found in fetch-web output"
    )

    # 4b. fetch-web: native markdown path — Cloudflare developer docs respond with
    #     Content-Type: text/markdown when Accept: text/markdown is sent,
    #     which our client sends by default via FETCH_HEADERS.
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "fetch-web",
                "arguments": {
                    "url": "https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/"
                },
            },
        },
    )

    md_response = _read_response(proc, timeout=30.0)
    assert "error" not in md_response, (
        f"fetch-web (markdown) returned an error: {md_response.get('error')}"
    )
    md_content = md_response.get("result", {}).get("content", [])
    assert md_content, f"fetch-web (markdown) result has no content: {md_response}"
    md_text = md_content[0].get("text", "")
    assert md_text, "fetch-web (markdown) response text is empty"
    assert "Markdown" in md_text, (
        "Expected markdown content not found in fetch-web output"
    )
    assert "<html>" not in md_text, "Raw HTML leaked into fetch-web markdown output"


# ---------------------------------------------------------------------------
# HTTP transport (shared container)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_http_transport_e2e(http_container):
    """E2E: verify the MCP endpoint responds to an initialize request over HTTP."""
    host, port, _ = http_container

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    conn, resp = _http_retry(host, port, "POST", "/mcp/", body=payload, headers=headers)
    assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"

    body = resp.read(65536).decode(errors="replace")
    conn.close()

    sse_data = None
    for line in body.splitlines():
        if line.startswith("data:"):
            sse_data = line[len("data:") :].strip()
            break

    assert sse_data, f"No SSE data line found in response: {body[:500]}"
    msg = json.loads(sse_data)
    assert msg.get("result", {}).get("serverInfo", {}).get("name") == "searxng-mcp", (
        f"Unexpected server name in HTTP initialize response: {msg}"
    )


@pytest.mark.timeout(180)
def test_proxy_e2e(http_container):
    """E2E: the transparent proxy forwards /healthz to SearXNG."""
    host, port, _ = http_container

    conn, resp = _http_retry(host, port, "GET", "/healthz")
    assert resp.status == 200, f"Expected 200 from /healthz proxy, got {resp.status}"
    body = resp.read(512).decode(errors="replace")
    conn.close()
    assert "OK" in body, f"Expected 'OK' in /healthz body, got: {body!r}"
