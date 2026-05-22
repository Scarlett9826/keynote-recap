"""Stage 5: draft — outline → write → callout.

5.1 outline:  build chapter outline (by publish priority, not time order)
5.2 write:    write full body (## 一 to ## 信源说明) following methodology
5.3 callout:  go back and write `<div class="callout">` 整体概要 from body

Output: <output>/report.md  (full markdown ready for stage 5.5 verify)
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient
from ..state import State
from ..util import format_duration

console = Console()

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def _pick_draft_prompt(cfg: Config) -> Path:
    """Resolve the draft-write prompt file based on cfg.draft.tier.

    Tiers:
        easy     → 05-draft-write-easy.md (looser constraints, ~37% shorter)
        standard → 05-draft-write.md      (current default; 21 forbidden phrases)
        strict   → 05-draft-write-strict.md (incremental constraints on top)

    Falls back to standard if the requested tier file is missing or the tier
    string is unrecognized; logs a warning to stderr.
    """
    tier = (cfg.draft.tier or "standard").lower()
    candidates = {
        "easy":     PROMPTS_DIR / "05-draft-write-easy.md",
        "standard": PROMPTS_DIR / "05-draft-write.md",
        "strict":   PROMPTS_DIR / "05-draft-write-strict.md",
    }
    chosen = candidates.get(tier)
    if chosen is None or not chosen.exists():
        # Fall back silently; the standard prompt always exists.
        return PROMPTS_DIR / "05-draft-write.md"
    return chosen
METHODOLOGY_DIR = Path(__file__).parent.parent.parent.parent / "methodology"


def run(state: State, cfg: Config) -> State:
    """Execute stage 5 (5.1 + 5.2 + 5.3)."""
    console.print("[bold]Stage 5 — draft[/]")
    client = LLMClient(cfg.llm)

    output_dir = Path(state.output_dir)

    # ─── 5.1 outline ───
    console.print("  [5.1] outline...")
    outline = _build_outline(state, cfg, client)
    outline_path = output_dir / "outline.md"
    outline_path.write_text(outline)
    state.outline_path = str(outline_path)
    console.print(f"        wrote {outline_path.name}")

    # ─── 5.2 write body ───
    console.print("  [5.2] write body...")
    body = _write_body(state, cfg, client, outline)

    # ─── 5.3 callout ───
    console.print("  [5.3] callout...")
    callout = _write_callout(state, cfg, client, body)

    # ─── Combine ───
    title = _extract_title(body) or state.video.title
    final = _assemble_report(title, callout, body)

    report_path = output_dir / "report.md"
    report_path.write_text(final)
    state.report_md_path = str(report_path)
    state.last_completed_stage = 5.0
    state.save()

    n_lines = len(final.split("\n"))
    n_imgs = final.count("![")
    n_citations = final.count("📎 **补充信源**")
    console.print(f"  Report: {n_lines} lines / {n_imgs} images / {n_citations} citations")
    console.print("[green]✓ Stage 5 done[/]\n")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# 5.1 outline
# ──────────────────────────────────────────────────────────────────────────────
def _build_outline(state: State, cfg: Config, client: LLMClient) -> str:
    system = _load_section(PROMPTS_DIR / "05-draft-outline.md", "System")
    style_rules = _load_methodology()

    user = _build_user_for_outline(state, style_rules)

    text, in_t, out_t = client.chat(
        model=cfg.llm.models.draft,
        system=system,
        user=user,
        temperature=0.4,
        max_tokens=4000,
    )
    track(state, stage="draft_outline", model=cfg.llm.models.draft,
          input_tokens=in_t, output_tokens=out_t)
    return text


def _build_user_for_outline(state: State, style_rules: str) -> str:
    # Use full transcript: outline must see all product names mentioned
    # Gemini 2.5 Pro context = 1M tokens, transcript ≈ 25K tokens, plenty of room
    transcript = state.video.transcript or ""
    detected_products = _detect_product_names(transcript)
    research_notes = ""
    if state.research_notes_path:
        try:
            research_notes = Path(state.research_notes_path).read_text()[:15000]
        except Exception:
            pass

    frames_summary = "\n".join(
        f"- {f.filename} @ {format_duration(f.timestamp_s)} → {f.recommended_section} | {f.caption[:80]}"
        for f in state.selected_frames[:60]
    )

    products_str = "\n".join(f"  - {p} (mentioned {n} times)" for p, n in detected_products)

    return f"""# 视频信息
- 标题：{state.video.title}
- 时长：{format_duration(state.video.duration_s)}

# 自动检测到的产品/协议名（字幕里出现 ≥ 2 次的关键词）

每个出现的产品名应当在大纲中有所体现：
{products_str}

# 完整字幕

```
{transcript}
```

# Research Notes
{research_notes}

# 已筛选关键帧（{len(state.selected_frames)} 张）
{frames_summary}

# 方法论摘要
{style_rules[:5000]}

---

请输出 markdown 大纲（按 prompts/05-draft-outline.md 要求）。
章节 12-15 个，按发布优先级排序，最后一章必须是「一点观察」。

**自检**：上方"自动检测到的产品/协议名"中，每个出现 ≥ 5 次的关键词，要么是某章节标题/副标题的一部分，要么是某子章节标题。
"""


# ──────────────────────────────────────────────────────────────────────────────
# 5.2 body
# ──────────────────────────────────────────────────────────────────────────────
def _write_body(state: State, cfg: Config, client: LLMClient, outline: str) -> str:
    system = _load_section(_pick_draft_prompt(cfg), "System")

    user = _build_user_for_body(state, outline)

    text, in_t, out_t = client.chat(
        model=cfg.llm.models.draft,
        system=system,
        user=user,
        temperature=0.5,
        max_tokens=16000,
    )
    track(state, stage="draft_body", model=cfg.llm.models.draft,
          input_tokens=in_t, output_tokens=out_t)
    return text


def _build_user_for_body(state: State, outline: str) -> str:
    # Use full transcript: body must accurately quote all sections
    transcript = state.video.transcript or ""
    research_notes = ""
    if state.research_notes_path:
        try:
            research_notes = Path(state.research_notes_path).read_text()[:20000]
        except Exception:
            pass

    # Build a numbered, very explicit frame list emphasizing the EXACT filename.
    # CRITICAL: keep `f.filename` verbatim — do NOT reconstruct from parts.
    # Past bug: rebuilt filename from `f.filename.split('_')[1]` lost the .jpg
    # suffix and confused the LLM into inventing semantic names like
    # `frame_gt_01.jpg` instead of using `frame_00457.jpg`.
    frames_block = "\n".join(
        f"[{i+1}] filename: `{f.filename}` "
        f"  ({format_duration(f.timestamp_s)} → {f.recommended_section})\n"
        f"     引用语法: ![{f.caption[:60]}](frames/{f.filename})\n"
        f"     caption: {f.caption}"
        for i, f in enumerate(state.selected_frames)
    )

    # All allowed filenames as a flat list for easy verification by LLM.
    allowed_filenames = ", ".join(f.filename for f in state.selected_frames)

    return f"""# 视频信息
- 标题：{state.video.title}
- 频道：{state.video.uploader}
- 时长：{format_duration(state.video.duration_s)}
- 链接：{state.url}

# 章节大纲（来自 stage 5.1，必须严格遵守）
{outline}

# 完整字幕
```
{transcript}
```

# Research Notes（联网补充事实）
{research_notes}

# 已筛选关键帧（{len(state.selected_frames)} 张）— caption 必须直接复用，不要改写
{frames_block}

# ⚠️ 允许使用的 filename 完整清单（不要使用此清单外的任何文件名）
{allowed_filenames}

---

请按 prompts/05-draft-write.md 要求输出**正文部分**（从 `## 一、` 到 `## 信源说明`）。

**关键约束**：
1. **总图数 25-40 张**（少于 25 张视为质量不达标）—— 你拿到 {len(state.selected_frames)} 张候选，请用 25-35 张
2. **filename 严禁编造**——只能用上方"已筛选关键帧"列表中给的真实文件名（形如 `frame_00457.jpg`）。绝对不能写 `frames/01-spark-intro.jpg` 之类的语义化文件名。
3. 每个 ## 章节至少 1 张图（违反则会被打回）
4. 重要章节 4-6 张图，次要章节 2-3 张图
5. 至少 10 个 `> 📎 **补充信源**：[Source](URL)` 块（少于 8 个视为质量不达标）—— 每个主要章节至少 1 个 📎 块
6. 使用 `frames/<filename>` 路径（不是 frames_raw/）
7. 按发布优先级排章节，不按时间序
8. 文末必须有：`## 十X、一点观察（独立判断，非发布会原话）` + `## 信源说明`

**⛔ filename 编造 = 最严重错误**

下面是 3 个**绝对禁止**的写法（每条都会让生成的报告里图片显示为损坏）：

```
❌ ![介绍页](frames/frame_gt_01.jpg)         ← gt_01 是编的语义化名
❌ ![Spark 平台](frames/01-spark-intro.jpg)  ← 01-spark-intro 不在清单里
❌ ![待补充](frames/frame_intro.jpg)         ← intro 是你自己起的
```

正确写法（直接从上方清单里复制 filename，**不要改写、不要简化**）：
```
✅ ![Spark 主舞台](frames/{state.selected_frames[0].filename if state.selected_frames else 'frame_00123.jpg'})
```

**⚠️ 输出前自检**：你写完正文后，扫一遍自己写的所有 `![...](frames/XXX)`：
- 每个 `XXX` 是不是**字面**出现在上方"已筛选关键帧"列表里？
- 如果有任何一个不在，**立刻改掉**（从清单里挑一个相邻时间戳的真实 filename 替换）。
- 不允许出现 `待补充`、`<filename>`、`xx`、`gt_01`、`spark-intro` 这类占位/语义化命名。

**不要**输出整体概要 callout（由 stage 5.3 单独写）。
**不要**输出 `# 标题`（由最终组装时加）。
直接从 `## 一、` 开始写。
"""


# ──────────────────────────────────────────────────────────────────────────────
# 5.3 callout
# ──────────────────────────────────────────────────────────────────────────────
def _write_callout(state: State, cfg: Config, client: LLMClient, body: str) -> str:
    system = _load_section(PROMPTS_DIR / "05-draft-callout.md", "System")

    user = f"""# 视频信息
- 标题：{state.video.title}

# 已写好的正文
```markdown
{body[:60000]}
```

---

请按 prompts/05-draft-callout.md 要求输出整体概要 callout。
只输出 `<div class="callout" markdown="1">` 块（含 `## 📌 整体概要` 标题），不输出其他内容。
"""

    text, in_t, out_t = client.chat(
        model=cfg.llm.models.draft,
        system=system,
        user=user,
        temperature=0.4,
        max_tokens=4000,
    )
    track(state, stage="draft_callout", model=cfg.llm.models.draft,
          input_tokens=in_t, output_tokens=out_t)
    return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    """Remove ```markdown / ``` wrappers if LLM added them around the callout."""
    t = text.strip()
    # Match opening fence ```... up to first newline
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
    # Match closing fence
    if t.endswith("```"):
        last_fence = t.rfind("```")
        t = t[:last_fence].rstrip()
    return t.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Assembly
# ──────────────────────────────────────────────────────────────────────────────
def _assemble_report(title: str, callout: str, body: str) -> str:
    return f"# {title}\n\n{callout}\n\n---\n\n{body}\n"


def _extract_title(body: str) -> str:
    """Extract # title if LLM included one anyway."""
    for line in body.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
import re

# Curated list of product/protocol names to detect in any keynote transcript.
# Detected names are passed to outline LLM as "must consider these products".
_PRODUCT_PATTERNS = [
    # Agent layer
    "Spark", "Antigravity", "Subagent", "Project Astra",
    # Models
    r"Gemini\s+\d", "Omni", "world model", r"TPU\s+\w", "Trillium",
    # Search / Workspace / YouTube
    "AI Mode", "AI Overviews", "Ask YouTube", "Docs Live", "Universal Cart",
    # Protocols
    "UCP", "AP2", "A2A", "MCP",
    # Creative tools
    "Pics", "Stitch", "Flow", "Veo", "Imagen",
    # Audio
    "Neural Expressive", "Chirp",
    # Hardware
    "Pixel", "glasses", "XR", "Halo",
    # Health / Science
    "Fitbit", "Health", "AlphaFold", "AlphaProteo",
    # Safety
    "SynthID", "Content Credentials",
    # Pricing
    "Ultra", "AI Pro", "AI Ultra",
    # Other
    "NotebookLM", "AI Studio", "Vertex", "Firebase",
]


def _detect_product_names(transcript: str) -> list[tuple[str, int]]:
    """Detect product/protocol names mentioned in transcript.

    Returns list of (name, count) for names mentioned ≥ 2 times,
    sorted by count descending. Used to feed outline LLM a "must consider" list.
    """
    if not transcript:
        return []
    counts: dict[str, int] = {}
    for pattern in _PRODUCT_PATTERNS:
        try:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
        except re.error:
            continue
        if matches:
            counts[pattern] = len(matches)
    # Filter ≥ 2 mentions, sort by count desc
    filtered = [(p, c) for p, c in counts.items() if c >= 2]
    filtered.sort(key=lambda x: -x[1])
    return filtered[:30]


def _load_section(prompt_file: Path, section: str) -> str:
    if not prompt_file.exists():
        return ""
    text = prompt_file.read_text()
    marker = f"# {section}"
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    next_h = after.find("\n# ")
    body = after[:next_h] if next_h > 0 else after
    return body.strip()


def _load_methodology() -> str:
    """Concatenate key methodology files for inclusion in prompts."""
    parts = []
    for fname in ["style-rules.md", "filter-three-principles.md",
                   "source-attribution.md", "report-skeleton.md"]:
        p = METHODOLOGY_DIR / fname
        if p.exists():
            parts.append(f"=== {fname} ===\n{p.read_text()}")
    return "\n\n".join(parts)
