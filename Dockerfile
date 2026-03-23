# Build on top of the official SearXNG image.
# This inherits their pre-compiled venv (granian, lxml, etc.) and avoids
# re-compiling C extensions. When SearXNG releases a new version, just
# re-pull this base image — no Dockerfile changes needed.
FROM docker.io/searxng/searxng:latest

# Bootstrap pip and uv into the system Python (Void Linux has neither by default).
# Install our MCP server dependencies into the existing SearXNG venv so both
# searx and fastmcp/httpx share the same Python interpreter.
# Clean up build tools and venv bloat in the same layer to minimise image size.
RUN python3 -m ensurepip \
    && python3 -m pip install --quiet uv \
    && python3 -m uv pip install fastmcp httpx markdownify \
        --python /usr/local/searxng/.venv/bin/python \
        --no-cache \
    && rm -rf \
        /usr/sbin/uv \
        /usr/sbin/uvx \
        /usr/sbin/pip3 \
        /usr/lib/python3.14/site-packages/pip \
        /usr/lib/python3.14/site-packages/pip-*.dist-info \
        /usr/lib/python3.14/site-packages/uv \
        /usr/lib/python3.14/site-packages/uv-*.dist-info \
    && find /usr/local/searxng/.venv -type d -name "__pycache__" | xargs rm -rf \
    && find /usr/local/searxng/.venv -type d -name "tests" | xargs rm -rf

# Copy MCP server source, SearXNG config, and entrypoint
COPY src/ /app/src/
COPY config/settings.yml /etc/searxng/settings.yml
COPY docker/entrypoint.sh /entrypoint.sh
RUN chown searxng:searxng /etc/searxng/settings.yml \
    && chmod +x /entrypoint.sh

# Environment defaults (overridable at docker run time)
ENV TRANSPORT=stdio
ENV LOG_LEVEL=WARNING
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp/

# Port exposed only when TRANSPORT=http (ignored in stdio mode)
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
