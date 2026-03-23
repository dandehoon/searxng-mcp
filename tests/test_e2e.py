"""End-to-end test: builds Docker image, starts the container, sends a real MCP
search_web call over stdin/stdout, and verifies results are returned.

Prerequisites:
  - Docker daemon is running
  - Image `searxng-mcp:latest` has already been built (`make build`)

Run via:
  make test-all
"""

import json
import subprocess
import time


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


def test_search_web_e2e():
    """Full E2E: spin up the Docker container, perform an MCP search, validate."""
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", "searxng-mcp:latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
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

    finally:
        proc.kill()
        proc.wait()
