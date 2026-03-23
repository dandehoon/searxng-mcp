# Stage 1: Extract SearXNG app code from official image (Void Linux based)
# We copy only the pure-Python `searx/` application directory.
# The official venv is NOT copied — it's compiled for Void Linux (musl/Python 3.14)
# and is incompatible with our Debian/Python 3.12 base.
FROM docker.io/searxng/searxng:latest AS searxng

# Stage 2: Final image — Python 3.12 slim (Debian-based)
FROM python:3.12-slim

# Build deps for lxml and other compiled SearXNG dependencies.
# Cleaned up after installation to keep image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libz-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy SearXNG pure-Python app code from the official image
COPY --from=searxng /usr/local/searxng/searx/ /usr/local/searxng/searx/

# Create searxng user/group (UID/GID 977) and required directories
RUN groupadd -g 977 searxng \
    && useradd -u 977 -g searxng -d /usr/local/searxng -s /bin/sh searxng \
    && mkdir -p /etc/searxng /var/cache/searxng \
    && chown -R searxng:searxng /etc/searxng /var/cache/searxng /usr/local/searxng

# Install SearXNG's Python dependencies (including granian, compiled for glibc/Python 3.12)
# Requirements fetched from the same git tag as the official image at build time.
# The SEARXNG_VERSION ARG allows pinning to a specific release.
ARG SEARXNG_REQUIREMENTS_URL=https://raw.githubusercontent.com/searxng/searxng/master
RUN uv pip install --system --no-cache \
    -r ${SEARXNG_REQUIREMENTS_URL}/requirements.txt \
    -r ${SEARXNG_REQUIREMENTS_URL}/requirements-server.txt

# Install MCP server Python dependencies using uv (separate layer for cache efficiency)
COPY pyproject.toml /app/pyproject.toml
RUN uv pip install --system --no-cache /app

# Copy MCP server source and our custom SearXNG settings
COPY src/ /app/src/
COPY config/settings.yml /etc/searxng/settings.yml
RUN chown searxng:searxng /etc/searxng/settings.yml

# Copy and configure the entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app

# Environment defaults (all overridable at docker run time)
ENV SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml
ENV PYTHONUNBUFFERED=1
ENV TRANSPORT=stdio
ENV LOG_LEVEL=WARNING
# Granian: bind to localhost only — SearXNG is internal to the container
ENV GRANIAN_HOST=127.0.0.1
ENV GRANIAN_PORT=8080
ENV GRANIAN_INTERFACE=wsgi
ENV GRANIAN_WEBSOCKETS=false

# No EXPOSE — SearXNG binds only on 127.0.0.1 inside the container

ENTRYPOINT ["/entrypoint.sh"]
