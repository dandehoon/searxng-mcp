#!/bin/sh
# entrypoint.sh — start SearXNG and the MCP server in a single container.
# Runs on Void Linux (the official searxng/searxng base image).

set -eu

VENV=/usr/local/searxng/.venv
SEARXNG_SETTINGS_PATH=${SEARXNG_SETTINGS_PATH:-/etc/searxng/settings.yml}
SEARXNG_URL=${SEARXNG_URL:-http://127.0.0.1:8080}

# Ensure settings file exists (official image creates it from template if missing)
if [ ! -f "$SEARXNG_SETTINGS_PATH" ]; then
    cp -f /usr/local/searxng/searx/settings.yml "$SEARXNG_SETTINGS_PATH"
    echo "Created settings from template: $SEARXNG_SETTINGS_PATH" >&2
fi

# Generate a random secret key if using the placeholder
if grep -q "searxng-mcp-secret-change-in-prod" "$SEARXNG_SETTINGS_PATH" 2>/dev/null; then
    RANDOM_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || date +%s%N)
    sed -i "s/searxng-mcp-secret-change-in-prod/$RANDOM_KEY/" "$SEARXNG_SETTINGS_PATH"
fi

# Launch SearXNG via granian in the background.
# Redirect granian's stdout to stderr so it doesn't pollute the MCP STDIO stream.
PYTHONPATH=/usr/local/searxng \
    SEARXNG_SETTINGS_PATH="$SEARXNG_SETTINGS_PATH" \
    "$VENV/bin/granian" --workers 1 --no-reload searx.webapp:app >&2 &

# Wait for SearXNG to become ready (max 30 seconds)
ATTEMPTS=0
MAX_ATTEMPTS=300
echo "Waiting for SearXNG to start..." >&2
until wget -q -O /dev/null "${SEARXNG_URL}/healthz" 2>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: SearXNG failed to start after 30 seconds" >&2
        exit 1
    fi
    sleep 0.1  # busybox ash supports fractional sleep
done
echo "SearXNG is ready" >&2

# exec replaces this shell process; Docker sends SIGTERM to Python (PID 1) on stop.
exec "$VENV/bin/python" /app/src/server.py
