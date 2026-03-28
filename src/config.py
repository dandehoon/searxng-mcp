import os

SEARXNG_URL: str = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8080").rstrip("/")
SEARXNG_TIMEOUT: float = float(os.environ.get("SEARXNG_TIMEOUT", "30.0"))
FETCH_TIMEOUT: float = float(os.environ.get("FETCH_TIMEOUT", "60.0"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "WARNING").upper()
TRANSPORT: str = os.environ.get("TRANSPORT", "stdio").lower()
MCP_HOST: str = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "8000"))
MCP_PATH: str = os.environ.get("MCP_PATH", "/mcp/")

# Search defaults — can be overridden per-request where exposed as tool params
SEARXNG_CATEGORIES: str = os.environ.get("SEARXNG_CATEGORIES", "general")
SEARXNG_LANGUAGE: str = os.environ.get("SEARXNG_LANGUAGE", "auto")
SEARXNG_MAX_RESULTS: int = int(os.environ.get("SEARXNG_MAX_RESULTS", "20"))
SEARXNG_SAFESEARCH: int = int(os.environ.get("SEARXNG_SAFESEARCH", "0"))
SEARXNG_TIME_RANGE: str | None = os.environ.get("SEARXNG_TIME_RANGE") or None
SEARXNG_ENGINES: str | None = os.environ.get("SEARXNG_ENGINES") or None

FETCH_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; searxng-mcp/1.0; +https://github.com/searxng/searxng-mcp)"
    )
}
