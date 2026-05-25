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

from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from .. import methodology as M
from ..config import Config
from ..cost_tracker import track
from ..llm_client import LLMClient
from ..official_channels import (
    candidate_urls_for_product,
    detect_publisher,
    get_channel,
    is_official_url,
)
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
# 4.2 verify — official-channel-first, search as fallback
# ──────────────────────────────────────────────────────────────────────────────
def _detect_product_names(transcript: str, min_count: int = 2, max_n: int = 30) -> list[str]:
    """Extract candidate product names from the transcript.

    Heuristic: tokens matching `<Capitalized Word>(?: Capitalized Word)?` plus
    optional version suffix like `3` / `3.0` / `Pro`. Keep names mentioned
    ≥ min_count times, sorted by frequency.
    """
    import re
    from collections import Counter

    # E.g., "Gemini 3 Pro", "Antigravity", "Veo 3", "ChatGPT Atlas"
    pattern = re.compile(
        r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z0-9]+){0,2}(?:\s+\d+(?:\.\d+)?)?(?:\s+(?:Pro|Ultra|Max|Mini|Lite|Plus))?)\b"
    )
    raw = pattern.findall(transcript or "")
    # Strip leading common English stopwords that get glued on by sentence starts
    leading_stop = {
        "The", "And", "For", "But", "When", "What", "How", "We", "You", "It", "I",
        "Today", "With", "Now", "So", "If", "Then", "This", "That", "These", "Those",
        "Our", "Your", "My", "His", "Her", "Their",
    }

    def _clean(name: str) -> str:
        parts = name.strip().split()
        while parts and parts[0] in leading_stop:
            parts = parts[1:]
        return " ".join(parts)

    cleaned = [c for c in (_clean(x) for x in raw) if c and len(c) >= 3]
    cnt = Counter(cleaned)
    out = [name for name, n in cnt.most_common(max_n) if n >= min_count]
    return out[:max_n]


def _summarize_page(
    state: State,
    cfg: Config,
    client: LLMClient,
    fact: FactToVerify,
    content: str,
) -> str | None:
    """Ask the research model to extract one short paragraph relevant to fact."""
    try:
        text, in_t, out_t = client.chat(
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
        if text and "无相关" not in text:
            return text.strip()
    except Exception:
        return None
    return None


def _try_official_url(
    state: State,
    cfg: Config,
    client: LLMClient,
    fact: FactToVerify,
    url: str,
    page_cache: dict[str, str],
) -> tuple[VerifiedFact, str] | None:
    """Try to verify a fact via a single official URL. Returns (vf, content) or None."""
    if url in page_cache:
        content = page_cache[url]
    else:
        if not url_alive(url, timeout=cfg.search.timeout_s):
            return None
        ok, content = webfetch(url, timeout=cfg.search.timeout_s, max_chars=8000)
        if not ok or not content:
            return None
        page_cache[url] = content

    summary = _summarize_page(state, cfg, client, fact, content)
    if not summary:
        return None

    # Pick a title from the first non-empty markdown heading or first 80 chars
    title = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("# ").strip()
            break
    if not title:
        title = content[:80].replace("\n", " ").strip()

    return (
        VerifiedFact(
            id=fact.id,
            transcript_quote=fact.transcript_quote,
            verified_content=summary,
            source_url=url,
            source_name=title or url,
            confidence="high",
        ),
        content,
    )


def _verify_facts(
    state: State,
    cfg: Config,
    client: LLMClient,
    facts: list[FactToVerify],
) -> tuple[list[VerifiedFact], list[str], list[dict[str, str]]]:
    """Verify facts by combining:
        1. Official-channel-first: detect publisher, fetch seed URLs + product
           URL templates derived from transcript, summarize relevant content.
        2. Generic web search as fallback when no official source verifies the fact.
    """
    verified: list[VerifiedFact] = []
    unknowns: list[str] = []
    url_index: dict[str, dict[str, str]] = {}

    # Sort by priority, cap to max_queries
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_facts = sorted(facts, key=lambda f: priority_order.get(f.priority, 2))[: M.RESEARCH_MAX_QUERIES]

    # ─── Detect publisher & build candidate URL pool ───
    transcript = state.video.transcript if state.video else ""
    title = state.video.title if state.video else ""
    uploader = state.video.uploader if state.video else ""
    publisher = detect_publisher(uploader, title, transcript[:2000])
    channel = get_channel(publisher)

    candidate_urls: list[str] = []
    if channel:
        console.print(f"  [4.2] Detected publisher: [cyan]{publisher}[/] "
                      f"({len(channel.domains)} official domains)")
        # Seed URLs (landing pages — index of recent posts)
        candidate_urls.extend(channel.seed_urls)
        # Product-derived URLs
        product_names = _detect_product_names(transcript)
        if product_names:
            console.print(f"        Detected products: {', '.join(product_names[:8])}"
                          f"{' …' if len(product_names) > 8 else ''}")
        for name in product_names:
            candidate_urls.extend(candidate_urls_for_product(channel, name))
        # Dedup, preserve order
        seen: set[str] = set()
        candidate_urls = [u for u in candidate_urls if not (u in seen or seen.add(u))]
        # Cap to a reasonable budget
        candidate_urls = candidate_urls[: M.RESEARCH_MAX_WEBFETCH * 2]
    else:
        console.print("  [4.2] No publisher detected; using search-only mode")

    page_cache: dict[str, str] = {}
    fetch_count = 0

    # ─── Pass 1: official-channel-first ───
    if candidate_urls:
        with Progress(transient=True) as progress:
            task = progress.add_task("official-first verify", total=len(sorted_facts))
            for fact in sorted_facts:
                hit = None
                for url in candidate_urls:
                    if fetch_count >= M.RESEARCH_MAX_WEBFETCH:
                        break
                    # Skip URLs already-cached as failed
                    if url in page_cache and not page_cache[url]:
                        continue
                    fetch_count += 1 if url not in page_cache else 0
                    res = _try_official_url(state, cfg, client, fact, url, page_cache)
                    if res:
                        hit = res
                        break
                if hit:
                    vf, _content = hit
                    verified.append(vf)
                    url_index[vf.source_url] = {
                        "url": vf.source_url,
                        "title": vf.source_name,
                        "fact_id": vf.id,
                    }
                progress.advance(task)
        console.print(f"        Official-first verified: {len(verified)} / {len(sorted_facts)}")

    verified_ids = {v.id for v in verified}
    remaining = [f for f in sorted_facts if f.id not in verified_ids]

    # ─── Pass 2: search fallback ───
    if remaining and fetch_count < M.RESEARCH_MAX_WEBFETCH:
        provider = get_search_provider(cfg.search)
        with Progress(transient=True) as progress:
            task = progress.add_task("search fallback", total=len(remaining))
            for fact in remaining:
                try:
                    query = fact.what_to_verify
                    if channel:
                        # Bias query toward official domains
                        domain_hint = " OR ".join(f"site:{d}" for d in channel.domains[:3])
                        query = f"{query} ({domain_hint})"
                    hits = provider.search(query, max_results=3)
                except Exception as e:
                    if cfg.debug:
                        console.print(f"    [red]search failed: {e}[/]")
                    hits = []

                if not hits:
                    unknowns.append(f"{fact.what_to_verify}（搜索无结果）")
                    progress.advance(task)
                    continue

                chosen = None
                for h in hits:
                    if h.url and url_alive(h.url, timeout=cfg.search.timeout_s):
                        chosen = h
                        break
                if not chosen:
                    unknowns.append(f"{fact.what_to_verify}（结果 URL 不可达）")
                    progress.advance(task)
                    continue

                content_summary = chosen.snippet
                if fetch_count < M.RESEARCH_MAX_WEBFETCH:
                    ok, content = webfetch(chosen.url, timeout=cfg.search.timeout_s, max_chars=8000)
                    fetch_count += 1
                    if ok:
                        s = _summarize_page(state, cfg, client, fact, content)
                        if s:
                            content_summary = s

                conf = "high" if is_official_url(chosen.url, channel) else "medium"
                verified.append(VerifiedFact(
                    id=fact.id,
                    transcript_quote=fact.transcript_quote,
                    verified_content=content_summary,
                    source_url=chosen.url,
                    source_name=chosen.title,
                    confidence=conf,
                ))
                url_index[chosen.url] = {
                    "url": chosen.url,
                    "title": chosen.title,
                    "fact_id": fact.id,
                }
                progress.advance(task)
    else:
        # Anything still unverified → unknown
        for fact in remaining:
            unknowns.append(f"{fact.what_to_verify}（官方渠道未覆盖且预算用尽）")

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
