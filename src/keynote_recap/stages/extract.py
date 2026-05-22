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

from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient
from ..state import SelectedFrame, State
from ..util import format_duration

console = Console()

# Path resolution: prompts/03-extract-vision-filter.md
PROMPT_FILE = Path(__file__).parent.parent.parent.parent / "prompts" / "03-extract-vision-filter.md"

BATCH_SIZE = 10        # frames per vision call
MAX_TRANSCRIPT_CHARS = 30000  # truncate transcript for batch prompts


def run(state: State, cfg: Config) -> State:
    """Execute stage 3."""
    if not state.candidate_frames:
        raise RuntimeError("Stage 3 requires stage 2 (candidate_frames) to be done first.")

    console.print("[bold]Stage 3 — vision filter (three principles)[/]")

    output_dir = Path(state.output_dir)
    frames_dir = output_dir / "frames_raw"

    client = LLMClient(cfg.llm)
    candidates = state.candidate_frames
    console.print(f"  Filtering {len(candidates)} candidates in batches of {BATCH_SIZE}")

    transcript = (state.video.transcript or "")[:MAX_TRANSCRIPT_CHARS]
    title = state.video.title or ""
    duration = format_duration(state.video.duration_s)

    # System prompt embedded (no jinja deps)
    system = _load_system_prompt()

    selected: list[SelectedFrame] = []
    rejected: list[dict] = []

    with Progress(transient=True) as progress:
        task = progress.add_task("vision filter", total=len(candidates))

        for batch_start in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[batch_start : batch_start + BATCH_SIZE]
            batch_paths = [frames_dir / c.filename for c in batch]

            user_text = _build_user_text(batch, transcript, title, duration, batch_start)

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
                track(state, stage="extract", model=cfg.llm.models.extract,
                      input_tokens=in_t, output_tokens=out_t)

                data = client.parse_json(text)
                _merge_batch_result(data, batch, selected, rejected)
            except Exception as e:
                console.print(f"    [red]Batch failed: {e}[/]")
                # Conservative fallback: keep all batch as rejected (they may be retried)
                for c in batch:
                    rejected.append({"filename": c.filename, "rejection_reason": f"batch error: {e}"})

            progress.advance(task, advance=len(batch))

    # Cap to final_count_max — in case LLM was too generous
    if len(selected) > cfg.frame_filter.final_count_max:
        selected.sort(key=lambda f: (f.info_density + f.relevance), reverse=True)
        selected = selected[: cfg.frame_filter.final_count_max]

    selected.sort(key=lambda f: f.timestamp_s)

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

    lines.append("---")
    lines.append("")
    lines.append("请按三原则筛选这批 frame，输出 JSON。"
                 "selected_frames 中只保留信息量足、相关、不重复的；"
                 "rejected_frames 中放被拒的（必须给 rejection_reason）。"
                 "图片按上面顺序与正文 frame_NN 对应。")

    return "\n".join(lines)


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
        selected_out.append(SelectedFrame(
            filename=fname,
            timestamp_s=c.timestamp_s,
            category=item.get("category", "other"),
            caption=item.get("caption", ""),
            recommended_section=item.get("recommended_section", ""),
            info_density=float(item.get("info_density", 0.7)),
            relevance=float(item.get("relevance_to_section", 0.7)),
            source="frame_extract",
        ))

    for item in data.get("rejected_frames", []):
        rejected_out.append({
            "filename": item.get("filename", ""),
            "rejection_reason": item.get("rejection_reason", ""),
        })
