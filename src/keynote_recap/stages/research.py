"""Stage 4: research — extract facts from transcript + verify via web search.

Two LLM passes:
    4.1 extract-facts: scan transcript → list of facts to verify (JSON)
    4.2 summarize:     run web search per fact → produce research_notes.md

Outputs:
    state.facts_to_verify
    state.verified_facts
    state.research_notes_path  (markdown file in output dir)
    state.unknowns
    state.source_urls
"""
from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient
from ..search import get_search_provider, url_alive, webfetch
from ..state import FactToVerify, State, VerifiedFact
from ..util import format_duration

console = Console()

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def run(state: State, cfg: Config) -> State:
    """Execute stage 4 (4.1 + 4.2)."""
    if state.video is None or not state.video.transcript:
        console.print("[yellow]Stage 4 — no transcript, skipping research[/]\n")
        state.last_completed_stage = 4.0
        state.save()
        return state

    console.print("[bold]Stage 4 — research[/]")
    client = LLMClient(cfg.llm)

    # ─── 4.1 extract facts ───
    facts = _extract_facts(state, cfg, client)
    console.print(f"  [4.1] Extracted {len(facts)} facts to verify")

    # ─── 4.2 verify via web search ───
    verified, unknowns, urls = _verify_facts(state, cfg, client, facts)
    console.print(f"  [4.2] Verified {len(verified)} / {len(facts)}; "
                  f"{len(unknowns)} unknowns; {len(urls)} URLs collected")

    # ─── Write research_notes.md ───
    notes_path = Path(state.output_dir) / "research_notes.md"
    notes_path.write_text(_render_notes_md(state, verified, unknowns, urls))

    state.facts_to_verify = facts
    state.verified_facts = verified
    state.unknowns = unknowns
    state.source_urls = urls
    state.research_notes_path = str(notes_path)
    state.last_completed_stage = 4.0
    state.save()

    console.print(f"  Wrote {notes_path.relative_to(Path.cwd()) if notes_path.is_relative_to(Path.cwd()) else notes_path}")
    console.print("[green]✓ Stage 4 done[/]\n")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# 4.1 extract facts
# ──────────────────────────────────────────────────────────────────────────────
def _extract_facts(state: State, cfg: Config, client: LLMClient) -> list[FactToVerify]:
    system = _load_section(PROMPTS_DIR / "04-research-extract-facts.md", "System")
    user = (
        f"# 视频信息\n"
        f"- 标题：{state.video.title}\n"
        f"- 频道：{state.video.uploader}\n"
        f"- 时长：{format_duration(state.video.duration_s)}\n\n"
        f"# 完整字幕\n```\n{state.video.transcript[:50000]}\n```\n\n"
        f"输出 JSON：facts_to_verify 数组（≥ 20 条），每条含 id / category / "
        f"transcript_quote / transcript_timestamp / what_to_verify / "
        f"search_priority / expected_source。"
    )

    text, in_t, out_t = client.chat(
        model=cfg.llm.models.research,
        system=system,
        user=user,
        temperature=0.2,
        max_tokens=16000,
        json_mode=True,
    )
    track(state, stage="research_extract", model=cfg.llm.models.research,
          input_tokens=in_t, output_tokens=out_t)

    try:
        data = client.parse_json(text)
    except Exception as e:
        # Try to recover from truncated JSON: trim to last complete object
        console.print(f"  [yellow]extract-facts JSON parse error: {e}; attempting recovery[/]")
        try:
            # Find last "}," before truncation point and close array+object
            last_complete = text.rfind('},')
            if last_complete > 0:
                fixed = text[:last_complete+1] + '\n  ]\n}'
                data = client.parse_json(fixed)
            else:
                return []
        except Exception:
            return []

    facts = []
    for item in data.get("facts_to_verify", []):
        try:
            ts = item.get("transcript_timestamp", 0)
            if isinstance(ts, str) and ":" in ts:
                from ..util import srt_timestamp_to_seconds
                ts = srt_timestamp_to_seconds(ts)
            facts.append(FactToVerify(
                id=item.get("id", f"fact_{len(facts):03d}"),
                category=item.get("category", "other"),
                transcript_quote=item.get("transcript_quote", ""),
                transcript_timestamp_s=float(ts) if ts else 0.0,
                what_to_verify=item.get("what_to_verify", ""),
                priority=item.get("search_priority", "medium"),
            ))
        except Exception:
            continue
    return facts


# ──────────────────────────────────────────────────────────────────────────────
# 4.2 verify via web search
# ──────────────────────────────────────────────────────────────────────────────
def _verify_facts(
    state: State,
    cfg: Config,
    client: LLMClient,
    facts: list[FactToVerify],
) -> tuple[list[VerifiedFact], list[str], list[dict[str, str]]]:
    """For each fact, run search → fetch top URL → ask LLM to summarize."""
    provider = get_search_provider(cfg.search)
    verified: list[VerifiedFact] = []
    unknowns: list[str] = []
    url_index: dict[str, dict[str, str]] = {}  # dedup by url

    # Sort by priority, cap to max_queries
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_facts = sorted(facts, key=lambda f: priority_order.get(f.priority, 2))[: cfg.search.max_queries]

    fetch_count = 0

    with Progress(transient=True) as progress:
        task = progress.add_task("verify facts", total=len(sorted_facts))

        for fact in sorted_facts:
            try:
                query = fact.what_to_verify
                hits = provider.search(query, max_results=3)
            except Exception as e:
                if cfg.debug:
                    console.print(f"    [red]search failed: {e}[/]")
                hits = []

            if not hits:
                unknowns.append(f"{fact.what_to_verify}（搜索无结果）")
                progress.advance(task)
                continue

            # Try top hit + verify URL alive
            chosen = None
            for h in hits:
                if not h.url:
                    continue
                if url_alive(h.url, timeout=cfg.search.timeout_s):
                    chosen = h
                    break

            if not chosen:
                unknowns.append(f"{fact.what_to_verify}（结果 URL 不可达）")
                progress.advance(task)
                continue

            # Webfetch content if budget allows
            content_summary = chosen.snippet
            if fetch_count < cfg.search.max_webfetch:
                ok, content = webfetch(chosen.url, timeout=cfg.search.timeout_s, max_chars=8000)
                fetch_count += 1
                if ok:
                    # Use small LLM to extract relevant fact
                    try:
                        extract_text, in_t, out_t = client.chat(
                            model=cfg.llm.models.research,
                            system="你从网页内容中精确提取一段事实。输出仅一段话，不超过 200 字。",
                            user=(
                                f"问题：{fact.what_to_verify}\n\n"
                                f"网页内容（前 8000 字符）：\n{content}\n\n"
                                f"请精确摘出与问题相关的内容（1 段，≤ 200 字）。"
                                f"如网页内容与问题无关，回复「无相关信息」。"
                            ),
                            temperature=0.1,
                            max_tokens=400,
                        )
                        track(state, stage="research_verify",
                              model=cfg.llm.models.research,
                              input_tokens=in_t, output_tokens=out_t)
                        if extract_text and "无相关" not in extract_text:
                            content_summary = extract_text.strip()
                    except Exception:
                        pass

            verified.append(VerifiedFact(
                id=fact.id,
                transcript_quote=fact.transcript_quote,
                verified_content=content_summary,
                source_url=chosen.url,
                source_name=chosen.title,
                confidence="high" if "blog." in chosen.url or ".com/blog" in chosen.url else "medium",
            ))
            url_index[chosen.url] = {
                "url": chosen.url,
                "title": chosen.title,
                "fact_id": fact.id,
            }

            progress.advance(task)

    return verified, unknowns, list(url_index.values())


# ──────────────────────────────────────────────────────────────────────────────
# Render research_notes.md
# ──────────────────────────────────────────────────────────────────────────────
def _render_notes_md(
    state: State,
    verified: list[VerifiedFact],
    unknowns: list[str],
    urls: list[dict[str, str]],
) -> str:
    title = state.video.title if state.video else ""
    lines = [
        f"# Research Notes — {title}",
        "",
        f"## 已查证事实（{len(verified)} 条）",
        "",
    ]
    for vf in verified:
        lines.append(f"### {vf.id}")
        lines.append("")
        lines.append(f"- **字幕原话**：「{vf.transcript_quote}」")
        lines.append(f"- **查到的**：{vf.verified_content}")
        lines.append(f"- **信源**：[{vf.source_name}]({vf.source_url}) — 可信度 {vf.confidence}")
        lines.append("")

    lines.append(f"## 未查到 / 官方未公布（{len(unknowns)} 条）")
    lines.append("")
    for i, u in enumerate(unknowns, start=1):
        lines.append(f"{i}. {u}")
    lines.append("")

    lines.append(f"## 可用信源 URL 清单（{len(urls)} 个）")
    lines.append("")
    for u in urls:
        lines.append(f"- [{u['title']}]({u['url']}) — fact {u['fact_id']}")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _load_section(prompt_file: Path, section: str) -> str:
    """Load # System or # User Template section from a prompt md file."""
    if not prompt_file.exists():
        return ""
    text = prompt_file.read_text()
    marker = f"# {section}"
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    # Stop at next # heading (or EOF)
    next_h = after.find("\n# ")
    body = after[:next_h] if next_h > 0 else after
    return body.strip()
