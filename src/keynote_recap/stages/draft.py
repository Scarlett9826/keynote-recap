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
    final = _assemble_report(title, callout, body, state, cfg)

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
        max_tokens=12000,
    )
    track(state, stage="draft_body", model=cfg.llm.models.draft,
          input_tokens=in_t, output_tokens=out_t)
    return text


def _build_user_for_body(state: State, outline: str) -> str:
    # Use full transcript: body must accurately quote all sections.
    # Truncate very long transcripts (~ 40000 char cap) to keep stage 5.2
    # input within gateway timeout budget. v0.3.7 keeps the cap; longer
    # term, sectioned chunking aligned with outline is the right fix
    # (P4 in CHANGELOG analysis).
    _raw_transcript = state.video.transcript or ""
    if len(_raw_transcript) > 40000:
        transcript = (
            _raw_transcript[:40000]
            + "\n\n[... 字幕已截断，仅保留前 40000 字符以控制长度 ...]"
        )
    else:
        transcript = _raw_transcript
    research_notes = ""
    if state.research_notes_path:
        try:
            research_notes = Path(state.research_notes_path).read_text()[:20000]
        except Exception:
            pass

    # M6 D1 — deterministic placement.
    # Bucket frames by recommended_section BEFORE the LLM sees them. The LLM
    # is then told exactly which frames are available per chapter and may pick
    # any subset (1+) within the bucket but MUST NOT cross-bucket. This turns
    # placement from a generative "guess where this fits" task into a
    # constrained "pick from this list" task.
    section_buckets = _bucket_by_section(state.selected_frames, outline)
    frames_block = _format_buckets_for_prompt(section_buckets)

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

# 已筛选关键帧（{len(state.selected_frames)} 张，按章节分桶）— caption 必须直接复用
#
# ⚠️ **配位硬约束**：每章只能用本章桶内列出的图，不能跨桶。
# 例：「### 一、模型层」桶里有 5 张，你可以挑其中 3-5 张用在这章；
# 但绝不能把「四、订阅价」桶里的图放进「一、模型层」章。
# 这条规则由 stage 5.5 自动校验，违反会触发重写。
{frames_block}

# ⚠️ 允许使用的 filename 完整清单（不要使用此清单外的任何文件名）
{allowed_filenames}

---

请按 prompts/05-draft-write.md 要求输出**正文部分**（从 `## 一、` 到 `## 信源说明`）。

**关键约束**：
1. **总图数 25-40 张**（少于 25 张视为质量不达标）—— 你拿到 {len(state.selected_frames)} 张候选，请用 25-35 张
2. **filename 严禁编造**——只能用上方"已筛选关键帧"列表中给的真实文件名（形如 `frame_00457.jpg`）。绝对不能写 `frames/01-spark-intro.jpg` 之类的语义化文件名。
3. **每章只能用本章桶内的图**（D1 配位硬约束，违反会被打回）：
   - 桶内有 N 张候选 → 本章必须挑 1 ~ N 张
   - 桶为空 → 本章无图（不要从其他章桶强行借图）
   - 不允许跨桶使用图
4. 重要章节优先用满本桶 4-6 张，次要章节 2-3 张
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
def _assemble_report(title: str, callout: str, body: str, state, cfg) -> str:
    """Compose final report.md with v0.2.4 integrity layer.

    Layout:
        ---  ← YAML frontmatter (M9.5: provenance + sha)
        ...
        ---
        # title
        > integrity callout (M9.4: ✅ or ⚠️ depending on stages_skipped)
        > ...

        ---
        body (LLM-written)

    The frontmatter's ``content-sha256`` covers everything starting from
    "# title" — the integrity callout is part of the signed body so a
    later edit (e.g. agent removing the ⚠️ block to hide a half-run)
    breaks sha verification.
    """
    from datetime import datetime

    from .. import __version__
    from ..frontmatter import attach_frontmatter

    integrity = _build_integrity_callout(state, cfg)
    body_text = f"# {title}\n\n{integrity}\n\n{callout}\n\n---\n\n{body}\n"

    meta: dict = {
        "keynote-recap-version": __version__,
        "generated-at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source-url": state.url,
        "stages-completed": [_fmt_stage(s) for s in sorted(state.stages_completed)],
        "stages-skipped": [_fmt_stage(s) for s in sorted(state.stages_skipped)],
        "model-extract": state.models_used.get("extract", "unknown"),
        "model-extract-tier": state.model_tiers.get("extract", "unknown"),
        "model-draft": state.models_used.get("draft", "unknown"),
        "model-draft-tier": state.model_tiers.get("draft", "unknown"),
    }
    # v0.3.7 P2: stamp low-yield-override into frontmatter so render banner
    # downgrades to half-run yellow tier and downstream verifiers can see
    # that the report shipped under a sanctioned floor breach.
    if getattr(state, "low_yield_override", False):
        meta["low-yield-override"] = True
        meta["low-yield-details"] = dict(state.low_yield_details or {})
    # v0.3.7 P3: stamp downloaded video resolution (when probed). Helps
    # downstream readers correlate "low extraction yield" with the input
    # quality that caused it.
    if state.video and state.video.actual_height:
        meta["video-actual-resolution"] = state.video.actual_resolution
    # BUG-5: stamp density distribution so readers can assess gateway quality.
    dd = getattr(state, "extract_density_distribution", {}) or {}
    if dd:
        meta["extract-density-distribution"] = dict(dd)
    return attach_frontmatter(meta, body_text)


def _fmt_stage(s: float) -> str:
    """Render stage number for frontmatter list (1.0 → '1', 5.5 → '5.5')."""
    return str(int(s)) if s == int(s) else str(s)


def _build_integrity_callout(state, cfg) -> str:
    """M9.4: mandatory integrity callout. Always emitted, two templates.

    Healthy:
        > ✅ 本次 keynote-recap 完整运行
        > - 全部 7 stage 完成
        > - 模型：claude-opus-4 (verified multimodal)
        > - 引用数：12，验证通过：12

    Half-run:
        > ⚠️ 本次 keynote-recap 部分运行
        > - 跳过：stage 1（字幕，原因：...），stage 4（事实查证）
        > - 完整：stage 2, 3, 5, 5.5
        > - 模型：your-vendor/text-only-v1（不在 verified 列表）
        > - 本报告无法验证以下方法论项：...

    Agent compressing the report MUST confront this — keep it (exposes
    half-run state in published doc) or delete it (breaks sha check).
    """
    skipped = sorted(state.stages_skipped)
    extract_model = state.models_used.get("extract", "unknown")
    extract_tier = state.model_tiers.get("extract", "unknown")
    n_citations = len(state.verified_facts) if state.verified_facts else 0
    low_yield = bool(getattr(state, "low_yield_override", False))

    is_healthy = (
        not skipped
        and extract_tier == "verified_multimodal"
        and n_citations >= 8
        and not low_yield  # v0.3.7 P2: low-yield override forces half-run
    )

    if is_healthy:
        lines = [
            "> ✅ 本次 keynote-recap 完整运行",
            "> ",
            "> - 全部 7 stage 完成",
            f"> - 模型：{extract_model}（verified multimodal）",
            f"> - 引用数：{n_citations}，全部验证通过",
        ]
        return "\n".join(lines)

    # Half-run template
    completed = sorted(state.stages_completed)
    skip_parts: list[str] = []
    for s in skipped:
        s_str = _fmt_stage(s)
        reason = state.stages_skip_reasons.get(s_str, "未知原因")
        skip_parts.append(f"stage {s_str}（{reason}）")
    skipped_line = "、".join(skip_parts) if skip_parts else "无"
    completed_line = "、".join(_fmt_stage(s) for s in completed) or "无"

    # Methodology items that cannot be verified given what was skipped
    cannot_verify: list[str] = []
    if 1.0 in skipped:
        cannot_verify.append("transcript 高频产品名 → 必须有图 对照")
    if 4.0 in skipped:
        cannot_verify.append("事实查证（引用 ≥ 8）")
    if extract_tier != "verified_multimodal":
        cannot_verify.append("视觉理解质量（当前模型不在 verified 列表）")
    # v0.3.7 P2: low-yield-override means stage 3 floors were not met.
    # Surface this as an explicit "cannot verify" item so the artifact
    # records what the override traded away.
    if low_yield:
        d = state.low_yield_details or {}
        cannot_verify.append(
            f"图像产出量门槛（低产出豁免：选中 {d.get('selected_count', '?')} 帧 / "
            f"地板 {d.get('count_floor', '?')}，"
            f"useful_ratio {(d.get('useful_ratio') or 0):.0%} / "
            f"地板 {(d.get('useful_ratio_floor') or 0):.0%}）"
        )

    cannot_line = "、".join(cannot_verify) if cannot_verify else "（无）"

    tier_zh = {
        "verified_multimodal": "verified 多模态",
        "known_text_only": "纯文本（不能看图）",
        "unknown": "未验证",
    }.get(extract_tier, extract_tier)

    lines = [
        "> ⚠️ 本次 keynote-recap 部分运行",
        "> ",
        f"> - 跳过：{skipped_line}",
        f"> - 完整：stage {completed_line}",
        f"> - 模型：{extract_model}（{tier_zh}）",
    ]
    if low_yield:
        d = state.low_yield_details or {}
        lines.append(
            f"> - **低产出豁免（--accept-low-yield）**：选中 "
            f"{d.get('selected_count', '?')} 帧（地板 {d.get('count_floor', '?')}），"
            f"useful_ratio {(d.get('useful_ratio') or 0):.0%}（地板 "
            f"{(d.get('useful_ratio_floor') or 0):.0%}）"
        )
    lines.append(f"> - 本报告无法验证以下方法论项：{cannot_line}")
    return "\n".join(lines)


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


# ──────────────────────────────────────────────────────────────────────────────
# M6 D1 — deterministic image-to-section bucket placement
# ──────────────────────────────────────────────────────────────────────────────
def _extract_outline_chapters(outline: str) -> list[str]:
    """Pull L1 chapter titles from a stage-5.1 outline markdown.

    Looks for lines like '## 一、模型层 — Gemini 3.5 ...' and returns the title
    line stripped of the leading '## '. Skips '一点观察' and '信源说明' which
    are reserved closing chapters that don't get image buckets.
    """
    chapters: list[str] = []
    for line in outline.split("\n"):
        line = line.strip()
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        # Skip reserved closing chapters (these are independent-judgement chapters,
        # not chapters that should consume keynote frames)
        if "信源说明" in title or "一点观察" in title or title.startswith("📌"):
            continue
        chapters.append(title)
    return chapters


def _bucket_by_section(
    frames: list, outline: str
) -> list[tuple[str, list]]:
    """Bucket selected frames by their recommended_section vs. outline chapters.

    Returns ordered list of (chapter_title, frames_in_bucket) tuples in the
    order chapters appear in the outline. A trailing bucket
    ('未分配（章节匹配失败，可挑选）', [...]) holds frames whose
    recommended_section didn't match any chapter — these are still allowed
    but flagged so the writer can place them where best fits.

    Matching is fuzzy: a frame matches a chapter if the chapter title contains
    any 2+ char substring of the frame's recommended_section, or vice versa.
    """
    chapters = _extract_outline_chapters(outline)
    if not chapters:
        # No structured outline → fall back to a single bucket
        return [("（大纲未识别，全部帧自由使用）", list(frames))]

    buckets: dict[str, list] = {ch: [] for ch in chapters}
    unassigned: list = []

    for f in frames:
        rec = (f.recommended_section or "").strip()
        if not rec:
            unassigned.append(f)
            continue
        matched = False
        # Try fuzzy substring match in either direction
        for ch in chapters:
            if _fuzzy_section_match(rec, ch):
                buckets[ch].append(f)
                matched = True
                break
        if not matched:
            unassigned.append(f)

    # Preserve outline order; drop empty buckets but keep the chapter listed
    # in the prompt (so writer knows to source elsewhere or warn)
    ordered: list[tuple[str, list]] = [(ch, buckets[ch]) for ch in chapters]
    if unassigned:
        ordered.append(("未分配（章节匹配失败，作者可灵活挑选）", unassigned))
    return ordered


def _fuzzy_section_match(rec: str, chapter: str) -> bool:
    """True if recommended_section and chapter title share a 2+ char keyword.

    Strips Chinese numerals/punctuation and compares 2+ char tokens.

    v0.3.4 P1: also tries 3-gram sliding-window overlap so Chinese compound
    tokens like "智能工厂" / "智能工厂介绍" share trigrams (智能工, 能工厂)
    even when neither is a substring of the other. Vision LLM (stage 3) emits
    ``recommended_section`` *before* stage 5 generates the real outline, so
    its phrasing won't match outline chapter titles word-for-word — this 3-gram
    fallback bridges that gap without an extra LLM call.

    Threshold: ≥ 2 shared trigrams to count as a match (single-trigram overlap
    is too noisy; e.g. "智能" appears everywhere).
    """
    def _tokens(s: str) -> set[str]:
        clean = re.sub(r"[一二三四五六七八九十、：（）()\s—\-:]+", " ", s)
        return {t.strip() for t in clean.split() if len(t.strip()) >= 2}

    def _trigrams(s: str) -> set[str]:
        # Strip punctuation/numerals first so "、智能工厂" → "智能工厂".
        clean = re.sub(r"[一二三四五六七八九十、：（）()\s—\-:,，。.]+", "", s)
        if len(clean) < 3:
            return set()
        return {clean[i : i + 3] for i in range(len(clean) - 2)}

    rec_tokens = _tokens(rec)
    ch_tokens = _tokens(chapter)
    # Direct token overlap
    if rec_tokens & ch_tokens:
        return True
    # Substring overlap (catch "Gemini 模型层" vs "模型层：Gemini 3.5 谱系")
    rec_blob = "".join(rec_tokens)
    ch_blob = "".join(ch_tokens)
    if rec_blob and ch_blob:
        for token in rec_tokens:
            if len(token) >= 2 and token in ch_blob:
                return True
        for token in ch_tokens:
            if len(token) >= 2 and token in rec_blob:
                return True
    # v0.3.4 P1: 3-gram fallback for Chinese compound tokens
    rec_grams = _trigrams(rec)
    ch_grams = _trigrams(chapter)
    if len(rec_grams & ch_grams) >= 2:
        return True
    return False


def _format_buckets_for_prompt(
    buckets: list[tuple[str, list]]
) -> str:
    """Render bucketed frames as a section-by-section authoritative list."""
    lines: list[str] = []
    for chapter, frames in buckets:
        if not frames:
            lines.append(f"### {chapter}")
            lines.append("（本章无候选帧 — 不要在本章插入任何图。如内容需要，提请用户后续补图）")
            lines.append("")
            continue
        lines.append(f"### {chapter}  （{len(frames)} 张候选，本章只能用这里的图）")
        for i, f in enumerate(frames, 1):
            # v0.3.1 D2: prefer alt_short for the alt text in the suggested
            # markdown reference (LLM frequently copy-pastes this template
            # verbatim, so we want short readable alt). Fall back to first 60
            # chars of caption for legacy frames where alt_short is empty.
            alt = (getattr(f, "alt_short", "") or f.caption)[:60]
            lines.append(
                f"  [{i}] `{f.filename}`  ({format_duration(f.timestamp_s)})\n"
                f"      引用: ![{alt}](frames/{f.filename})\n"
                f"      alt_short: {getattr(f, 'alt_short', '') or '(空，使用 caption 截断)'}\n"
                f"      caption: {f.caption}"
            )
        lines.append("")
    return "\n".join(lines)


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
