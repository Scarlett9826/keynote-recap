# Configuration Guide

## Config Layers (later overrides earlier)

| Priority | Source | Example |
|---|---|---|
| 1 (lowest) | Built-in defaults | `src/keynote_recap/config.py` |
| 2 | `~/.config/keynote-recap/config.yaml` | global user config |
| 3 | `--config <path>` CLI flag | per-project config |
| 4 | CLI flags | `--llm`, `--keep-video`, etc. |
| 5 (highest) | Environment variables | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |

## Quick Start

```bash
# Generate a sample config
keynote-recap config --init

# Edit it
vim keynote-recap.yaml

# Run with your config
keynote-recap recap <URL> -c keynote-recap.yaml
```

## Full Config Reference

### `llm` — LLM Provider & Models

```yaml
llm:
  provider: openai-compatible        # openai-compatible | anthropic-native
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY        # env var name for the API key
  timeout_s: 600                     # per-request timeout (seconds)
  max_retries: 3                     # retry count on transient errors
  models:
    extract: claude-sonnet-4         # stage 3: vision frame filter
    research: gpt-4o-mini            # stage 4: research fact extraction
    draft: claude-opus-4             # stage 5: main body writer
    verify: claude-sonnet-4          # stage 5.5: caption verification
    transcribe: gemini-2.5-pro       # stage 1: subtitle transcription
```

**Per-stage model selection rationale:**

| Stage | Recommended | Why |
|---|---|---|
| extract (vision) | claude-sonnet-4 / gemini-2.5-pro | needs strong image understanding |
| research | gpt-4o-mini / gemini-2.5-flash | cheap, fast, text-only |
| draft | claude-opus-4 / gemini-2.5-pro | best writing quality, most important |
| verify (vision) | claude-sonnet-4 / gemini-2.5-pro | needs image understanding |
| transcribe | gemini-2.5-pro | good subtitle quality, reasonable cost |

**Using a non-OpenAI endpoint** (e.g., a corporate LLM gateway, OpenRouter, Together, Anyscale, …):

```yaml
llm:
  provider: openai-compatible
  base_url: https://your-llm-proxy.example.com/v1
  api_key_env: CUSTOM_LLM_API_KEY
  models:
    # Model IDs depend on the proxy. Many corporate gateways prefix the
    # upstream provider, e.g. `vendor/gemini-2.5-pro` or `openrouter/google/gemini-pro-1.5`.
    extract: gemini-2.5-pro
    research: gemini-2.5-flash
    draft: gemini-2.5-pro
    verify: gemini-2.5-pro
    transcribe: gemini-2.5-pro
```

> Some OpenAI-compatible gateways do not proxy Claude models (the Anthropic
> wire format differs). If `claude-*` returns 404, fall back to `gemini-2.5-pro`
> or `gpt-4o` to confirm connectivity, then file a ticket with your gateway
> vendor for Claude support.

### `search` — Web Search Provider

```yaml
search:
  provider: duckduckgo               # duckduckgo | tavily | webfetch_only
  api_key_env: TAVILY_API_KEY        # only used when provider=tavily
  max_queries: 30                    # max search queries per run
  max_webfetch: 50                   # max URL fetches per run
  timeout_s: 15                      # per-request timeout
```

**Provider comparison:**

| Provider | Cost | Quality | Setup |
|---|---|---|---|
| `duckduckgo` | Free | Medium | None |
| `tavily` | $5/mo | High | `TAVILY_API_KEY` |
| `webfetch_only` | Free | Low | None (no search, just fetch known URLs) |

### `video` — Download Settings

```yaml
video:
  resolution: 1080p60                # yt-dlp -f filter target
  keep_video: true                   # keep video.mp4 after pipeline (recommended)
  download_subtitles: true           # auto-download subtitles via yt-dlp
  languages:                         # subtitle language priority order
    - zh-Hans
    - zh
    - en
```

**`keep_video: true`** is strongly recommended. Deleting the video means re-downloading 1-2GB for every re-run.

### `stages` — Pipeline Control

```yaml
stages:
  start: 1.0                         # first stage to run
  end: 6.0                           # last stage to run
  checkpoints: [3.0, 4.0, 5.5]       # pause points for review (empty = no pause)
```

**Stage numbers:**

| Stage | Number | Description |
|---|---|---|
| download | 1.0 | yt-dlp video + subtitles |
| segment | 2.0 | ffmpeg frame extraction + PIL scoring |
| extract | 3.0 | vision LLM frame filtering |
| research | 4.0 | fact extraction + web verification |
| draft | 5.0 | outline → body → callout |
| verify | 5.5 | coverage + caption + lint checks |
| render | 6.0 | markdown → self-contained HTML |

**Resume from a specific stage:**

```bash
keynote-recap recap <URL> --start-stage 5 --end-stage 6
```

### `frame_filter` — Frame Selection

```yaml
frame_filter:
  # Stage 2: PIL frame_scorer (zero LLM cost)
  candidate_count: 80                # top N frames after PIL scoring
  sample_interval_s: 5.0             # extract 1 frame every N seconds
  min_text_density: 0.05             # minimum text/edge density threshold

  # Stage 3: vision LLM filtering
  final_count_min: 30                # minimum frames after vision filter
  final_count_max: 50                # maximum frames after vision filter
  info_density_min: 0.7              # minimum information density score
  relevance_min: 0.7                 # minimum section relevance score
```

**Tuning tips:**
- For a 2-hour keynote at 5s intervals: ~1440 frames → 80 candidates → 30-50 final
- Increase `sample_interval_s` to 10 for faster processing (fewer candidates)
- Decrease `final_count_min` if vision LLM is rejecting too many

### `draft` — Writing Parameters

```yaml
draft:
  target_lines_min: 600              # minimum report lines
  target_lines_max: 900              # maximum report lines
  section_count_min: 8               # minimum chapter count
  section_count_max: 14              # maximum chapter count
  callout_block_min: 8               # minimum callout summary blocks
  callout_block_max: 12              # maximum callout summary blocks
  citation_min: 8                    # minimum `> 📎 补充信源` blocks
```

### `language` & `template`

```yaml
language: zh                         # zh (Chinese) | en (English)
template: keynote-recap              # report template name
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | LLM API key | (required) |
| `OPENAI_BASE_URL` | LLM base URL | `https://api.openai.com/v1` |
| `KEYNOTE_RECAP_MODEL` | Override all stage models | (uses config) |
| `TAVILY_API_KEY` | Tavily search API key | (only for tavily) |
| `HTTP_PROXY` / `HTTPS_PROXY` | Proxy for web search | (system default) |

## Example: Minimal Config

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  models:
    draft: gpt-4o
    extract: gpt-4o
    verify: gpt-4o
search:
  provider: duckduckgo
video:
  keep_video: true
```

## Example: Cost-Optimized Config

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  models:
    extract: gpt-4o-mini             # cheaper vision
    research: gpt-4o-mini            # cheap research
    draft: gpt-4o                    # good writing
    verify: gpt-4o-mini              # cheap verify
    transcribe: gpt-4o-mini          # cheap transcribe
frame_filter:
  candidate_count: 50                # fewer candidates → fewer LLM calls
  final_count_min: 25
draft:
  citation_min: 6                    # fewer citations → shorter report
```

Expected cost: ~$0.10-0.20 per run (vs ~$0.30-0.50 with Opus).
