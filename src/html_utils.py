"""HTML content extraction utilities for the fetch-web MCP tool."""

import re
from typing import Any

from bs4 import BeautifulSoup

# Tags whose entire subtree is noise — no readable content value.
STRIP_TAGS = [
    "script",
    "style",
    "head",
    "nav",
    "footer",
    "aside",
    "iframe",
    "noscript",
]

# ARIA / attribute selectors for page-level chrome not covered by tag names.
STRIP_SELECTORS = [
    '[role="banner"]',
    '[role="navigation"]',
    '[role="complementary"]',
    '[role="dialog"]',
    '[aria-hidden="true"]',
]
STRIP_SELECTORS_STR = ", ".join(STRIP_SELECTORS)

# Ordered list of selectors for the primary content container.
_MAIN_SELECTORS = [
    "main",
    "article",
    '[role="main"]',
    "#main",
    "#content",
    ".content",
]


def extract_title(soup: BeautifulSoup, fallback: str) -> str:
    """Return page title from <title>, first <h1>, or fallback."""
    tag = soup.find("title")
    if tag:
        return tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return fallback


def extract_title_from_markdown(text: str, fallback: str) -> str:
    """Return title from a markdown document's frontmatter or first H1."""
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("title:"):
            return line[6:].strip().strip("\"'")
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def find_main_content(soup: BeautifulSoup) -> Any:
    """Return the most specific content container, falling back to <body>."""
    for selector in _MAIN_SELECTORS:
        node = soup.select_one(selector)
        if node:
            return node
    return soup.find("body") or soup


def clean_markdown(text: str) -> str:
    """Strip trailing whitespace per line and collapse 3+ blank lines to 2."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
