"""Official channel registry for keynote publishers.

Many keynotes (Google I/O, Apple WWDC, OpenAI DevDay, Meta Connect …) publish
their announcement details on a small, predictable set of official sites.
Searching DuckDuckGo / Tavily for these facts is wasteful and noisy — we know
the canonical domain ahead of time. This module maps a publisher (detected
from the video uploader / title) to:

  - a set of allow-listed official domains
  - a list of seed URLs (landing pages) to try first
  - URL templates keyed by product slug (filled in from transcript)

Stage 4.2 uses this to run an "official-first" pass before falling back to
generic web search. This dramatically improves verified-fact precision and
removes dependency on flaky search providers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OfficialChannel:
    """One publisher's official-channel profile."""
    publisher: str
    # Lowercased domains — facts whose source URL contains one of these are
    # treated as confidence="high".
    domains: tuple[str, ...]
    # Seed URLs (landing pages) likely to contain the keynote's announcements.
    # These are fetched unconditionally, regardless of which fact we're
    # verifying, and indexed by the LLM during summarization.
    seed_urls: tuple[str, ...] = ()
    # URL templates: each callable receives a product slug and returns a list
    # of candidate URLs to try. Slugs are derived from product names extracted
    # from the transcript (e.g., "Gemini 3" -> "gemini-3").
    url_templates: tuple[Callable[[str], list[str]], ...] = ()


def _slugify(name: str) -> str:
    """Convert 'Gemini 3 Pro' → 'gemini-3-pro'."""
    return (
        name.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(".", "")
        .replace(",", "")
        .strip("-")
    )


# ──────────────────────────────────────────────────────────────────────────────
# Google
# ──────────────────────────────────────────────────────────────────────────────
def _google_templates(slug: str) -> list[str]:
    """Common Google product announcement URL patterns."""
    return [
        f"https://blog.google/technology/google-deepmind/{slug}/",
        f"https://blog.google/products/{slug}/",
        f"https://blog.google/technology/ai/{slug}/",
        f"https://blog.google/technology/developers/{slug}/",
        f"https://developers.googleblog.com/en/{slug}/",
        f"https://deepmind.google/discover/blog/{slug}/",
    ]


GOOGLE = OfficialChannel(
    publisher="google",
    domains=(
        "blog.google",
        "developers.googleblog.com",
        "developers.google.com",
        "ai.googleblog.com",
        "deepmind.google",
        "research.google",
        "cloud.google.com/blog",
        "android-developers.googleblog.com",
        "store.google.com",
        "youtube.com/google",
    ),
    seed_urls=(
        "https://blog.google/technology/ai/",
        "https://blog.google/technology/google-deepmind/",
        "https://developers.googleblog.com/",
    ),
    url_templates=(_google_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────────────────────────────────────────
def _openai_templates(slug: str) -> list[str]:
    return [
        f"https://openai.com/index/{slug}/",
        f"https://openai.com/blog/{slug}/",
        f"https://platform.openai.com/docs/models/{slug}",
    ]


OPENAI = OfficialChannel(
    publisher="openai",
    domains=("openai.com", "platform.openai.com"),
    seed_urls=("https://openai.com/news/",),
    url_templates=(_openai_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic
# ──────────────────────────────────────────────────────────────────────────────
def _anthropic_templates(slug: str) -> list[str]:
    return [
        f"https://www.anthropic.com/news/{slug}",
        f"https://www.anthropic.com/claude/{slug}",
    ]


ANTHROPIC = OfficialChannel(
    publisher="anthropic",
    domains=("anthropic.com",),
    seed_urls=("https://www.anthropic.com/news",),
    url_templates=(_anthropic_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# Apple
# ──────────────────────────────────────────────────────────────────────────────
def _apple_templates(slug: str) -> list[str]:
    return [
        f"https://www.apple.com/newsroom/2026/{slug}/",
        f"https://developer.apple.com/{slug}/",
    ]


APPLE = OfficialChannel(
    publisher="apple",
    domains=("apple.com", "developer.apple.com"),
    seed_urls=("https://www.apple.com/newsroom/", "https://developer.apple.com/wwdc/"),
    url_templates=(_apple_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# Meta
# ──────────────────────────────────────────────────────────────────────────────
def _meta_templates(slug: str) -> list[str]:
    return [
        f"https://about.fb.com/news/2026/{slug}/",
        f"https://ai.meta.com/blog/{slug}/",
    ]


META = OfficialChannel(
    publisher="meta",
    domains=("about.fb.com", "ai.meta.com", "developers.meta.com", "meta.com"),
    seed_urls=("https://about.fb.com/news/", "https://ai.meta.com/blog/"),
    url_templates=(_meta_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# Microsoft
# ──────────────────────────────────────────────────────────────────────────────
def _microsoft_templates(slug: str) -> list[str]:
    return [
        f"https://blogs.microsoft.com/blog/2026/{slug}/",
        f"https://devblogs.microsoft.com/{slug}/",
    ]


MICROSOFT = OfficialChannel(
    publisher="microsoft",
    domains=("microsoft.com", "blogs.microsoft.com", "devblogs.microsoft.com"),
    seed_urls=("https://blogs.microsoft.com/blog/", "https://devblogs.microsoft.com/"),
    url_templates=(_microsoft_templates,),
)


# ──────────────────────────────────────────────────────────────────────────────
# NVIDIA
# ──────────────────────────────────────────────────────────────────────────────
def _nvidia_templates(slug: str) -> list[str]:
    return [
        f"https://blogs.nvidia.com/blog/{slug}/",
        f"https://developer.nvidia.com/blog/{slug}/",
    ]


NVIDIA = OfficialChannel(
    publisher="nvidia",
    domains=("nvidia.com", "blogs.nvidia.com", "developer.nvidia.com"),
    seed_urls=("https://blogs.nvidia.com/", "https://developer.nvidia.com/blog/"),
    url_templates=(_nvidia_templates,),
)


REGISTRY: dict[str, OfficialChannel] = {
    "google": GOOGLE,
    "openai": OPENAI,
    "anthropic": ANTHROPIC,
    "apple": APPLE,
    "meta": META,
    "facebook": META,
    "microsoft": MICROSOFT,
    "nvidia": NVIDIA,
}


# ──────────────────────────────────────────────────────────────────────────────
# Detection
# ──────────────────────────────────────────────────────────────────────────────
_PUBLISHER_SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    ("google", ("google", "deepmind", "android", "youtube official", " io ", "i/o")),
    ("openai", ("openai", "devday", "sam altman")),
    ("anthropic", ("anthropic", "claude")),
    ("apple", ("apple", "wwdc", "tim cook")),
    ("meta", ("meta", "facebook", "connect 2", "zuckerberg")),
    ("microsoft", ("microsoft", "build 20", "satya nadella", "windows")),
    ("nvidia", ("nvidia", "gtc", "jensen huang")),
]


def detect_publisher(uploader: str, title: str, transcript_head: str = "") -> str | None:
    """Best-effort detection of the keynote publisher.

    Looks at the YouTube uploader, video title, and the first ~2k chars of the
    transcript for tell-tale brand mentions. Returns a key into REGISTRY, or
    None if no match is confident enough.
    """
    haystack = f"{uploader} | {title} | {transcript_head[:2000]}".lower()
    for key, signals in _PUBLISHER_SIGNALS:
        for sig in signals:
            if sig in haystack:
                return key
    return None


def get_channel(publisher: str | None) -> OfficialChannel | None:
    if not publisher:
        return None
    return REGISTRY.get(publisher.lower())


def candidate_urls_for_product(channel: OfficialChannel, product_name: str) -> list[str]:
    """Generate candidate URLs for a product on a given publisher's channels."""
    slug = _slugify(product_name)
    if not slug:
        return []
    urls: list[str] = []
    for tmpl in channel.url_templates:
        urls.extend(tmpl(slug))
    return urls


def is_official_url(url: str, channel: OfficialChannel | None) -> bool:
    if not channel or not url:
        return False
    u = url.lower()
    return any(d in u for d in channel.domains)
