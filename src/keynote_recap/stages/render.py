"""Stage 6: render markdown → self-contained HTML.

Reuses video-recap/md_to_html.py logic with slight tweaks:
- markdown.extras includes "tables" (used heavily in keynote-recap)
- Embed all local images as base64 data URIs
- Single self-contained file (Feishu-friendly)
"""
from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

import markdown
from rich.console import Console

from ..config import Config
from ..state import State
from ..util import format_size

console = Console()


CSS = """
<style>
:root {
    --fg: #1f2328;
    --fg-muted: #656d76;
    --bg: #ffffff;
    --bg-soft: #f6f8fa;
    --border: #d0d7de;
    --accent: #0969da;
    --quote-bg: #f6f8fa;
    --quote-border: #d0d7de;
    --table-stripe: #f6f8fa;
}
@media (prefers-color-scheme: dark) {
    :root {
        --fg: #e6edf3;
        --fg-muted: #8b949e;
        --bg: #0d1117;
        --bg-soft: #161b22;
        --border: #30363d;
        --accent: #58a6ff;
        --quote-bg: #161b22;
        --quote-border: #30363d;
        --table-stripe: #161b22;
    }
}
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                 Helvetica, Arial, sans-serif;
    line-height: 1.7;
    color: var(--fg);
    background: var(--bg);
    max-width: 880px;
    margin: 0 auto;
    padding: 32px 40px 80px;
    font-size: 16px;
}
h1 { font-size: 32px; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-top: 0; }
h2 {
    font-size: 22px;
    margin-top: 48px;
    padding-top: 16px;
    border-top: 1px dashed var(--border);
    color: var(--accent);
}
h2:first-of-type { border-top: 0; padding-top: 0; }
h3 { font-size: 18px; margin-top: 32px; }
img {
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border);
    margin: 14px 0;
    display: block;
}
blockquote {
    background: var(--quote-bg);
    border-left: 4px solid var(--quote-border);
    margin: 12px 0;
    padding: 10px 16px;
    color: var(--fg-muted);
    border-radius: 0 6px 6px 0;
    font-size: 14px;
    line-height: 1.55;
}
blockquote > p { margin: 0; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code {
    background: var(--bg-soft);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, monospace;
}
pre code { padding: 12px; display: block; overflow-x: auto; }
hr { border: 0; border-top: 1px solid var(--border); margin: 32px 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 14px;
}
th, td {
    border: 1px solid var(--border);
    padding: 8px 12px;
    text-align: left;
}
th { background: var(--bg-soft); font-weight: 600; }
tr:nth-child(even) { background: var(--table-stripe); }
.callout {
    background: linear-gradient(135deg, rgba(9,105,218,0.06), rgba(88,166,255,0.04));
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 8px 28px 24px;
    margin: 24px 0 36px;
}
.callout > h2:first-child {
    margin-top: 16px;
    border-top: none;
    padding-top: 0;
}
.callout ul { padding-left: 24px; }
.callout li { margin: 4px 0; }
.callout li > ul { margin-top: 4px; margin-bottom: 4px; }
@media (prefers-color-scheme: dark) {
    .callout {
        background: linear-gradient(135deg, rgba(88,166,255,0.10), rgba(88,166,255,0.04));
    }
}
.quality-banner {
    border-radius: 6px;
    padding: 16px 20px;
    margin: 0 0 28px;
    border-style: solid;
    border-width: 2px;
    border-left-width: 6px;
}
.quality-banner strong { font-size: 16px; display: block; margin-bottom: 4px; }
.quality-banner p { margin: 8px 0; }
.quality-banner ul { margin: 8px 0 8px 22px; }
.quality-banner li { margin: 2px 0; line-height: 1.5; }
.quality-banner-tip { font-size: 13px; opacity: 0.85; }
.quality-banner-red {
    background: #fff0f0; border-color: #cf222e; color: #5b0c14;
}
.quality-banner-yellow {
    background: #fff8e6; border-color: #d99100; color: #5c4500;
}
@media (prefers-color-scheme: dark) {
    .quality-banner-red {
        background: rgba(207, 34, 46, 0.10); color: #ff9aa2;
    }
    .quality-banner-yellow {
        background: rgba(217, 145, 0, 0.10); color: #e8c474;
    }
}
.responsibility {
    margin: 48px 0 24px;
    padding: 20px 24px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--table-stripe);
    font-size: 14px;
}
.responsibility h3 { margin-top: 0; padding-top: 0; border-top: none; font-size: 15px; }
.responsibility h4 { margin: 14px 0 6px; font-size: 14px; font-weight: 600; }
.responsibility ul { margin: 4px 0 4px 22px; padding-left: 0; }
.responsibility li { margin: 2px 0; line-height: 1.5; }
.responsibility table { font-size: 13px; }
.responsibility code { font-size: 12px; }

/* v0.2.5 (L2): top sticky banner — primary forensic visual signature.
   Sticky to top; non-removable; aggressive project-orange to maximize
   visual delta vs. hand-crafted impostor HTML. Color modulates by run
   integrity (orange / yellow / red) reading from frontmatter
   stages-skipped list. */
.recap-banner {
    position: sticky;
    top: 0;
    z-index: 9999;
    margin: 0 -40px 24px;  /* counter body padding to span full width */
    padding: 0;
    border-top: 6px solid #ff6900;
    background: #fff7ed;
    color: #7c2d12;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 14px;
    line-height: 1.4;
}
.recap-banner-body {
    padding: 12px 40px;
    text-align: center;
}
.recap-banner-half-run {
    border-top-color: #d99100;
    background: #fff8e6;
    color: #5c4500;
}
.recap-banner-unverified {
    border-top-color: #cf222e;
    background: #fff0f0;
    color: #5b0c14;
}
@media print {
    .recap-banner { position: static; }
}

/* v0.2.4 (M9.7): provenance stamp — verifiable visual signature.
   Position fixed bottom-right so downstream readers can identify a
   keynote-recap-produced HTML at a glance. Subtle, non-distracting. */
.recap-stamp {
    position: fixed;
    bottom: 8px;
    right: 12px;
    font-size: 10px;
    color: var(--fg-muted);
    background: var(--bg);
    padding: 3px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    opacity: 0.6;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    pointer-events: none;
    z-index: 1000;
}
@media print {
    .recap-stamp { position: static; opacity: 1; margin-top: 24px; }
}
</style>
"""


def run(state: State, cfg: Config) -> State:
    """Execute stage 6."""
    if not state.report_md_path or not Path(state.report_md_path).exists():
        console.print("[yellow]Stage 6 — no report.md, skipping[/]\n")
        return state

    console.print("[bold]Stage 6 — render HTML[/]")

    md_path = Path(state.report_md_path)
    html_path = md_path.with_suffix(".html")

    title = state.video.title if state.video else md_path.stem
    banner_html = _build_banner(state)
    responsibility_html = _build_responsibility_section(state) if banner_html else ""

    _write_html(
        md_path=md_path,
        html_path=html_path,
        title=title,
        banner_html=banner_html,
        responsibility_html=responsibility_html,
    )

    state.report_html_path = str(html_path)
    state.last_completed_stage = 6.0
    state.save()

    size_str = format_size(html_path.stat().st_size)
    console.print(f"  Wrote {html_path.name} ({size_str})")
    console.print("[green]✓ Stage 6 done[/]\n")
    return state


def render_report_md_to_html(
    md_path: Path,
    html_path: Path,
    frontmatter_meta: dict,
) -> None:
    """v0.2.4 (M9.6): re-render an already-signed report.md to HTML.

    Used by ``keynote-recap publish-html``. Caller has already verified
    the sha matches; we just render. We don't have access to the State
    here (this can run on a fresh machine with only report.md), so we
    skip the banner / responsibility section — those are run-time
    concepts. The integrity callout in the body covers the same ground
    visually.

    The HTML stamp (M9.7) embeds version + sha so downstream can verify
    provenance even without re-running this command.
    """
    title = md_path.stem
    _write_html(
        md_path=md_path,
        html_path=html_path,
        title=title,
        banner_html="",
        responsibility_html="",
        frontmatter_meta=frontmatter_meta,
    )


def _write_html(
    md_path: Path,
    html_path: Path,
    title: str,
    banner_html: str,
    responsibility_html: str,
    frontmatter_meta: dict | None = None,
) -> None:
    """Shared HTML rendering core for both stage 6 and publish-html."""
    from ..frontmatter import parse_frontmatter

    md_text = md_path.read_text()
    base_dir = md_path.parent

    # v0.2.4: strip YAML frontmatter before rendering — it would otherwise
    # show up as "—" + raw key:value lines at the top of the HTML.
    meta, body = parse_frontmatter(md_text)
    if frontmatter_meta is None:
        frontmatter_meta = meta

    # 1. embed images as base64
    body = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: _embed_image(m, base_dir),
        body,
    )

    # 2. render markdown
    html_body = markdown.markdown(
        body,
        extensions=["extra", "sane_lists", "tables", "md_in_html"],
    )

    # 3. v0.2.4 (M9.7): provenance stamp
    version = frontmatter_meta.get("keynote-recap-version", "?")
    full_sha = frontmatter_meta.get("content-sha256", "")
    sha_short = full_sha[:8] if full_sha else "unsigned"
    model = frontmatter_meta.get("model-extract", "?")
    stamp_meta = (
        f'<meta name="generator" content="keynote-recap {_escape(version)}">\n'
        f'<meta name="content-sha256" content="{_escape(full_sha)}">\n'
    )
    stamp_html = (
        f'<div class="recap-stamp">'
        f'v{_escape(version)} · sha:{_escape(sha_short)} · 模型:{_escape(model)}'
        f'</div>'
    )

    top_banner_html = _build_top_banner(frontmatter_meta)

    html_full = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{stamp_meta}<title>{_escape(title)}</title>
{CSS}
</head>
<body>
{top_banner_html}
{banner_html}{html_body}{responsibility_html}
{stamp_html}
</body>
</html>"""

    html_path.write_text(html_full)


def _escape(s: str) -> str:
    """Minimal HTML escape for banner text."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def _build_top_banner(frontmatter_meta: dict) -> str:
    """v0.2.5 (L2): inject sticky top banner — primary forensic visual signature.

    Reads from frontmatter:
      keynote-recap-version, content-sha256, model-extract,
      stages-completed, stages-skipped

    Color modulates by integrity:
      - orange (default) — healthy: no skipped stages
      - yellow           — half-run: some stages skipped but stage 5 ran
      - red              — unverified: stage 1 (transcript) or stage 4 (research) skipped

    Non-cooperative: no JavaScript, no close button. A removable banner
    is a forgeable banner.
    """
    version = frontmatter_meta.get("keynote-recap-version", "?")
    full_sha = frontmatter_meta.get("content-sha256", "")
    sha8 = full_sha[:8] if full_sha else "unsigned"
    model = frontmatter_meta.get("model-extract", "?")

    completed = frontmatter_meta.get("stages-completed") or []
    skipped = frontmatter_meta.get("stages-skipped") or []
    n_done = len(completed) if isinstance(completed, list) else 0

    # Tolerant membership check — frontmatter may parse stage numbers
    # as int, float, or str depending on emitter
    def _in_skipped(stage_num: int) -> bool:
        for v in skipped:
            try:
                if float(v) == float(stage_num):
                    return True
            except (TypeError, ValueError):
                if str(v) in (str(stage_num), str(float(stage_num))):
                    return True
        return False

    unverified = _in_skipped(1) or _in_skipped(4)
    half_run = bool(skipped) and not unverified

    if unverified:
        cls = "recap-banner recap-banner-unverified"
        suffix = "✗ unverified"
    elif half_run:
        cls = "recap-banner recap-banner-half-run"
        suffix = "⚠ partial"
    else:
        cls = "recap-banner"
        suffix = "verified ✓"

    text = (
        f"keynote-recap v{_escape(str(version))} · "
        f"sha:{_escape(str(sha8))} · "
        f"model:{_escape(str(model))} · "
        f"stages:{n_done}/6 · "
        f"{suffix}"
    )
    return (
        f'<div class="{cls}">'
        f'<div class="recap-banner-body">{text}</div>'
        f'</div>'
    )


def _embed_image(match: re.Match, base_dir: Path) -> str:
    """Replace local image refs with base64 data URI; leave http/data alone."""
    alt = match.group(1)
    src = match.group(2)
    if src.startswith(("http://", "https://", "data:")):
        return match.group(0)
    img_path = (base_dir / src).resolve()
    if not img_path.exists():
        return match.group(0)
    mime = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
    data = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"![{alt}](data:{mime};base64,{data})"


# ──────────────────────────────────────────────────────────────────────────────
# Tri-color quality banner + responsibility section (M7 / v0.2.2)
# ──────────────────────────────────────────────────────────────────────────────
def _build_banner(state: State) -> str:
    """Decide red / yellow / no banner based on state.

    Red    — project quality gate failed after retry. Project's responsibility.
    Yellow — env / model preflight or runtime probe surfaced concerns.
             NOT the project's quality issue; user-environment-driven.
    None   — healthy run; no banner.

    Red takes precedence over yellow when both apply.
    """
    # v0.3.1 C2: quality_passed defaults to False now. Three cases:
    #  (a) explicit pass:    quality_passed=True  → no red banner.
    #  (b) explicit fail:    quality_passed=False AND final_quality_warnings non-empty.
    #  (c) implicit fail:    quality_passed=False AND no warnings — verify never ran
    #      (early exit, --start-stage skipped 5.5, retry exception). Treat as red
    #      with a synthetic warning so the user sees that the gate was not enforced.
    explicit_pass = getattr(state, "quality_passed", False)
    final_warnings = list(getattr(state, "final_quality_warnings", []) or [])
    if not explicit_pass and not final_warnings:
        final_warnings = [
            "Quality gate did not run (verify stage skipped or aborted before "
            "reaching final assessment). Report content has NOT been validated; "
            "re-run `keynote-recap recap-and-verify` to enforce gates."
        ]
    quality_failed = (not explicit_pass) and bool(final_warnings)
    env_warnings = list(getattr(state, "preflight_env_warnings", []) or [])
    model_warnings = list(getattr(state, "preflight_model_warnings", []) or [])
    runtime_warnings = list(getattr(state, "runtime_warnings", []) or [])

    # v0.2.4 (M9.3): stage 4 skipped or zero verified facts → red banner.
    # This is "project methodology partially executed", not a user-env
    # warning, so it goes red not yellow.
    #
    # Trigger condition: stage 4 was either skipped (in stages_skipped) OR
    # ran but produced zero verified facts (research_notes_path set but
    # verified_facts empty — distinguishes "stage 4 ran, found nothing"
    # from "stage 4 hasn't run yet" e.g. unit tests on synthetic state).
    stages_skipped = list(getattr(state, "stages_skipped", []) or [])
    stages_completed = list(getattr(state, "stages_completed", []) or [])
    n_verified = len(getattr(state, "verified_facts", []) or [])
    transcript_skipped = (1.0 in stages_skipped)
    research_skipped = (
        (4.0 in stages_skipped)
        or (4.0 in stages_completed and n_verified == 0)
    )

    has_yellow = bool(env_warnings or model_warnings or runtime_warnings)

    if quality_failed:
        items = "".join(
            f"<li>{_escape(w)}</li>" for w in final_warnings
        )
        return f"""
<div class="quality-banner quality-banner-red">
  <strong>本报告未通过项目质量门</strong>
  <p>已自动重跑一次，仍存在以下未达标项目。属于<b>项目质量门捕获的问题</b>，请人工审阅后再发布：</p>
  <ul>{items}</ul>
  <p class="quality-banner-tip">
    建议：换一个更强的多模态模型（如 <code>gemini-2.5-pro</code> /
    <code>claude-opus-4</code>），或运行 <code>keynote-recap doctor</code>
    检查模型能力，再用 <code>--start-stage 5</code> 重跑 draft。
  </p>
</div>
"""

    # v0.2.4 (M9.3): stage 4 skipped / no verified facts → dedicated red banner.
    # Distinct from quality-gate failure: there, stage 4 ran and the report
    # failed quality. Here, stage 4 didn't run at all — the report contains
    # NO third-party-verified information.
    if research_skipped or transcript_skipped:
        reasons: list[str] = []
        if transcript_skipped:
            reasons.append("Stage 1（字幕）未完成 — 无 transcript，stage 4 事实查证无法启动")
        if research_skipped and not transcript_skipped:
            reasons.append(
                f"Stage 4（事实查证）未完成 — 验证事实数 {n_verified}"
            )
        items = "".join(f"<li>{_escape(r)}</li>" for r in reasons)
        return f"""
<div class="quality-banner quality-banner-red">
  <strong>本报告未经事实查证</strong>
  <p>所有“数据”均从演讲画面文字抠出，<b>未经第三方信源核对</b>，
     可能存在 OCR 错误、演讲者口误未修正、营销话术未挑明。请勿
     按"已查证"标准引用本报告。</p>
  <ul>{items}</ul>
  <p class="quality-banner-tip">
    修复：用 <code>--transcript-file</code> 提供字幕，或用
    <code>yt-dlp --cookies-from-browser chrome &lt;url&gt;
    --write-auto-sub --skip-download</code> 重新拉字幕，再
    <code>--start-stage 4</code> 跑事实查证。
  </p>
</div>
"""

    if has_yellow:
        sections: list[str] = []
        if env_warnings:
            items = "".join(f"<li>{_escape(w)}</li>" for w in env_warnings)
            sections.append(
                f"<p><b>环境告警</b>（来自跑前体检）：</p><ul>{items}</ul>"
            )
        if model_warnings:
            items = "".join(f"<li>{_escape(w)}</li>" for w in model_warnings)
            sections.append(
                f"<p><b>模型告警</b>（视觉 stage 使用了未验证模型）：</p><ul>{items}</ul>"
            )
        if runtime_warnings:
            items = "".join(f"<li>{_escape(w)}</li>" for w in runtime_warnings)
            sections.append(
                f"<p><b>跑中能力探针</b>（模型实际产出可疑）：</p><ul>{items}</ul>"
            )
        body = "".join(sections)
        return f"""
<div class="quality-banner quality-banner-yellow">
  <strong>本次运行存在环境 / 模型告警</strong>
  <p>项目质量门已通过，但<b>用户运行环境或所选模型不在项目验证范围内</b>，
     报告质量可能受限。详见末尾「模型与责任边界」section。</p>
  {body}
</div>
"""

    return ""


_TIER_LABEL_ZH: dict[str, str] = {
    "verified_multimodal": "已验证多模态",
    "known_text_only": "已知纯文本（不达标）",
    "unknown": "未验证",
}


def _build_responsibility_section(state: State) -> str:
    """Render the §模型与责任边界 section.

    Only emitted when there's a banner (red or yellow) — keeps healthy reports
    clean. Lays out:

      - which model was used at each stage and its capability tier
      - what the project takes responsibility for
      - what the project does NOT take responsibility for (model self-direction,
        environment limits, model hallucination beyond verified facts)
      - how to re-run with a stronger model
    """
    models_used: dict[str, str] = getattr(state, "models_used", {}) or {}
    model_tiers: dict[str, str] = getattr(state, "model_tiers", {}) or {}
    parallelism: dict[str, int] = getattr(state, "stage_parallelism", {}) or {}

    # Build per-stage model table (only stages that called an LLM).
    # v0.2.3: extra column for agent parallelism so users see what the
    # project decided based on their model's tier.
    stage_label = {
        "extract":  ("stage 3 extract", "图片筛选 / 视觉理解"),
        "research": ("stage 4 research", "事实查证"),
        "draft":    ("stage 5 draft", "正文撰写"),
        "verify":   ("stage 5.5 verify", "质量校验 / 视觉对照"),
    }
    rows: list[str] = []
    for key, (stage_name, role) in stage_label.items():
        model = models_used.get(key, "(未记录)")
        tier_raw = model_tiers.get(key, "unknown")
        tier_zh = _TIER_LABEL_ZH.get(tier_raw, tier_raw)
        # parallelism column — only "extract" is eligible in v0.2.3
        if key in parallelism:
            p = parallelism[key]
            par_cell = f"并发 {p}" if p > 1 else "顺序"
        else:
            par_cell = "—"
        rows.append(
            f"<tr><td><code>{_escape(stage_name)}</code></td>"
            f"<td>{_escape(role)}</td>"
            f"<td><code>{_escape(model)}</code></td>"
            f"<td>{_escape(tier_zh)}</td>"
            f"<td>{_escape(par_cell)}</td></tr>"
        )
    table_html = (
        "<table><thead><tr>"
        "<th>Stage</th><th>职责</th><th>本次实际模型</th>"
        "<th>能力等级</th><th>Agent 并发</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    return f"""
<section class="responsibility">
<h3>模型与责任边界</h3>

<h4>本次运行使用的模型</h4>
{table_html}

<h4>项目（keynote-recap）负责</h4>
<ul>
  <li>方法论：整体概要 callout / 时间-数据三段对比 / 「一点观察」+「未查到」</li>
  <li>章节结构：L1-L3 层级、bullet 缩进、图顶格</li>
  <li>图片筛选：信息量 / 相关性 / 去重三原则、useful ratio 硬门（v0.3.6）、桶约束配位</li>
  <li>禁词与文风：emoji / 渲染感 / 转录腔等 5.5.3 lint</li>
  <li>事实校验：5.5.2 真看图核对 caption、引用源 allowlist</li>
</ul>

<h4>项目<b>不</b>负责</h4>
<ul>
  <li><b>用户环境</b>：ffmpeg / yt-dlp / Python 版本、网络、磁盘空间、API key</li>
  <li><b>模型自由发挥</b>：模型在方法论之外自创的措辞、感叹语气、emoji 漏网</li>
  <li><b>模型 hallucination</b>：模型自行编造、且不在 5.5.2 视觉对照覆盖范围内的细节</li>
  <li><b>模型视觉精度上限</b>：未验证 / 弱视觉模型对 PPT 的识别误差</li>
  <li><b>视频源质量</b>：模糊画面、无字幕、变速字幕错位</li>
</ul>

<h4>如何用更强的模型重跑</h4>
<p>先运行 <code>keynote-recap doctor</code> 检查环境与模型；用 <code>--llm gemini-2.5-pro</code>
   或 <code>--llm-all claude-opus-4</code> 切换模型；用 <code>--start-stage 5</code>
   只重跑写作、保留已选好的图。</p>
</section>
"""
