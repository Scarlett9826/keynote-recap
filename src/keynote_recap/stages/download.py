"""Stage 1: download video + subtitles via yt-dlp.

Outputs to <output_dir>/:
    video.mp4         — 1080p60 by default
    subtitle.<lang>.{srt,vtt}
    metadata.json     — yt-dlp -J output (for title/uploader/duration)

Falls back gracefully:
    - If 1080p60 unavailable → 1080p → 720p
    - If no subtitles → flag for stage 1 fallback (LLM transcription)
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from rich.console import Console

from ..config import Config
from ..state import State, VideoMeta
from ..util import ensure_dir, format_duration, srt_timestamp_to_seconds

console = Console()


def run(state: State, cfg: Config) -> State:
    """Execute stage 1."""
    output_dir = Path(state.output_dir)
    ensure_dir(output_dir)

    console.print("[bold]Stage 1 — download[/]")

    # 1. metadata
    meta = _fetch_metadata(state.url)
    title = meta.get("title", "")
    uploader = meta.get("uploader", "") or meta.get("channel", "")
    duration_s = float(meta.get("duration", 0))

    console.print(f"  Title:    {title}")
    console.print(f"  Uploader: {uploader}")
    console.print(f"  Duration: {format_duration(duration_s)}")

    (output_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # 2. video
    video_path = _download_video(state.url, output_dir, cfg.video.resolution)
    console.print(f"  Video:    {video_path}")

    # v0.3.7 P3: probe actual resolution. yt-dlp may fall back to a lower
    # quality format (Bilibili non-premium = 480p, region locks, etc.).
    # Surface this BEFORE stage 3 burns 30+ vision-LLM calls — low-res
    # input causes uniformly low info_density scores which then trip the
    # v0.3.6 F5 useful_ratio gate. ffprobe is part of ffmpeg (already a
    # hard dep), so this is free.
    actual_w, actual_h = _probe_resolution(video_path)
    actual_resolution_str = f"{actual_w}x{actual_h}" if actual_h else ""
    if actual_h:
        console.print(f"  Probed:   {actual_w}x{actual_h} (actual)")
        if actual_h < 720:
            warn = (
                f"Downloaded video is {actual_w}x{actual_h} (< 720p). "
                f"Vision LLM tends to assign uniformly low info_density to "
                f"low-res frames — stage 3 may trip useful_ratio < 50% even "
                f"on legitimate content. Recommended: re-download with "
                f"`--cookies-from-browser chrome` (or your browser) to "
                f"unlock 1080p. If this is the best available source, pass "
                f"`--accept-low-yield` to stage 3 (report will carry "
                f"low-yield-override stamp)."
            )
            console.print(f"  [bold yellow]\u26a0 low-resolution warning:[/] {warn}")
            if warn not in state.runtime_warnings:
                state.runtime_warnings.append(warn)

    # 3. subtitles
    subtitle_path, subtitle_lang, transcript = "", "", ""

    # v0.2.4 (M9.2): user-supplied transcript takes precedence and is the
    # sanctioned escape hatch for sources that block subtitle download
    # (Bilibili 412, region-locked, etc.).
    transcript_override = getattr(state, "transcript_override_path", "") or ""
    if transcript_override:
        ov_path = Path(transcript_override)
        if not ov_path.exists():
            raise RuntimeError(
                f"--transcript-file {transcript_override} does not exist."
            )
        if ov_path.suffix.lower() in (".srt", ".vtt"):
            transcript = _extract_plaintext(ov_path)
            subtitle_path = str(ov_path)
            subtitle_lang = "user-supplied"
        else:
            transcript = ov_path.read_text(encoding="utf-8", errors="replace")
            subtitle_lang = "user-supplied"
        console.print(f"  Subtitle: {ov_path} (user-supplied)")
    elif cfg.video.download_subtitles:
        subtitle_path, subtitle_lang = _download_subtitles(
            state.url, output_dir, cfg.video.languages
        )
        if subtitle_path:
            console.print(f"  Subtitle: {subtitle_path} ({subtitle_lang})")
            transcript = _extract_plaintext(Path(subtitle_path))

    # v0.2.4 (M9.2): no transcript = hard fail. Without transcript, stage 3
    # cannot do "high-frequency product name has image" cross-check, stage 4
    # has no facts to research, and the methodology collapses. Previously
    # this was a soft warning + continue, which produced silent half-quality
    # reports.
    if not transcript:
        raise RuntimeError(
            "No transcript available — stage 1 cannot complete.\n\n"
            "Pipeline aborted. The methodology requires transcript text for:\n"
            "  - stage 3 'high-freq product name → image' cross-check\n"
            "  - stage 4 fact research\n"
            "  - stage 5 outline & body grounding\n\n"
            "Fix options:\n"
            "  1. yt-dlp --cookies-from-browser chrome <url> "
            "--write-auto-sub --skip-download\n"
            "     (extract cookies from your browser; works for Bilibili 412 "
            "and similar)\n"
            "  2. Manually prepare a .srt or .txt transcript and pass it via\n"
            "     keynote-recap recap <url> --transcript-file ./manual.srt\n"
            "  3. Try a different mirror / region for the source URL"
        )

    state.video = VideoMeta(
        url=state.url,
        title=title,
        uploader=uploader,
        duration_s=duration_s,
        resolution=cfg.video.resolution,
        actual_resolution=actual_resolution_str,
        actual_height=actual_h,
        video_path=str(video_path),
        subtitle_path=str(subtitle_path) if subtitle_path else "",
        subtitle_lang=subtitle_lang,
        transcript=transcript,
    )
    state.last_completed_stage = 1.0
    state.save()
    console.print("[green]✓ Stage 1 done[/]\n")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# yt-dlp wrappers
# ──────────────────────────────────────────────────────────────────────────────
def _fetch_metadata(url: str) -> dict:
    """yt-dlp -J to get full info JSON without downloading."""
    cmd = ["yt-dlp", "-J", "--no-playlist", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # Retry with cookies
        cmd2 = cmd + ["--cookies-from-browser", "chrome"]
        r = subprocess.run(cmd2, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"yt-dlp metadata failed:\n{r.stderr}")
    return json.loads(r.stdout)


def _download_video(url: str, dest_dir: Path, resolution: str) -> Path:
    """Download mp4 at requested resolution. Returns Path."""
    out_tmpl = str(dest_dir / "video.%(ext)s")

    # Build format selector based on resolution
    fmt = _resolution_to_format(resolution)

    cmd = [
        "yt-dlp",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        "--no-playlist",
        url,
    ]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        # Retry with cookies + alt extractor
        console.print("  [yellow]Retry with cookies...[/]")
        cmd2 = cmd + [
            "--cookies-from-browser", "chrome",
            "--extractor-args", "youtube:player_client=mweb,tv_simply",
        ]
        r2 = subprocess.run(cmd2)
        if r2.returncode != 0:
            raise RuntimeError("yt-dlp video download failed even with cookies.")

    for f in dest_dir.glob("video.*"):
        if f.suffix in (".mp4", ".mkv", ".webm"):
            return f
    raise RuntimeError(f"Download succeeded but no video file in {dest_dir}")


def _resolution_to_format(resolution: str) -> str:
    """'1080p60' → yt-dlp -f selector."""
    m = re.match(r"(\d+)p(\d+)?", resolution)
    if not m:
        return "bv*+ba/b"
    height = m.group(1)
    fps = m.group(2)
    if fps:
        return (
            f"bv*[height<={height}][fps>={fps}]+ba/"
            f"bv*[height<={height}]+ba/"
            f"b[height<={height}]"
        )
    return f"bv*[height<={height}]+ba/b[height<={height}]"


def _download_subtitles(url: str, dest_dir: Path, languages: list[str]) -> tuple[str, str]:
    """Download subtitles. Returns (path, lang) or ('', '').

    Tries without cookies first; if no usable subtitle file appears (e.g.
    Bilibili requires login for subtitles since 2024H2), retries with
    --cookies-from-browser chrome.
    """
    lang_arg = ",".join(languages)
    base_cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", lang_arg,
        "--sub-format", "srt/vtt/best",
        "--convert-subs", "srt",
        "-o", str(dest_dir / "subtitle.%(ext)s"),
        "--no-playlist",
        url,
    ]

    def _scan() -> tuple[str, str]:
        for lang in languages:
            for ext in ("srt", "vtt"):
                for pattern in (f"subtitle.{lang}.{ext}", f"subtitle*{lang}*.{ext}"):
                    matches = list(dest_dir.glob(pattern))
                    if matches:
                        return str(matches[0]), lang
        for ext in ("srt", "vtt"):
            any_match = list(dest_dir.glob(f"subtitle*.{ext}"))
            if any_match:
                return str(any_match[0]), "auto"
        return "", ""

    # First attempt: no cookies (works for sites without auth requirement)
    subprocess.run(base_cmd, capture_output=True, text=True)
    path, lang = _scan()
    if path:
        return path, lang

    # Retry with cookies — Bilibili since 2024H2 requires login for subtitles,
    # and yt-dlp's first attempt returns 0 with only danmaku.xml (not usable).
    console.print("  [yellow]No subtitle file found; retry with browser cookies...[/]")
    cmd_cookie = base_cmd + ["--cookies-from-browser", "chrome"]
    subprocess.run(cmd_cookie, capture_output=True, text=True)
    return _scan()


# ──────────────────────────────────────────────────────────────────────────────
# Subtitle parsing
# ──────────────────────────────────────────────────────────────────────────────
def _extract_plaintext(subtitle_path: Path) -> str:
    """Extract plain text from SRT/VTT file (no timestamps)."""
    text = subtitle_path.read_text(encoding="utf-8", errors="replace")
    # Strip SRT numbering and timestamp lines
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\d+$", line):  # SRT index
            continue
        if "-->" in line:  # timestamp
            continue
        if line.startswith("WEBVTT"):
            continue
        # Strip HTML/SSA tags
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        lines.append(line)
    return "\n".join(lines)


def _probe_resolution(video_path: Path) -> tuple[int, int]:
    """v0.3.7 P3: probe (width, height) of downloaded video via ffprobe.

    Returns ``(0, 0)`` if ffprobe is missing or fails — non-fatal because
    the resolution probe is advisory (warns about likely-low-yield runs).

    Streams the first video stream's coded dimensions; for hardware-encoded
    sources these match the pixel dimensions seen by the vision LLM after
    ffmpeg sampling.
    """
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return (0, 0)
    if r.returncode != 0:
        return (0, 0)
    out = (r.stdout or "").strip()
    m = re.match(r"^(\d+)x(\d+)$", out)
    if not m:
        return (0, 0)
    try:
        return (int(m.group(1)), int(m.group(2)))
    except ValueError:
        return (0, 0)


def parse_srt(subtitle_path: Path) -> list[dict]:
    """Parse SRT into list of {start_s, end_s, text} segments.

    Used by later stages (segment.py, extract.py) to look up context for a frame.
    """
    text = subtitle_path.read_text(encoding="utf-8", errors="replace")
    segments = []

    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Skip index line if present (SRT)
        if re.match(r"^\d+$", lines[0]):
            lines = lines[1:]

        if not lines or "-->" not in lines[0]:
            continue

        m = re.match(r"([\d:,.]+)\s*-->\s*([\d:,.]+)", lines[0])
        if not m:
            continue

        start_s = srt_timestamp_to_seconds(m.group(1))
        end_s = srt_timestamp_to_seconds(m.group(2))
        text_content = "\n".join(lines[1:]).strip()
        text_content = re.sub(r"<[^>]+>", "", text_content)

        if text_content:
            segments.append({"start_s": start_s, "end_s": end_s, "text": text_content})

    return segments
