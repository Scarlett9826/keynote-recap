"""Utility helpers shared across stages."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def slugify_url(url: str) -> str:
    """Generate a stable, filesystem-safe slug from a video URL.

    Examples:
        https://www.youtube.com/watch?v=wYSncx9zLIU → youtube_wYSncx9zLIU
        https://www.bilibili.com/video/BV1xxx       → bilibili_BV1xxx
        Other URLs                                  → host_<8charhash>
    """
    p = urlparse(url)
    host = p.hostname or "unknown"
    host = host.replace("www.", "").split(".")[0]

    # YouTube ?v=
    if "youtube" in host or host == "youtu":
        if host == "youtu":  # youtu.be/<id>
            vid = p.path.strip("/").split("/")[0]
        else:
            qs = parse_qs(p.query)
            vid = qs.get("v", [""])[0]
        if vid:
            return f"youtube_{_safe_token(vid)}"

    # Bilibili /video/BVxxx
    if "bilibili" in host:
        m = re.search(r"/video/(BV\w+)", p.path)
        if m:
            return f"bilibili_{m.group(1)}"

    # Fallback: host + short hash
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{host}_{h}"


def _safe_token(s: str) -> str:
    """Strip anything not [A-Za-z0-9_-]."""
    return re.sub(r"[^A-Za-z0-9_-]", "", s)


def format_duration(seconds: float) -> str:
    """Format seconds → HH:MM:SS or MM:SS."""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_size(num_bytes: float) -> str:
    """Format bytes → human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


def ensure_dir(path: Path) -> Path:
    """mkdir -p and return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def srt_timestamp_to_seconds(ts: str) -> float:
    """Convert '00:01:23,456' or '00:01:23.456' to float seconds."""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert float seconds to '00:01:23,456'."""
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    s -= h * 3600
    m = int(s // 60)
    s -= m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
