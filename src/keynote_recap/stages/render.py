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

    html_full = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{CSS}
</head>
<body>
{html_body}
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
