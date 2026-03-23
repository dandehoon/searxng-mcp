import os

SEARXNG_URL: str = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8080").rstrip("/")
SEARXNG_TIMEOUT: float = float(os.environ.get("SEARXNG_TIMEOUT", "30.0"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "WARNING").upper()
TRANSPORT: str = os.environ.get("TRANSPORT", "stdio").lower()
