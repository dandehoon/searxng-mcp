#!/bin/sh
# entrypoint.sh — start SearXNG and the MCP server in a single container.
# Runs on Void Linux (the official searxng/searxng base image).

set -eu

VENV=/usr/local/searxng/.venv
SEARXNG_SETTINGS_PATH=${SEARXNG_SETTINGS_PATH:-/etc/searxng/settings.yml}

# Ensure settings file exists (official image creates it from template if missing)
if [ ! -f "$SEARXNG_SETTINGS_PATH" ]; then
    cp -f /usr/local/searxng/searx/settings.yml "$SEARXNG_SETTINGS_PATH"
    echo "Created settings from template: $SEARXNG_SETTINGS_PATH" >&2
fi

# Launch SearXNG via granian in the background.
# Redirect granian's stdout to stderr so it doesn't pollute the MCP STDIO stream.
PYTHONPATH=/usr/local/searxng \
    SEARXNG_SETTINGS_PATH="$SEARXNG_SETTINGS_PATH" \
    "$VENV/bin/granian" searx.webapp:app >&2 &
SEARXNG_PID=$!

# Cleanup handler: kill SearXNG when the MCP server exits
cleanup() {
    kill "$SEARXNG_PID" 2>/dev/null || true
    wait "$SEARXNG_PID" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

# Wait for SearXNG to become ready (max 30 seconds)
ATTEMPTS=0
MAX_ATTEMPTS=30
echo "Waiting for SearXNG to start..." >&2
until wget -q -O /dev/null "http://127.0.0.1:8080/healthz" 2>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: SearXNG failed to start after ${MAX_ATTEMPTS} seconds" >&2
        exit 1
    fi
    sleep 1
done
echo "SearXNG is ready" >&2

# Start the MCP server in the foreground (exec replaces this shell).
# stdin/stdout are wired directly to Docker — clean STDIO transport.
exec "$VENV/bin/python" /app/src/server.py
