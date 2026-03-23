#!/bin/sh
# entrypoint.sh — start SearXNG and the MCP server in a single container

set -eu

# Launch SearXNG via granian in the background.
# PYTHONPATH ensures `searx` package is importable from /usr/local/searxng/searx/
# Redirect granian's stdout to stderr so it doesn't pollute the MCP STDIO stream.
PYTHONPATH=/usr/local/searxng python -m granian --interface wsgi searx.webapp:app >&2 &
SEARXNG_PID=$!

MCP_PID=""

# Cleanup handler: kill both processes on SIGTERM/SIGINT
cleanup() {
    if [ -n "$MCP_PID" ]; then
        kill "$MCP_PID" 2>/dev/null || true
        wait "$MCP_PID" 2>/dev/null || true
    fi
    kill "$SEARXNG_PID" 2>/dev/null || true
    wait "$SEARXNG_PID" 2>/dev/null || true
    exit 0
}
trap cleanup TERM INT

# Wait for SearXNG to become ready (max 30 seconds)
ATTEMPTS=0
MAX_ATTEMPTS=30
echo "Waiting for SearXNG to start..." >&2
until curl -sf "http://127.0.0.1:8080/healthz" > /dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: SearXNG failed to start after ${MAX_ATTEMPTS} seconds" >&2
        kill "$SEARXNG_PID" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done
echo "SearXNG is ready" >&2

# Start MCP server (foreground so stdin/stdout are inherited directly)
# Using exec replaces the shell process with the MCP server, which is cleaner
# for STDIO transport — no shell buffering between Docker and the MCP server.
exec python /app/src/server.py
