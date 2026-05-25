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

from .. import methodology as M
from ..config import Config
from ..frame_scorer import score_image
from ..state import FrameCandidate, State
from ..util import ensure_dir
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
    interval = M.SEGMENT_SAMPLE_INTERVAL_S
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

    # 4. parse subtitles for context (parsed early so step 3 can use them for chunking)
    segments = []
    if state.video.subtitle_path:
        segments = parse_srt(Path(state.video.subtitle_path))

    # 3. take top-N candidates with M6 D3 topic-chunk floor
    # Why: pure top-N by score causes whole transcript chunks (e.g. a long
    # speaker-led conversation segment) to be skipped because their PIL
    # scores are uniformly low. To prevent topic dropouts, we split the
    # video into N time chunks and reserve a per-chunk minimum even if the
    # absolute score is below the global cutoff.
    target_count = M.SEGMENT_CANDIDATE_COUNT
    top_n = _topn_with_chunk_floor(
        scored=scored,
        duration_s=duration_s,
        target_count=target_count,
        chunk_count=M.SEGMENT_CHUNK_COUNT,
        per_chunk_min=M.SEGMENT_CHUNK_FLOOR,
    )

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


def _topn_with_chunk_floor(
    scored: list[tuple[Path, float, dict]],
    duration_s: float,
    target_count: int,
    chunk_count: int = 12,
    per_chunk_min: int = 3,
) -> list[tuple[Path, float, dict]]:
    """Return ~target_count frames with per-time-chunk floor guarantee.

    The video is split into ``chunk_count`` equal time chunks. Each chunk
    contributes at least ``per_chunk_min`` frames (its top-scored ones) to
    the result; the remaining budget is filled by global top-N.

    This guarantees no whole stretch of the video is skipped just because
    its frames score low — preventing the F4 "漏了某产品" failure mode.
    """
    if not scored or chunk_count <= 0 or duration_s <= 0:
        scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
        return scored_sorted[:target_count]

    # Sort by score descending; we'll pull top-K from each chunk
    scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)

    # Build frame → chunk_idx mapping by parsing timestamp from filename
    # (frame_NNNNN.jpg, where N is the global sequence number 1-indexed).
    # We don't have interval here, so derive from the filename count.
    n_frames = len(scored)
    interval_est = duration_s / n_frames if n_frames > 0 else 1.0
    chunk_size_s = duration_s / chunk_count

    def _chunk_idx(path: Path) -> int:
        try:
            idx = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            return 0
        ts = (idx - 1) * interval_est
        ci = int(ts / chunk_size_s)
        return max(0, min(chunk_count - 1, ci))

    # First pass: per-chunk top-K
    by_chunk: dict[int, list[tuple[Path, float, dict]]] = {i: [] for i in range(chunk_count)}
    for entry in scored_sorted:
        ci = _chunk_idx(entry[0])
        if len(by_chunk[ci]) < per_chunk_min:
            by_chunk[ci].append(entry)

    floor_set = {entry[0]: entry for cs in by_chunk.values() for entry in cs}

    # Second pass: fill remaining budget by global top-N (skipping already-included)
    remaining_budget = max(0, target_count - len(floor_set))
    fill: list[tuple[Path, float, dict]] = []
    for entry in scored_sorted:
        if entry[0] in floor_set:
            continue
        if len(fill) >= remaining_budget:
            break
        fill.append(entry)

    combined = list(floor_set.values()) + fill
    return combined


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
