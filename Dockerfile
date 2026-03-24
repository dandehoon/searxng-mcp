# Build on top of the official SearXNG image.
# This inherits their pre-compiled venv (granian, lxml, etc.) and avoids
# re-compiling C extensions. When SearXNG releases a new version, just
# re-pull this base image — no Dockerfile changes needed.
FROM docker.io/searxng/searxng:latest

# Bootstrap pip and uv into the system Python (Void Linux has neither by default).
# Install our MCP server dependencies into the existing SearXNG venv so both
# searx and fastmcp/httpx share the same Python interpreter.
# Clean up build tools and venv bloat in the same layer to minimise image size.
RUN PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))") \
    && python3 -m ensurepip \
    && python3 -m pip install --quiet uv \
    && python3 -m uv pip install beautifulsoup4 fastmcp httpx markdownify \
        --python /usr/local/searxng/.venv/bin/python \
        --no-cache \
    && rm -rf \
        /usr/sbin/uv /usr/bin/uv \
        /usr/sbin/uvx /usr/bin/uvx \
        /usr/sbin/pip3 /usr/sbin/pip3.* \
        /usr/bin/pip3 /usr/bin/pip3.* \
        "$PYLIB/pip" \
        "$PYLIB/pip-"*.dist-info \
        "$PYLIB/uv" \
        "$PYLIB/uv-"*.dist-info

# Copy MCP server source, SearXNG config, and entrypoint
COPY src/ /app/src/
COPY --chown=searxng:searxng config/settings.yml /etc/searxng/settings.yml
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment defaults (overridable at docker run time)
ENV TRANSPORT=stdio
ENV LOG_LEVEL=WARNING
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp/
ENV SEARXNG_URL=http://127.0.0.1:8080
ENV SEARXNG_TIMEOUT=30.0
ENV FETCH_TIMEOUT=60.0
ENV SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml

# Port exposed only when TRANSPORT=http (ignored in stdio mode)
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
