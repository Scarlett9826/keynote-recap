"""Stage 2: extract candidate frames + PIL-score them.

Produces ~80 candidate frames (configurable) with frame_scorer scores and
±15s subtitle context. Stage 3 will then vision-LLM-filter to ~30-50.

Outputs:
    <output>/frames_raw/frame_NNN.jpg     (all sampled frames)
    state.candidate_frames               (top-N by score)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from ..config import Config
from ..frame_scorer import score_image
from ..state import FrameCandidate, State
from ..util import ensure_dir, format_duration
from .download import parse_srt

console = Console()


def run(state: State, cfg: Config) -> State:
    """Execute stage 2."""
    if state.video is None:
        raise RuntimeError("Stage 2 requires stage 1 (video) to be done first.")

    output_dir = Path(state.output_dir)
    raw_dir = ensure_dir(output_dir / "frames_raw")

    console.print("[bold]Stage 2 — segment + frame_scorer[/]")

    duration_s = state.video.duration_s
    interval = cfg.frame_filter.sample_interval_s
    n_samples = int(duration_s / interval)

    # Cap samples to a reasonable upper bound (3000) to avoid disk blow-up
    if n_samples > 3000:
        interval = duration_s / 3000
        n_samples = 3000
        console.print(f"  [yellow]Adjusted interval to {interval:.1f}s (cap 3000 samples)[/]")

    console.print(f"  Sampling every {interval:.1f}s ≈ {n_samples} frames")

    # 1. ffmpeg extraction
    _ffmpeg_sample(
        Path(state.video.video_path),
        raw_dir,
        interval=interval,
        duration_s=duration_s,
    )

    # 2. score every frame
    raw_frames = sorted(raw_dir.glob("frame_*.jpg"))
    console.print(f"  Extracted {len(raw_frames)} frames; scoring...")

    scored: list[tuple[Path, float, dict]] = []
    with Progress(transient=True) as progress:
        task = progress.add_task("scoring", total=len(raw_frames))
        for p in raw_frames:
            try:
                r = score_image(str(p))
                scored.append((p, r["score"], r["metrics"]))
            except Exception as e:
                if cfg.debug:
                    console.print(f"    [red]score failed: {p.name} ({e})[/]")
            progress.advance(task)

    # 3. take top-N candidates
    scored.sort(key=lambda x: x[1], reverse=True)
    top_n = scored[: cfg.frame_filter.candidate_count]

    # 4. parse subtitles for context
    segments = []
    if state.video.subtitle_path:
        segments = parse_srt(Path(state.video.subtitle_path))

    # 5. build FrameCandidate list
    candidates: list[FrameCandidate] = []
    for p, score, metrics in top_n:
        ts = _frame_timestamp(p, interval)
        ctx = _subtitle_context(segments, ts, window_s=15)
        candidates.append(FrameCandidate(
            filename=p.name,
            timestamp_s=ts,
            score=score,
            text_density=metrics.get("edge_density", 0),
            edge_density=metrics.get("edge_density", 0),
            context_subtitle=ctx,
        ))

    candidates.sort(key=lambda c: c.timestamp_s)

    # 6. delete raw frames that didn't make it (saves disk)
    keep = {c.filename for c in candidates}
    for p in raw_frames:
        if p.name not in keep:
            p.unlink(missing_ok=True)

    state.candidate_frames = candidates
    state.last_completed_stage = 2.0
    state.save()

    console.print(
        f"  Kept top {len(candidates)} candidates "
        f"(score range {candidates[-1].score:.1f}–{candidates[0].score:.1f})"
        if candidates else "  No candidates kept"
    )
    console.print("[green]✓ Stage 2 done[/]\n")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# ffmpeg helper
# ──────────────────────────────────────────────────────────────────────────────
def _ffmpeg_sample(video: Path, dest_dir: Path, interval: float, duration_s: float) -> None:
    """Sample one frame every `interval` seconds. Output frame_00001.jpg ..."""
    out_pattern = str(dest_dir / "frame_%05d.jpg")
    fps = 1.0 / interval

    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"fps={fps:.6f}",
        "-q:v", "2",                  # high quality
        "-y",
        out_pattern,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{r.stderr}")


def _frame_timestamp(path: Path, interval: float) -> float:
    """frame_00042.jpg → seconds. ffmpeg starts numbering at 1."""
    stem = path.stem  # frame_00042
    try:
        idx = int(stem.split("_")[1])
    except (IndexError, ValueError):
        return 0.0
    return (idx - 1) * interval


def _subtitle_context(segments: list[dict], timestamp_s: float, window_s: float = 15) -> str:
    """Return concatenated subtitle text within ±window_s of timestamp."""
    matches = [
        s["text"] for s in segments
        if s["end_s"] >= timestamp_s - window_s
        and s["start_s"] <= timestamp_s + window_s
    ]
    return " ".join(matches)
