"""Search + webfetch abstraction.

Default provider: DuckDuckGo (zero-key, zero-cost).
Optional: Tavily (better quality, requires TAVILY_API_KEY).
Always available: webfetch (HTTP GET + HTML→text).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import SearchConfig


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]: ...


# ──────────────────────────────────────────────────────────────────────────────
# DuckDuckGo (default)
# ──────────────────────────────────────────────────────────────────────────────
class DuckDuckGoProvider:
    """Zero-key search via duckduckgo-search package."""

    def __init__(self, cfg: SearchConfig) -> None:
        self.cfg = cfg
        # Lazy import — keeps cold start fast
        from duckduckgo_search import DDGS
        self._ddgs = DDGS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        with self._ddgs() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results, region="us-en"))
        return [
            SearchHit(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in raw
        ]


# ──────────────────────────────────────────────────────────────────────────────
# Tavily (optional, paid)
# ──────────────────────────────────────────────────────────────────────────────
class TavilyProvider:
    def __init__(self, cfg: SearchConfig) -> None:
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(f"Set ${cfg.api_key_env} to use Tavily.")
        from tavily import TavilyClient
        self.client = TavilyClient(api_key=api_key)
        self.cfg = cfg

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        resp = self.client.search(query=query, max_results=max_results, search_depth="advanced")
        return [
            SearchHit(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in resp.get("results", [])
        ]


# ──────────────────────────────────────────────────────────────────────────────
# Webfetch-only (no search, just URL fetcher)
# ──────────────────────────────────────────────────────────────────────────────
class WebfetchOnlyProvider:
    """No search. LLM must guess URLs and we just fetch them."""

    def __init__(self, cfg: SearchConfig) -> None:
        self.cfg = cfg

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        return []  # Always empty — caller falls back to LLM-guessed URLs


# ──────────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────────
def get_search_provider(cfg: SearchConfig) -> SearchProvider:
    if cfg.provider == "duckduckgo":
        return DuckDuckGoProvider(cfg)
    if cfg.provider == "tavily":
        return TavilyProvider(cfg)
    if cfg.provider == "webfetch_only":
        return WebfetchOnlyProvider(cfg)
    raise ValueError(f"Unknown search provider: {cfg.provider}")


# ──────────────────────────────────────────────────────────────────────────────
# Webfetch (always available)
# ──────────────────────────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
def webfetch(url: str, timeout: int = 15, max_chars: int = 50000) -> tuple[bool, str]:
    """Fetch URL and return (success, text-or-error).

    Strips HTML, returns plaintext. Truncates to max_chars.
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "keynote-recap/0.1"})
            if resp.status_code >= 400:
                return False, f"HTTP {resp.status_code}"

        # If JSON or non-HTML, return raw
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return True, resp.text[:max_chars]

        soup = BeautifulSoup(resp.text, "html.parser")
        # Strip scripts/styles
        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = "\n".join(line for line in text.split("\n") if line.strip())
        return True, text[:max_chars]
    except Exception as e:
        return False, str(e)


def url_alive(url: str, timeout: int = 5) -> bool:
    """HEAD request to verify URL is reachable. For citation validation."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.head(url, headers={"User-Agent": "keynote-recap/0.1"})
        return r.status_code < 400
    except Exception:
        return False
