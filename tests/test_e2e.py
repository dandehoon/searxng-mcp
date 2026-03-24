"""End-to-end test: builds Docker image, starts the container, sends a real MCP
search_web call over stdin/stdout, and verifies results are returned.

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
    line = json.dumps(message) + "\n"
    proc.stdin.write(line.encode())
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, timeout: float = 120.0) -> dict:
    """Read lines from stdout until a JSON object with an 'id' field is found."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            # EOF or process died
            raise RuntimeError("Container stdout closed unexpectedly")
        line = line.decode().strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Skip server-sent notifications (no 'id')
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
) -> http.client.HTTPResponse:
    """Retry an HTTP request until it succeeds or the timeout expires."""
    deadline = time.monotonic() + timeout
    exc: Exception = OSError("Deadline passed before first attempt")
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.request(method, path, **kwargs)
            return conn.getresponse()
        except (http.client.RemoteDisconnected, ConnectionResetError, OSError) as e:
            exc = e
            conn.close()
            time.sleep(0.5)
    raise RuntimeError(f"HTTP {host}:{port}{path} never responded") from exc


@pytest.fixture
def stdio_container():
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", "searxng-mcp:latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.mark.timeout(180)
def test_search_web_e2e(stdio_container):
    """Full E2E: spin up the Docker container, perform an MCP search, validate."""
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

    # 3. Perform a search via tools/call
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search-web",
                "arguments": {
                    "query": "python programming language",
                    "max_results": 3,
                },
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
    assert not text.startswith("Search failed"), (
        f"Search returned an error string: {text}"
    )

    # 4. Fetch a URL via tools/call
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "fetch-url",
                "arguments": {"url": "https://example.com"},
            },
        },
    )

    fetch_response = _read_response(proc, timeout=30.0)
    assert "error" not in fetch_response, (
        f"fetch-url returned an error: {fetch_response.get('error')}"
    )
    fetch_content = fetch_response.get("result", {}).get("content", [])
    assert fetch_content, f"fetch-url result has no content: {fetch_response}"
    fetch_text = fetch_content[0].get("text", "")
    assert fetch_text, "fetch-url response content text is empty"
    # example.com has no <script> or <nav> — just a heading and paragraph
    assert "<html>" not in fetch_text, "Raw HTML leaked into fetch-url output"


@pytest.mark.timeout(180)
def test_http_transport_e2e():
    """E2E: start container in HTTP transport mode, verify the MCP endpoint is reachable."""
    host = "127.0.0.1"
    port = 18000  # use a non-default port to avoid conflicts
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
        # Wait for the TCP port to accept connections (SearXNG + MCP server both up)
        _wait_for_port(host, port, timeout=120.0)

        # Send an MCP initialize request. FastMCP HTTP transport responds with SSE
        # (text/event-stream). We use http.client directly to read chunked SSE data.
        # Retry briefly: the port opens before uvicorn finishes app startup.
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

        resp = _http_retry(host, port, "POST", "/mcp/", body=payload, headers=headers)
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"

        # Read the SSE stream — data lines look like: data: {"jsonrpc":"2.0",...}
        body = resp.read(65536).decode(errors="replace")

        sse_data = None
        for line in body.splitlines():
            if line.startswith("data:"):
                sse_data = line[len("data:") :].strip()
                break

        assert sse_data, f"No SSE data line found in response: {body[:500]}"
        msg = json.loads(sse_data)
        assert (
            msg.get("result", {}).get("serverInfo", {}).get("name") == "searxng-mcp"
        ), f"Unexpected server name in HTTP initialize response: {msg}"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.mark.timeout(60)
def test_startup_time():
    """Measure wall-clock time from docker run to MCP HTTP endpoint readiness."""
    container_id = (
        subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "-e",
                "TRANSPORT=http",
                "-p",
                "0:8000",
                "searxng-mcp:latest",
            ]
        )
        .decode()
        .strip()
    )

    try:
        port_info = (
            subprocess.check_output(["docker", "port", container_id, "8000"])
            .decode()
            .strip()
        )
        assert port_info, (
            "docker port returned empty output — container may have crashed"
        )
        port = int(port_info.split(":")[-1])

        start = time.monotonic()
        deadline = start + 30.0

        while time.monotonic() < deadline:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/healthz")
                resp = conn.getresponse()
                conn.close()
                if resp.status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.1)

        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"Startup took {elapsed:.1f}s (expected < 10s)"

    finally:
        subprocess.run(["docker", "stop", container_id], capture_output=True)


@pytest.mark.timeout(180)
def test_proxy_e2e():
    """E2E: in HTTP transport mode the transparent proxy forwards /healthz to SearXNG."""
    host = "127.0.0.1"
    port = 18001  # distinct port to avoid conflicts with test_http_transport_e2e
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

        resp = _http_retry(host, port, "GET", "/healthz")
        assert resp.status == 200, (
            f"Expected 200 from /healthz proxy, got {resp.status}"
        )
        body = resp.read(512).decode(errors="replace")
        assert "OK" in body, f"Expected 'OK' in /healthz body, got: {body!r}"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
