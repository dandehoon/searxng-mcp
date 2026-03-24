#!/bin/sh
# entrypoint.sh — start SearXNG and the MCP server in a single container.
# Runs on Void Linux (the official searxng/searxng base image).

set -eu

VENV=/usr/local/searxng/.venv
SEARXNG_SETTINGS_PATH=${SEARXNG_SETTINGS_PATH:-/etc/searxng/settings.yml}
SEARXNG_URL=${SEARXNG_URL:-http://127.0.0.1:8080}

# Fail fast if settings file is missing (Dockerfile COPYs it; fallback to
# upstream defaults would break the server — missing formats: [html, json])
if [ ! -f "$SEARXNG_SETTINGS_PATH" ]; then
    echo "ERROR: Settings file not found: $SEARXNG_SETTINGS_PATH" >&2
    exit 1
fi

# Generate a random secret key on every container start
RANDOM_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s/secret_key:.*/secret_key: \"$RANDOM_KEY\"/" "$SEARXNG_SETTINGS_PATH"

# Launch SearXNG via granian in the background.
# Redirect granian's stdout to stderr so it doesn't pollute the MCP STDIO stream.
PYTHONPATH=/usr/local/searxng \
    SEARXNG_SETTINGS_PATH="$SEARXNG_SETTINGS_PATH" \
    "$VENV/bin/granian" --workers 1 --no-reload searx.webapp:app >&2 &

# Wait for SearXNG to become ready (max ~30 seconds with 0.1s polling)
ATTEMPTS=0
MAX_ATTEMPTS=300
echo "Waiting for SearXNG to start..." >&2
until wget -q --timeout=2 -O /dev/null "${SEARXNG_URL}/healthz" 2>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: SearXNG did not respond at ${SEARXNG_URL}/healthz after $MAX_ATTEMPTS attempts" >&2
        exit 1
    fi
    sleep 0.1  # busybox ash supports fractional sleep
done
echo "SearXNG is ready" >&2

# exec replaces this shell process; Docker sends SIGTERM to Python (PID 1) on stop.
exec "$VENV/bin/python" /app/src/server.py
