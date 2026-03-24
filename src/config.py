import os

SEARXNG_URL: str = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8080").rstrip("/")
SEARXNG_TIMEOUT: float = float(os.environ.get("SEARXNG_TIMEOUT", "30.0"))
FETCH_TIMEOUT: float = float(os.environ.get("FETCH_TIMEOUT", "60.0"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "WARNING").upper()
TRANSPORT: str = os.environ.get("TRANSPORT", "stdio").lower()
MCP_HOST: str = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "8000"))
MCP_PATH: str = os.environ.get("MCP_PATH", "/mcp/")

FETCH_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; searxng-mcp/1.0; +https://github.com/searxng/searxng-mcp)"
    )
}
