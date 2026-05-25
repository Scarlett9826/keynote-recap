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

    md_text = md_path.read_text()
    base_dir = md_path.parent

    # 1. embed images as base64
    md_text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: _embed_image(m, base_dir),
        md_text,
    )

    # 2. render markdown
    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "tables", "md_in_html"],
    )

    title = state.video.title if state.video else md_path.stem

    # ─── Tri-color quality banner (M5 + M7) ───
    # Red    = project quality gate failed (after retries)
    # Yellow = environment / model capability concern (project ran fine but
    #          output quality may be limited by user's model / env choice)
    # No banner = healthy run
    banner_html = _build_banner(state)

    # ─── Responsibility section (M7) ───
    # Only when there's a banner: makes it explicit which deltas are
    # project-design vs. user-environment / model-self-direction.
    responsibility_html = _build_responsibility_section(state) if banner_html else ""

    html_full = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{CSS}
</head>
<body>
{banner_html}{html_body}{responsibility_html}
</body>
</html>"""

    html_path.write_text(html_full)
    state.report_html_path = str(html_path)
    state.last_completed_stage = 6.0
    state.save()

    size_str = format_size(html_path.stat().st_size)
    console.print(f"  Wrote {html_path.name} ({size_str})")
    console.print("[green]✓ Stage 6 done[/]\n")
    return state


def _escape(s: str) -> str:
    """Minimal HTML escape for banner text."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
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
    quality_failed = (
        not getattr(state, "quality_passed", True)
        and getattr(state, "final_quality_warnings", [])
    )
    env_warnings = list(getattr(state, "preflight_env_warnings", []) or [])
    model_warnings = list(getattr(state, "preflight_model_warnings", []) or [])
    runtime_warnings = list(getattr(state, "runtime_warnings", []) or [])
    has_yellow = bool(env_warnings or model_warnings or runtime_warnings)

    if quality_failed:
        items = "".join(
            f"<li>{_escape(w)}</li>" for w in state.final_quality_warnings
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
  <li>图片筛选：信息量 / 相关性 / 去重三原则、live ratio 硬门、桶约束配位</li>
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
