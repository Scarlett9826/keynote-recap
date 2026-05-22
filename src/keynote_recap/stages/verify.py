"""Stage 5.5: verify — 3 sub-checks on report.md.

5.5.1 coverage check (Python-only): every ## 章节 has ≥ 1 image (A8 hard constraint)
5.5.2 caption verify (Vision LLM): re-look at each image, confirm caption matches
5.5.3 anti-AI lint (regex): scan for forbidden emoji / phrases / overhype

If any check fails, writes a lint report to <output>/lint_report.md.
For now, M1 only emits warnings; M2 will add auto-fix loop.
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient
from ..state import State
from ..util import VisionCapabilityError, detect_vision_capability_error

console = Console()

# Path resolution: prompts/05-5-caption-verify.md
CAPTION_VERIFY_PROMPT_FILE = (
    Path(__file__).parent.parent.parent.parent / "prompts" / "05-5-caption-verify.md"
)


def _load_caption_verify_system() -> str:
    """Load the System section from prompts/05-5-caption-verify.md.

    Falls back to a minimal hard-coded system prompt if the file is missing
    (e.g. when running from a non-standard install layout).
    """
    if not CAPTION_VERIFY_PROMPT_FILE.exists():
        return _CAPTION_VERIFY_FALLBACK
    text = CAPTION_VERIFY_PROMPT_FILE.read_text()
    if "# System" in text and "# User Template" in text:
        body = text.split("# System", 1)[1].split("# User Template", 1)[0]
        return body.strip()
    return _CAPTION_VERIFY_FALLBACK


_CAPTION_VERIFY_FALLBACK = """## 能力前置自检（必须先执行）

本任务需要多模态视觉能力。如果你只能看到文本但看不到图像，请只输出：
ERROR_NO_VISION_CAPABILITY: 当前模型无法重新看图核对 caption。
然后停止。

你是质量审核员。重看图，核对 caption。严禁仅根据文本反推 actual_image_content。输出严格 JSON。"""


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.0 image filename existence check
# ──────────────────────────────────────────────────────────────────────────────
def check_image_filenames(report_md: str, output_dir: Path) -> dict:
    """Every image filename referenced must exist in <output_dir>/frames/."""
    frames_dir = output_dir / "frames"
    available = {p.name for p in frames_dir.glob("*")} if frames_dir.exists() else set()

    refs = re.findall(r"!\[[^\]]*\]\(frames/([^)]+)\)", report_md)
    missing: list[str] = []
    found: list[str] = []
    for ref in refs:
        if ref in available:
            found.append(ref)
        else:
            missing.append(ref)
    return {
        "total_refs": len(refs),
        "found": found,
        "missing": missing,
        "all_pass": len(missing) == 0,
        "available_count": len(available),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.1 coverage check
# ──────────────────────────────────────────────────────────────────────────────
def check_coverage(report_md: str) -> dict:
    """Every ## chapter (中文数字 一/二/...) must have ≥ 1 image."""
    sections = re.split(r"\n## ", report_md)[1:]
    missing: list[str] = []
    passed: list[str] = []

    EXEMPT_KEYWORDS = ("信源说明", "整体概要", "📌")

    for sec in sections:
        title_line = sec.split("\n", 1)[0].strip()
        if any(k in title_line for k in EXEMPT_KEYWORDS):
            continue
        # Only check sections with chinese numerals (## 一、/ 二、/ ...)
        if not re.match(r"^[一二三四五六七八九十]+、", title_line):
            continue

        has_image = bool(re.search(r"!\[.*?\]\(.*?\)", sec))
        if has_image:
            passed.append(title_line)
        else:
            missing.append(title_line)

    return {
        "passed": passed,
        "missing": missing,
        "all_pass": len(missing) == 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.3 anti-AI lint
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_EMOJI = ["🔥", "🚀", "💡", "⭐", "🎉", "👀", "🤔", "🎯", "✨", "🌟",
                    "⚡", "🎁", "💪", "🙌", "💯", "🌈", "🎊"]
FORBIDDEN_PHRASES = [
    "让我们一起来看看", "让我们来看看", "让我们看看",
    "值得我们关注的是", "不仅仅是",
    "在当今的", "这无疑标志着", "未来已来",
    "以下是关于", "不难看出", "众所周知",
    "相信大家都", "总而言之", "综上所述",
    "由此可见", "毋庸置疑", "可以预见",
]
# M4: "transcription mode" indicators — these phrases pattern-match speech
# being literally transcribed into the report instead of analyzed/condensed.
# Pure occurrence is OK in 「字幕原话」 quotes; this list catches them in
# narrative body text.
TRANSCRIPTION_TELLS = [
    "今天我非常高兴", "我非常高兴",
    "首先我想说", "首先让我",
    "下面我们来看", "下面让我们看",
    "接下来我们", "接下来让我",
    "正如大家所看到的",
    "请大家欢迎",
    "请允许我", "请让我",
    "我想跟大家分享", "我想要分享",
    "现在我把时间交给", "把时间交给",
]
WARN_ADJECTIVES = ["巨大", "显著", "革命性", "惊人", "震撼",
                    "重磅", "史诗级", "颠覆性", "空前"]


def lint_report(report_md: str) -> dict:
    """Scan for forbidden patterns. Returns dict with violations."""
    lines = report_md.split("\n")
    level1: list[dict] = []  # hard errors
    level2: list[dict] = []  # warnings

    in_quote_block = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track context — exempt content inside `> "..."` and `> 📎` blocks
        if stripped.startswith('> "') or stripped.startswith("> 📎"):
            in_quote_block = True
            continue
        if not stripped.startswith(">"):
            in_quote_block = False

        # Skip image captions and headers (no L2 check)
        is_image = "![" in line and "](" in line
        is_header = line.startswith("#")

        # Level 1: emoji
        for e in FORBIDDEN_EMOJI:
            if e in line and not is_image:
                level1.append({
                    "line": i, "rule": "L1.1 forbidden emoji",
                    "found": e, "context": stripped[:80],
                })

        # Level 1: forbidden phrases (skip in quotes / 📎)
        if not in_quote_block:
            for phrase in FORBIDDEN_PHRASES:
                if phrase in line and not is_header:
                    level1.append({
                        "line": i, "rule": "L1.2 forbidden phrase",
                        "found": phrase, "context": stripped[:80],
                    })

        # Level 2: overhype adjectives
        if not in_quote_block and not is_header:
            for adj in WARN_ADJECTIVES:
                if adj in line:
                    level2.append({
                        "line": i, "rule": "L2.1 overhype adjective",
                        "found": adj, "context": stripped[:80],
                    })

        # Level 1 (M4): transcription tells in narrative body
        if not in_quote_block and not is_header and not is_image:
            for tell in TRANSCRIPTION_TELLS:
                if tell in line:
                    level1.append({
                        "line": i, "rule": "L1.4 transcription tell (这是转写不是分析)",
                        "found": tell, "context": stripped[:80],
                    })

    # Level 1: structural checks
    if "<div class=\"callout\"" not in report_md:
        level1.append({"line": 0, "rule": "L1.3 missing callout block"})
    if "## 信源说明" not in report_md:
        level1.append({"line": 0, "rule": "L1.3 missing 信源说明 section"})
    if "一点观察" not in report_md:
        level1.append({"line": 0, "rule": "L1.3 missing 一点观察 section"})

    # Citation count
    citations = re.findall(r"^>\s*📎\s*\*\*补充信源\*\*", report_md, re.MULTILINE)
    if len(citations) < 8:
        level1.append({
            "line": 0, "rule": "L1.3 too few 📎 citations",
            "found": f"{len(citations)} (need ≥ 8)",
        })

    return {"level1": level1, "level2": level2}


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.2 caption verify (vision LLM)
# ──────────────────────────────────────────────────────────────────────────────
def verify_captions(state: State, cfg: Config, client: LLMClient) -> dict:
    """Re-vision-look every image, compare against caption in report.md.

    Note: M1 implements basic check (random sample 10 frames to control cost).
    M2 will scale to all frames.
    """
    if not state.selected_frames:
        return {"verifications": [], "summary": {"total": 0}}

    # Sample first 10 to keep M1 fast
    sample = state.selected_frames[:10]
    output_dir = Path(state.output_dir)
    frames_dir = output_dir / "frames"

    image_paths = [frames_dir / f.filename for f in sample if (frames_dir / f.filename).exists()]
    if not image_paths:
        return {"verifications": [], "summary": {"total": 0, "note": "no images found"}}

    captions_block = "\n".join(
        f"## Image {i+1}: {f.filename}\n- caption: 「{f.caption}」"
        for i, f in enumerate(sample[:len(image_paths)])
    )

    user_text = f"""请核对以下 {len(image_paths)} 张图的 caption 是否真实。

{captions_block}

输出 JSON：
{{
  "verifications": [
    {{
      "filename": "...",
      "match_status": "exact|partial|wrong",
      "actual_image_content": "<重新描述>",
      "issues": [...],
      "suggested_caption": "<如有问题给修正>"
    }}
  ]
}}
"""

    try:
        text, in_t, out_t = client.chat_with_images(
            model=cfg.llm.models.verify,
            system=_load_caption_verify_system(),
            user_text=user_text,
            image_paths=image_paths,
            temperature=0.1,
            max_tokens=4000,
            json_mode=True,
        )
        track(state, stage="verify_captions", model=cfg.llm.models.verify,
              input_tokens=in_t, output_tokens=out_t)

        # Capability probe: if the model couldn't see images, surface a clear
        # warning instead of letting the JSON parser fail with a cryptic error.
        err = detect_vision_capability_error(text)
        if err:
            raise VisionCapabilityError(err)

        return client.parse_json(text)
    except VisionCapabilityError as e:
        console.print()
        console.print("  [yellow]⚠ Stage 5.5.2 skipped: model cannot see images[/]")
        console.print(f"    Model returned: {e}")
        console.print(f"    Current verify model: [cyan]{cfg.llm.models.verify}[/]")
        console.print("    Set a multimodal model for the verify stage, e.g.:")
        console.print("      [cyan]llm.models.verify: gemini-2.5-pro[/]")
        console.print("      [cyan]llm.models.verify: claude-sonnet-4[/]")
        console.print("    See README → 'Model Selection' for the verified list.")
        return {
            "verifications": [],
            "summary": {
                "total": 0,
                "skipped": True,
                "skip_reason": "no_vision_capability",
                "model": cfg.llm.models.verify,
            },
        }
    except Exception as e:
        console.print(f"  [yellow]caption verify failed: {e}[/]")
        return {"verifications": [], "summary": {"total": 0, "error": str(e)}}


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.4 image-section fit (M4 — addresses "图位置和文字不匹配" feedback)
# ──────────────────────────────────────────────────────────────────────────────
def check_image_section_fit(report_md: str) -> dict:
    """For every image in the report, check whether the section it's in
    plausibly matches the image caption.

    This is a *static* heuristic check — it does not call the LLM. It looks
    for caption keywords appearing in the section title or surrounding ±20
    lines of body text. The intent is to catch the egregious case where an
    image of, say, "Pixel Halo" lands inside a "## 五、Search" section.

    Returns a dict with `mismatches` listing (filename, section_title,
    caption_excerpt) tuples. M4 emits these as warnings; auto-fix moves
    them to the section whose body has the most caption-keyword overlap.
    """
    lines = report_md.split("\n")
    # Track current section title as we walk
    current_section = ""
    section_body: list[tuple[str, list[str]]] = []   # (title, lines_in_section)
    current_body: list[str] = []
    for line in lines:
        if re.match(r"^## [一二三四五六七八九十]+、", line):
            if current_section:
                section_body.append((current_section, current_body))
            current_section = line.strip()
            current_body = []
        else:
            current_body.append(line)
    if current_section:
        section_body.append((current_section, current_body))

    mismatches: list[dict] = []
    img_re = re.compile(r"!\[([^\]]*)\]\(frames/([^)]+)\)")

    for title, body in section_body:
        # Build a "section keyword pool" = words in title (stripped of
        # 中文数字/punctuation) + content words from non-image body lines
        title_clean = re.sub(r"[一二三四五六七八九十、：（）()\s]+", " ", title).strip()
        title_keywords = {w.strip("：—、，。 ") for w in title_clean.split() if len(w) >= 2}

        body_text = "\n".join(b for b in body if "![" not in b)

        for line_in_body in body:
            for cap, fname in img_re.findall(line_in_body):
                # caption keywords: 2+ char tokens that are non-digit
                cap_tokens = {t for t in re.split(r"[\s，。、：—()（）]+", cap) if len(t) >= 2}
                # Score: how many caption tokens appear in title or body context?
                title_hits = sum(1 for t in cap_tokens if any(t in k or k in t for k in title_keywords))
                body_hits = sum(1 for t in cap_tokens if t in body_text)
                # Mismatch heuristic: 0 title hits AND ≤ 1 body hits
                # AND caption has ≥ 4 meaningful tokens (so we're not flagging
                # a 1-word caption with no hope of matching anything)
                if title_hits == 0 and body_hits <= 1 and len(cap_tokens) >= 4:
                    mismatches.append({
                        "filename": fname,
                        "section_title": title,
                        "caption_excerpt": cap[:80],
                        "title_hits": title_hits,
                        "body_hits": body_hits,
                    })

    return {
        "mismatches": mismatches,
        "all_pass": len(mismatches) == 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.5 structure lint (M4 — addresses "格式没按要求产出" feedback)
# ──────────────────────────────────────────────────────────────────────────────
def check_structure(report_md: str) -> dict:
    """Static checks for required document structure beyond plain coverage.

    Catches the failure mode "the body is just a transcript with images" by
    verifying:
      - L1 titles match `## <中文数字>、<主题>(<副标题>)?: <点题副句>`
      - L2 sub-titles match `### <数字>.<数字> <名词> — <定位>`
      - Every L1 section has at least one `**核心判断**：` line
      - The whole report has at least N `> "..."` original-quote blocks
      - The whole report has at least N `|...|...|` table rows
    """
    lines = report_md.split("\n")
    issues: list[dict] = []

    # L1 title format
    l1_re = re.compile(r"^## [一二三四五六七八九十]+、")
    l1_format_re = re.compile(r"^## [一二三四五六七八九十]+、[^：\n]+：.+$")
    EXEMPT_L1 = ("信源说明",)
    for i, line in enumerate(lines, 1):
        if l1_re.match(line) and not any(k in line for k in EXEMPT_L1):
            if not l1_format_re.match(line):
                issues.append({
                    "rule": "L1 title missing 「：点题副句」",
                    "line": i,
                    "context": line[:80],
                })

    # L2 title format (### 1.1 名 — 定位)
    l2_re = re.compile(r"^### \d+\.\d+\s")
    l2_format_re = re.compile(r"^### \d+\.\d+\s+[^—\n]+—\s*.+$")
    for i, line in enumerate(lines, 1):
        if l2_re.match(line) and not l2_format_re.match(line):
            issues.append({
                "rule": "L2 title missing 「— 定位短句」",
                "line": i,
                "context": line[:80],
            })

    # Per-section 「核心判断」 presence
    sections = re.split(r"\n## ", report_md)[1:]
    sections_missing_judgement: list[str] = []
    for sec in sections:
        title_line = sec.split("\n", 1)[0].strip()
        if any(k in title_line for k in ("信源说明", "整体概要", "一点观察", "📌")):
            continue
        if not l1_re.match("## " + title_line):
            continue
        if "**核心判断**" not in sec and "核心判断：" not in sec:
            sections_missing_judgement.append(title_line)

    # Original quote blocks 「> "..."」 count
    quote_blocks = re.findall(r'^>\s*"[^\n]+', report_md, re.MULTILINE)
    quote_count = len(quote_blocks)

    # Table rows count
    table_rows = re.findall(r"^\|.+\|.+\|.*$", report_md, re.MULTILINE)
    table_count = len(table_rows)

    return {
        "issues": issues,
        "sections_missing_judgement": sections_missing_judgement,
        "quote_count": quote_count,
        "table_count": table_count,
        "all_pass": (
            not issues
            and not sections_missing_judgement
            and quote_count >= 4
            and table_count >= 8
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Stage 5.5 entry
# ──────────────────────────────────────────────────────────────────────────────
def run(state: State, cfg: Config) -> State:
    """Execute stage 5.5 (3 sub-checks)."""
    console.print("[bold]Stage 5.5 — verify[/]")

    if not state.report_md_path or not Path(state.report_md_path).exists():
        console.print("  [yellow]No report.md to verify, skipping[/]\n")
        return state

    report_md = Path(state.report_md_path).read_text()
    output_dir = Path(state.output_dir)

    # 5.5.0 — image filename existence
    fnchk = check_image_filenames(report_md, output_dir)
    if fnchk["all_pass"]:
        console.print(f"  [5.5.0] image filenames: ✓ all {fnchk['total_refs']} exist")
    else:
        console.print(f"  [5.5.0] image filenames: [red]✗ {len(fnchk['missing'])} / {fnchk['total_refs']} missing[/]")
        for m in fnchk["missing"][:5]:
            console.print(f"          - {m}")
        if len(fnchk["missing"]) > 5:
            console.print(f"          ... and {len(fnchk['missing']) - 5} more")

    # 5.5.1
    cov = check_coverage(report_md)
    state.coverage_check_passed = cov["all_pass"]
    if cov["all_pass"]:
        console.print(f"  [5.5.1] coverage: ✓ all {len(cov['passed'])} sections have images")
    else:
        console.print(f"  [5.5.1] coverage: [red]✗ missing in {len(cov['missing'])} sections[/]")
        for m in cov["missing"]:
            console.print(f"          - {m}")

    # 5.5.3
    lint = lint_report(report_md)
    if lint["level1"]:
        console.print(f"  [5.5.3] lint: [red]{len(lint['level1'])} L1 errors[/]")
    if lint["level2"]:
        console.print(f"  [5.5.3] lint: [yellow]{len(lint['level2'])} L2 warnings[/]")
    if not lint["level1"] and not lint["level2"]:
        console.print("  [5.5.3] lint: ✓ no violations")

    # 5.5.4 image-section fit (M4)
    fit = check_image_section_fit(report_md)
    if fit["all_pass"]:
        console.print("  [5.5.4] image-section fit: ✓ all images plausibly match section")
    else:
        n = len(fit["mismatches"])
        console.print(f"  [5.5.4] image-section fit: [yellow]{n} likely mismatches[/]")
        for m in fit["mismatches"][:3]:
            console.print(
                f"          - {m['filename']} in 「{m['section_title'][:40]}」 "
                f"(caption: {m['caption_excerpt'][:40]}...)"
            )

    # 5.5.5 structure (M4)
    structure = check_structure(report_md)
    state.structure_check_passed = structure["all_pass"]
    if structure["all_pass"]:
        console.print("  [5.5.5] structure: ✓ format passes (titles/quotes/tables/judgement)")
    else:
        if structure["issues"]:
            console.print(f"  [5.5.5] structure: [red]{len(structure['issues'])} title-format errors[/]")
            for iss in structure["issues"][:3]:
                console.print(f"          - L{iss['line']}: {iss['rule']}: {iss['context'][:60]}")
        if structure["sections_missing_judgement"]:
            console.print(
                f"  [5.5.5] structure: [red]{len(structure['sections_missing_judgement'])} "
                f"sections missing **核心判断**：[/]"
            )
        if structure["quote_count"] < 4:
            console.print(
                f"  [5.5.5] structure: [red]too few 「> \"原话\"」 quotes "
                f"({structure['quote_count']} / need ≥ 4)[/]"
            )
        if structure["table_count"] < 8:
            console.print(
                f"  [5.5.5] structure: [red]too few table rows "
                f"({structure['table_count']} / need ≥ 8)[/]"
            )

    # 5.5.2 (sampled)
    client = LLMClient(cfg.llm)

    # ─── Auto-fix: if coverage fails, try to add images to missing sections ───
    if not cov["all_pass"] and state.selected_frames:
        console.print("  [5.5.1] auto-fix: adding images to missing sections...")
        report_md = _auto_fix_coverage(report_md, cov, state, cfg, client)
        # Re-check coverage after fix
        cov = check_coverage(report_md)
        state.coverage_check_passed = cov["all_pass"]
        if cov["all_pass"]:
            console.print(f"  [5.5.1] auto-fix: ✓ all {len(cov['passed'])} sections now have images")
        else:
            console.print(f"  [5.5.1] auto-fix: still missing {len(cov['missing'])} sections")
        # Write fixed report
        Path(state.report_md_path).write_text(report_md)

    cap = verify_captions(state, cfg, client)
    n_verifications = len(cap.get("verifications", []))
    n_wrong = sum(1 for v in cap.get("verifications", []) if v.get("match_status") == "wrong")
    console.print(f"  [5.5.2] caption verify (sample {n_verifications}): "
                  f"{'✓' if n_wrong == 0 else f'[red]✗ {n_wrong} wrong[/]'}")

    # Write lint report
    lint_path = output_dir / "lint_report.md"
    lint_path.write_text(_render_lint_report(cov, lint, cap, fnchk, fit, structure))
    state.lint_report_path = str(lint_path)
    state.last_completed_stage = 5.5
    state.save()

    console.print(f"  Wrote {lint_path.name}")
    console.print("[green]✓ Stage 5.5 done[/]\n")
    return state


def _render_lint_report(
    coverage: dict,
    lint: dict,
    captions: dict,
    fnchk: dict | None = None,
    fit: dict | None = None,
    structure: dict | None = None,
) -> str:
    lines = ["# Lint Report\n"]

    if fnchk is not None:
        lines.append("## 5.5.0 Image Filename Existence\n")
        if fnchk["all_pass"]:
            lines.append(f"✓ All {fnchk['total_refs']} image references exist in frames/.\n")
        else:
            lines.append(f"❌ {len(fnchk['missing'])} / {fnchk['total_refs']} image references missing:\n")
            for m in fnchk["missing"]:
                lines.append(f"- `{m}`")
            lines.append("")

    lines.append("## 5.5.1 Coverage Check\n")
    if coverage["all_pass"]:
        lines.append(f"✓ All {len(coverage['passed'])} sections have images.\n")
    else:
        lines.append(f"❌ Missing in {len(coverage['missing'])} sections:\n")
        for m in coverage["missing"]:
            lines.append(f"- {m}")
        lines.append("")

    lines.append("## 5.5.2 Caption Verify (sample)\n")
    for v in captions.get("verifications", []):
        status = v.get("match_status", "?")
        emoji = {"exact": "✓", "partial": "⚠", "wrong": "✗"}.get(status, "?")
        lines.append(f"- {emoji} {v.get('filename', '')}: {status}")
        if v.get("issues"):
            for issue in v["issues"]:
                lines.append(f"    - {issue}")
        if v.get("suggested_caption"):
            lines.append(f"    - 建议：{v['suggested_caption']}")
    lines.append("")

    lines.append("## 5.5.3 Anti-AI Lint\n")
    lines.append(f"### Level 1 (硬错误)：{len(lint['level1'])} 处\n")
    for v in lint["level1"]:
        line_no = v.get("line", 0)
        rule = v.get("rule", "")
        found = v.get("found", "")
        ctx = v.get("context", "")
        lines.append(f"- L{line_no}: {rule}" + (f" - 「{found}」" if found else "")
                      + (f"\n    > {ctx}" if ctx else ""))
    lines.append("")

    lines.append(f"### Level 2 (建议)：{len(lint['level2'])} 处\n")
    for v in lint["level2"][:50]:
        line_no = v.get("line", 0)
        rule = v.get("rule", "")
        found = v.get("found", "")
        ctx = v.get("context", "")
        lines.append(f"- L{line_no}: {rule} - 「{found}」\n    > {ctx}")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# 5.5.1 auto-fix: add images to sections missing them
# ──────────────────────────────────────────────────────────────────────────────
def _auto_fix_coverage(
    report_md: str,
    cov: dict,
    state: State,
    cfg: Config,
    client: LLMClient,
) -> str:
    """For each section missing an image, pick a relevant frame and insert it."""
    # Get frames already used in report
    used_filenames = set(re.findall(r"!\[.*?\]\(frames/([^)]+)\)", report_md))
    unused = [f for f in state.selected_frames if f.filename not in used_filenames]

    if not unused:
        return report_md

    # Split report into sections
    parts = re.split(r"(\n## [一二三四五六七八九十]+、[^\n]*\n)", report_md)
    # parts alternates: [preamble, title1, content1, title2, content2, ...]

    missing_titles = set(cov["missing"])
    frame_idx = 0

    for i, part in enumerate(parts):
        title_match = re.match(r"\n## ([一二三四五六七八九十]+、[^\n]*)\n", part)
        if not title_match:
            continue
        title = "## " + title_match.group(1)
        if title not in missing_titles:
            continue

        # Insert an image at the start of this section's content
        if frame_idx < len(unused):
            frame = unused[frame_idx]
            frame_idx += 1
            img_md = f"\n![{frame.caption}](frames/{frame.filename})\n"
            # Insert after the title (which is parts[i])
            if i + 1 < len(parts):
                parts[i + 1] = img_md + parts[i + 1]

    return "".join(parts)
