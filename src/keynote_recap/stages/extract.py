"""Stage 3: vision LLM三原则筛图.

Input:  ~80 candidate frames from stage 2
Output: 30-50 selected frames + captions + recommended sections

Strategy:
    - Batch frames (8-12 per LLM call) to fit in vision context
    - Pass full transcript + per-frame context for relevance check
    - Parse JSON output, deduplicate, sort by timestamp
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from .. import methodology as M
from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient, run_parallel
from ..preflight import check_model_capability
from ..state import SelectedFrame, State
from ..util import (
    VisionCapabilityError,
    detect_vision_capability_error,
    format_duration,
)

console = Console()

# Path resolution: prompts/03-extract-vision-filter.md
PROMPT_FILE = Path(__file__).parent.parent.parent.parent / "prompts" / "03-extract-vision-filter.md"

BATCH_SIZE = 10        # frames per vision call
MAX_TRANSCRIPT_CHARS = 30000  # truncate transcript for batch prompts


class ExtractFloorError(RuntimeError):
    """Stage 3 produced fewer/worse frames than methodology hard floors require.

    Raising this is how stage 3 signals 'retry me with a strengthened prompt'.
    Pipeline retry orchestration (v0.2.5 skeleton, v0.3.1 wiring) catches it
    and routes to the extract retry path with last-failures as prompt context.

    Distinct from generic RuntimeError so retry orchestration can tell apart
    'methodology floor breach' (retryable) from 'environmental error' (not).
    """


def _build_retry_directive(failures: list[str] | None) -> str:
    """v0.3.1 C3: render a [RETRY GUIDANCE] block from the prior attempt's
    quality-gate failures, to be injected at the top of the stage-3 vision
    prompt so the LLM is aware of what went wrong last time.

    Empty / None → empty string (first attempt, not a retry).
    """
    if not failures:
        return ""
    lines = [
        "=" * 70,
        "[RETRY GUIDANCE — previous attempt failed quality gates]",
        "",
        "The previous extraction round produced output that failed these checks:",
        "",
    ]
    for f in failures:
        lines.append(f"  - {f}")
    lines.extend([
        "",
        "This run MUST address each failure:",
        "  * If 'image mix' failed: select MORE live keynote frames (≥ 50%);",
        "    reduce marketing renders / inserted slides.",
        "  * If 'caption verify' failed: describe ONLY what is literally visible",
        "    in the frame — no inference, no extrapolation, no hallucination.",
        "    Wrong captions = LLM described frames it never actually saw.",
        "  * If 'per-section floor' failed: ensure each chapter has ≥ 1 frame,",
        "    mainline chapters have ≥ 4 frames; spread selection across the timeline.",
        "  * If 'topic coverage' failed: high-frequency transcript topics must",
        "    have associated frames; do not skip topics that recur in subtitles.",
        "  * If 'info density' failed: select frames with readable text/numbers/",
        "    diagrams (info_density ≥ 0.70); avoid pure-emotion / pure-portrait shots.",
        "=" * 70,
        "",
    ])
    return "\n".join(lines)


def run(state: State, cfg: Config, retry_context: list[str] | None = None) -> State:
    """Execute stage 3.

    v0.3.1 C3: ``retry_context`` is the prior attempt's quality-gate failure
    list; when non-empty, _build_retry_directive renders it as a [RETRY GUIDANCE]
    block injected at the top of every batch's user_text — telling the vision
    LLM what to fix this round. Pipeline passes this on second invocation.
    """
    if not state.candidate_frames:
        raise RuntimeError("Stage 3 requires stage 2 (candidate_frames) to be done first.")

    console.print("[bold]Stage 3 — vision filter (three principles)[/]")
    if retry_context:
        console.print(
            f"  [yellow]\u26a0 Retry mode:[/] injecting {len(retry_context)} "
            f"failure(s) from prior attempt into prompt as [RETRY GUIDANCE]"
        )

    output_dir = Path(state.output_dir)
    frames_dir = output_dir / "frames_raw"

    client = LLMClient(cfg.llm)
    candidates = state.candidate_frames

    # ─── Project-controlled parallelism (v0.2.3) ───
    # Concurrency is determined by methodology.parallel_for_stage based on
    # the model tier. Verified multimodal -> up to 4; otherwise -> 1.
    # User CANNOT override this; see methodology.py docstring for rationale.
    model_tier = check_model_capability(cfg.llm.models.extract).tier.value
    parallel = M.parallel_for_stage("extract", model_tier)
    state.stage_parallelism["extract"] = parallel

    console.print(
        f"  Filtering {len(candidates)} candidates in batches of {BATCH_SIZE} "
        f"(parallel: {parallel})"
    )

    transcript = (state.video.transcript or "")[:MAX_TRANSCRIPT_CHARS]
    title = state.video.title or ""
    duration = format_duration(state.video.duration_s)

    # System prompt embedded (no jinja deps)
    system = _load_system_prompt()

    selected: list[SelectedFrame] = []
    rejected: list[dict] = []

    # Pre-compute batches as a list so we can dispatch them in parallel.
    batches: list[tuple[int, list]] = []
    for batch_start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[batch_start : batch_start + BATCH_SIZE]
        batches.append((batch_start, batch))

    def _run_batch(item: tuple[int, list]) -> dict:
        """Process one batch; return a dict so the caller can merge in order.

        Returning data + cost-tracking deferred to the main thread keeps
        the cost_tracker / state mutations single-threaded (state is a
        Pydantic model; concurrent .append on its lists is unsafe).
        """
        batch_start, batch = item
        batch_paths = [frames_dir / c.filename for c in batch]
        user_text = _build_user_text(batch, transcript, title, duration, batch_start)
        # v0.3.1 C3: prepend retry guidance if this is a retry attempt
        retry_directive = _build_retry_directive(retry_context)
        if retry_directive:
            user_text = retry_directive + "\n" + user_text

        try:
            text, in_t, out_t = client.chat_with_images(
                model=cfg.llm.models.extract,
                system=system,
                user_text=user_text,
                image_paths=batch_paths,
                temperature=0.2,
                max_tokens=4000,
                json_mode=True,
            )
            err = detect_vision_capability_error(text)
            if err:
                raise VisionCapabilityError(err)
            return {
                "ok": True,
                "batch": batch,
                "data": client.parse_json(text),
                "in_tokens": in_t,
                "out_tokens": out_t,
            }
        except VisionCapabilityError as e:
            return {"ok": False, "batch": batch, "vision_error": str(e)}
        except Exception as e:
            return {"ok": False, "batch": batch, "error": str(e)}

    with Progress(transient=True) as progress:
        task = progress.add_task("vision filter", total=len(candidates))
        results = run_parallel(batches, _run_batch, parallel=parallel)

        for r in results:
            batch = r["batch"]
            if r.get("vision_error"):
                console.print()
                console.print("[bold red]✗ Stage 3 aborted: model cannot see images[/]")
                console.print(f"  Model returned: {r['vision_error']}")
                console.print()
                console.print("[bold]How to fix:[/]")
                console.print(f"  Current model: [cyan]{cfg.llm.models.extract}[/]")
                console.print("  Set a multimodal model via env or config, e.g.:")
                console.print("    [cyan]export KEYNOTE_RECAP_MODEL=gemini-2.5-pro[/]")
                console.print("    [cyan]export KEYNOTE_RECAP_MODEL=claude-sonnet-4[/]")
                console.print("    [cyan]export KEYNOTE_RECAP_MODEL=gpt-4o[/]")
                console.print("  Or set per-stage in config.yaml under llm.models.extract")
                console.print()
                console.print("  See README → 'Model Selection' section for the verified list.")
                raise VisionCapabilityError(r["vision_error"])
            if not r["ok"]:
                console.print(f"    [red]Batch failed: {r['error']}[/]")
                for c in batch:
                    rejected.append({
                        "filename": c.filename,
                        "rejection_reason": f"batch error: {r['error']}",
                    })
                progress.advance(task, advance=len(batch))
                continue
            track(state, stage="extract", model=cfg.llm.models.extract,
                  input_tokens=r["in_tokens"], output_tokens=r["out_tokens"])
            _merge_batch_result(r["data"], batch, selected, rejected)
            progress.advance(task, advance=len(batch))

    # ─── v0.3.1 A4: drop low-info-density frames before rescue/cap ───
    # Vision LLM sometimes self-assigns info_density < 0.70 but still puts
    # the frame in selected (prompt-only soft constraint). Hard-filter here.
    selected, dropped_lowd = _enforce_density_floor(
        selected, threshold=M.EXTRACT_INFO_DENSITY_MIN
    )
    if dropped_lowd:
        console.print(
            f"  [yellow]density filter: dropped {len(dropped_lowd)} frames "
            f"(info_density < {M.EXTRACT_INFO_DENSITY_MIN})[/]"
        )

    # ─── Floor enforcement: rescue pass if LLM was too conservative ───
    # M4 fix: previously we only capped to max; if LLM rejected too aggressively
    # we'd silently produce a 12-image report. Now if we're under the floor,
    # we promote rejected frames back from highest scorer score.
    #
    # v0.3.1: rescue frames now use info_density = M.EXTRACT_INFO_DENSITY_MIN
    # (not 0.6) so they survive the density filter above; if scorer score is
    # decent, treat them as floor-quality candidates. Truly bad rescue
    # candidates remain rejected by the post-rescue _check_extract_floors gate.
    if len(selected) < M.EXTRACT_FINAL_COUNT_MIN:
        gap = M.EXTRACT_FINAL_COUNT_MIN - len(selected)
        console.print(
            f"  [yellow]Selected only {len(selected)} (floor: "
            f"{M.EXTRACT_FINAL_COUNT_MIN}); promoting top {gap} "
            f"rescue candidates by scorer score[/]"
        )
        selected_names = {f.filename for f in selected}
        # Sort rejected by original scorer score (descending)
        rejected_with_score = []
        for r in rejected:
            fname = r.get("filename", "")
            if fname in selected_names:
                continue
            cand = next((c for c in candidates if c.filename == fname), None)
            if cand is None:
                continue
            rejected_with_score.append((cand, r))
        rejected_with_score.sort(key=lambda x: x[0].score, reverse=True)

        promoted = 0
        for cand, _r in rejected_with_score:
            if promoted >= gap:
                break
            selected.append(SelectedFrame(
                filename=cand.filename,
                timestamp_s=cand.timestamp_s,
                category="other",
                caption=f"[补救入选] 来自 {format_duration(cand.timestamp_s)} "
                        f"附近的画面（演讲上下文：{cand.context_subtitle[:120]}）",
                recommended_section="",
                info_density=M.EXTRACT_INFO_DENSITY_MIN,
                relevance=M.EXTRACT_INFO_DENSITY_MIN,
                source="frame_extract_rescue",
            ))
            promoted += 1
        console.print(f"  [yellow]Promoted {promoted} frames; total now {len(selected)}[/]")

    # ─── Global deduplication by perceptual hash ───
    # Two near-identical frames (e.g. consecutive samples of the same slide)
    # get collapsed; we keep the one with higher info_density.
    selected = _dedupe_by_phash(selected, frames_dir)

    # Cap to final_count_max — in case rescue + dedupe still left too many
    if len(selected) > M.EXTRACT_FINAL_COUNT_MAX:
        selected.sort(key=lambda f: (f.info_density + f.relevance), reverse=True)
        selected = selected[: M.EXTRACT_FINAL_COUNT_MAX]

    selected.sort(key=lambda f: f.timestamp_s)

    # ─── v0.3.1 A1/A3: hard floor gate (count + live ratio) ───
    # Raises ExtractFloorError → caught by pipeline retry orchestration
    # (which retries stage 3 with last-failures injected into the prompt).
    # Do NOT silently ship a sub-floor selection.
    _check_extract_floors(
        selected,
        count_min=M.EXTRACT_FINAL_COUNT_MIN,
        live_ratio_min=M.EXTRACT_LIVE_RATIO_MIN,
    )

    # Move selected frames to frames/ for the final report
    final_dir = output_dir / "frames"
    final_dir.mkdir(exist_ok=True)
    for f in selected:
        src = frames_dir / f.filename
        dst = final_dir / f.filename
        if src.exists() and not dst.exists():
            src.rename(dst)

    state.selected_frames = selected
    state.rejected_frames = rejected
    state.last_completed_stage = 3.0
    state.save()

    console.print(
        f"  Selected {len(selected)} / {len(candidates)} "
        f"(rejected {len(rejected)})"
    )
    console.print("[green]✓ Stage 3 done[/]\n")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Prompt building
# ──────────────────────────────────────────────────────────────────────────────
def _load_system_prompt() -> str:
    """Load system part from prompts/03-extract-vision-filter.md (between # System and # User Template)."""
    if not PROMPT_FILE.exists():
        return _FALLBACK_SYSTEM
    text = PROMPT_FILE.read_text()
    # Find # System ... # User Template
    if "# System" in text and "# User Template" in text:
        body = text.split("# System", 1)[1].split("# User Template", 1)[0]
        return body.strip()
    return _FALLBACK_SYSTEM


_FALLBACK_SYSTEM = """你是一位资深视觉编辑，正在为科技发布会复盘简报筛选关键帧。

严格遵守筛图三原则：
1. 信息量：含可读数据、产品 UI、技术架构图、对比表格、产品照片、合作伙伴 logo 墙
2. 相关性：与所在章节直接相关
3. 去重：同信息严格去重

必须拒绝：
- 纯标题页（如「Gemini Omni」单行大字）
- 营销 slogan（如「Bring any idea to life」）
- 品牌 logo 大字
- 过场页 / 章节分隔页
- 演讲者特写（除非演讲者本人是发布主角）
- 远景会场
- 同信息多视角（去重）

输出严格 JSON 格式：
{
  "selected_frames": [
    {
      "filename": "frame_00042.jpg",
      "category": "demo|product|data|architecture|partner_logos|other",
      "caption": "<完整 caption：是什么+讲什么+上下文>",
      "recommended_section": "<章节归属>",
      "info_density": 0.85,
      "relevance_to_section": 0.92
    }
  ],
  "rejected_frames": [
    {"filename": "frame_00003.jpg", "rejection_reason": "<原因>"}
  ]
}
"""


def _build_user_text(
    batch: list,
    transcript: str,
    title: str,
    duration: str,
    batch_start: int,
) -> str:
    """Build per-batch user prompt with frame metadata."""
    lines = [
        "# 视频信息",
        f"- 标题：{title}",
        f"- 时长：{duration}",
        "",
        "# 字幕全文（已截断到 30K 字符）",
        "```",
        transcript,
        "```",
        "",
        f"# 候选帧（本批 {len(batch)} 张，全局序号 {batch_start + 1} – {batch_start + len(batch)}）",
        "",
    ]

    for i, c in enumerate(batch, start=1):
        ts_str = format_duration(c.timestamp_s)
        ctx = c.context_subtitle.replace("\n", " ")[:300]
        lines.append(f"## Frame {i}：{c.filename}")
        lines.append(f"- 时间戳：{ts_str}")
        lines.append(f"- frame_scorer 分数：{c.score:.1f} / 100")
        lines.append(f"- 当时字幕（±15s）：{ctx}")
        lines.append("")

    # Per-batch quota: each batch must aim to keep ~50-65% so the cumulative
    # selection across all batches lands in the global 35-50 floor/ceiling.
    # Without this, batch-level LLMs uniformly reject "marginal" frames and
    # the global count collapses to ~15 — the symptom users reported.
    keep_floor = max(4, int(len(batch) * 0.50))
    keep_ceil = max(keep_floor + 1, int(len(batch) * 0.70))

    lines.append("---")
    lines.append("")
    lines.append(
        f"## 本批筛选硬约束（必读）\n\n"
        f"**本批 {len(batch)} 张，必须保留 {keep_floor}-{keep_ceil} 张。**\n\n"
        f"原因：本任务全局目标 35-50 张，分多批处理。如果你只保留 1-2 张，"
        f"全局会塌陷到 < 20 张（已发生过）。\n\n"
        f"### 数量优先于完美\n\n"
        f"- 如果一张图**不是**演讲者特写/纯黑过场/纯 slogan 标题页，**就保留**\n"
        f"- 「PPT 不算特别精彩」**不是**拒绝理由 → 保留\n"
        f"- 「内容和上一张有点像」**不是**拒绝理由 → 全局去重在后面单独做\n"
        f"- 演讲者远景但 PPT 占主体 → 保留\n"
        f"- demo 截图但有产品 UI → 保留\n\n"
        f"### 必须拒绝（仅这些情况）\n\n"
        f"- 演讲者特写脸占主体（PPT 不可见）\n"
        f"- 纯黑/纯白/纯渐变过场\n"
        f"- 仅 slogan 文字（如 'Bring any idea to life'）\n"
        f"- 全屏品牌 logo（如 Google 大字）\n\n"
        f"输出 JSON。selected_frames 至少 {keep_floor} 项，rejected_frames "
        f"必须给 rejection_reason。图片按上面顺序与正文 frame_NN 对应。"
    )

    return "\n".join(lines)


def _dedupe_by_phash(
    selected: list[SelectedFrame], frames_dir: Path, hamming_threshold: int = 6
) -> list[SelectedFrame]:
    """Drop near-duplicate frames using a 64-bit perceptual hash (PIL only).

    For pairs within ``hamming_threshold`` Hamming distance, keep the frame
    with the higher (info_density + relevance) score. This catches the common
    case where stage 2 sampled multiple frames within a few seconds of the
    same slide.
    """
    try:
        from PIL import Image
    except ImportError:
        return selected

    def _phash(path: Path) -> int:
        try:
            img = Image.open(path).convert("L").resize((9, 8))
            pixels = list(img.getdata())
            # 8 rows of 9 pixels → 8 bits per row → 64 bits total
            bits = 0
            for row in range(8):
                row_pixels = pixels[row * 9 : row * 9 + 9]
                for col in range(8):
                    if row_pixels[col] > row_pixels[col + 1]:
                        bits = (bits << 1) | 1
                    else:
                        bits = bits << 1
            return bits
        except Exception:
            return 0

    def _hamming(a: int, b: int) -> int:
        return bin(a ^ b).count("1")

    # Compute hashes for each selected frame
    hashes: dict[str, int] = {}
    for f in selected:
        p = frames_dir / f.filename
        if p.exists():
            hashes[f.filename] = _phash(p)

    # Sort by (info_density + relevance) descending — higher quality wins
    sorted_frames = sorted(
        selected, key=lambda f: f.info_density + f.relevance, reverse=True
    )

    kept: list[SelectedFrame] = []
    kept_hashes: list[int] = []
    drops = 0
    for f in sorted_frames:
        h = hashes.get(f.filename, 0)
        if h == 0:
            kept.append(f)
            continue
        is_dup = any(_hamming(h, kh) <= hamming_threshold for kh in kept_hashes)
        if is_dup:
            drops += 1
            continue
        kept.append(f)
        kept_hashes.append(h)

    if drops:
        console.print(f"  [dim]Dedup: dropped {drops} near-duplicate frames[/]")
    return kept


def _merge_batch_result(
    data: dict,
    batch: list,
    selected_out: list[SelectedFrame],
    rejected_out: list[dict],
) -> None:
    """Merge LLM batch JSON into selected/rejected lists."""
    name_to_candidate = {c.filename: c for c in batch}

    for item in data.get("selected_frames", []):
        fname = item.get("filename", "")
        if fname not in name_to_candidate:
            continue
        c = name_to_candidate[fname]
        # M6: is_live defaults to True for backward compat — old prompts
        # didn't ask for this field. New prompts populate it explicitly.
        is_live_raw = item.get("is_live", True)
        is_live = bool(is_live_raw) if isinstance(is_live_raw, (bool, int)) else True
        # If LLM marked is_live=false but caption doesn't already start with
        # the disclaimer, prepend it so downstream readers see the warning.
        caption = item.get("caption", "")
        if not is_live and not caption.startswith("（插播官方渲染）"):
            caption = f"（插播官方渲染）{caption}"
        selected_out.append(SelectedFrame(
            filename=fname,
            timestamp_s=c.timestamp_s,
            category=item.get("category", "other"),
            caption=caption,
            recommended_section=item.get("recommended_section", ""),
            info_density=float(item.get("info_density", 0.7)),
            relevance=float(item.get("relevance_to_section", 0.7)),
            source="frame_extract",
            is_live=is_live,
            what_can_be_read=item.get("what_can_be_read", ""),
        ))

    for item in data.get("rejected_frames", []):
        rejected_out.append({
            "filename": item.get("filename", ""),
            "rejection_reason": item.get("rejection_reason", ""),
        })


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 — image quality hard floor helpers (A1/A3/A4)
# ──────────────────────────────────────────────────────────────────────────────
def _enforce_density_floor(
    frames: list[SelectedFrame],
    threshold: float = M.EXTRACT_INFO_DENSITY_MIN,
) -> tuple[list[SelectedFrame], list[SelectedFrame]]:
    """v0.3.1 A4: drop frames whose info_density < threshold.

    Returns (kept, dropped). Vision LLM occasionally self-marks frames
    info_density < 0.70 but still keeps them in selected_frames; this
    function turns that prompt-only soft constraint into a code filter.

    Frames exactly at threshold are kept (>=).
    """
    kept = [f for f in frames if (f.info_density or 0.0) >= threshold]
    dropped = [f for f in frames if (f.info_density or 0.0) < threshold]
    return kept, dropped


def _check_extract_floors(
    selected: list[SelectedFrame],
    count_min: int = M.EXTRACT_FINAL_COUNT_MIN,
    live_ratio_min: float = M.EXTRACT_LIVE_RATIO_MIN,
) -> None:
    """v0.3.1 A1/A3: raise ExtractFloorError if hard floors fail.

    Floors checked here (cheap / deterministic, run after dedupe + cap):
      - total count >= count_min (default 35; methodology.EXTRACT_FINAL_COUNT_MIN)
      - live ratio >= live_ratio_min (default 0.50)

    Per-section / per-mainline checks live in verify (need report.md and
    section structure; see check_per_section_floor).

    Raising ExtractFloorError signals to pipeline retry orchestration that
    stage 3 should be re-run with last-failures injected into the prompt.
    """
    n = len(selected)
    if n < count_min:
        raise ExtractFloorError(
            f"selected_frames count {n} < {count_min} "
            f"(EXTRACT_FINAL_COUNT_MIN). Vision LLM rejected too aggressively; "
            f"retry will inject 'select more frames' directive."
        )
    n_live = sum(1 for f in selected if f.is_live)
    ratio = n_live / n if n else 0.0
    if ratio < live_ratio_min:
        raise ExtractFloorError(
            f"live ratio {ratio:.0%} < {live_ratio_min:.0%} "
            f"({n_live}/{n} live frames). Too many marketing renders / "
            f"insert clips vs. live keynote frames; retry will boost live "
            f"frame priority in prompt."
        )
