# Changelog

All notable changes to **keynote-recap** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — M3
- `src/keynote_recap/official_channels.py`: registry of 7 publishers (Google,
  OpenAI, Anthropic, Apple, Meta, Microsoft, NVIDIA) with allow-listed
  domains, seed URLs, and product-slug URL templates.
- `stages/research.py`: official-channel-first verification pass before
  falling back to web search; new `_detect_product_names()` heuristic
  extracts capitalized product phrases from the transcript with frequency ≥ 2.
- `_summarize_page()` and `_try_official_url()` helpers for reuse across
  the official-first and search fallback passes.
- 7 new smoke tests covering the official-channels registry, publisher
  detection, URL template generation, and product-name extraction.
- `USAGE.md`: end-to-end reuse guide for new keynote URLs (one-shot recipe,
  acceptance checklist, troubleshooting matrix).
- `.github/workflows/ci.yml`: CI matrix for Python 3.10–3.13 (smoke tests +
  ruff lint).

### Changed
- Search fallback in `_verify_facts()` now biases queries toward the detected
  publisher's domains (`site:` operator).
- `confidence` is auto-assigned `high` whenever the source URL matches an
  official domain in the registry, regardless of which pass produced it.

### Fixed
- Removed dead `in_callout` tracking in `stages/verify.py` lint scan
  (resolved last lingering `F841`).

## [0.1.0a0] — M2 quality baseline (2026-05-21)

First end-to-end run that meets the M2 acceptance gates.

### Achievements vs. golden standard (Google I/O '26 keynote)

| Metric | Golden (manual) | M2 v10 (CLI) | Ratio |
|---|---|---|---|
| Lines | 783 | 486 | 62% |
| Sections | 14 | 11 | 79% |
| Images | 35 | 19 | 54% |
| Citations | — | 11 | ✓ (≥ 8) |
| L1 lint errors | 0 | 0 | ✓ |
| L2 lint warnings | 0 | 0 | ✓ |
| Wrong captions | 0 | 0 | ✓ |
| Wrong filenames | 0 | 0 | ✓ |
| Cost | ~$6 (manual time) | $0.20–0.50 (LLM) | — |
| Duration | ~6 hours | 15–25 minutes | — |

### Added — M2
- 7-stage pipeline (download → segment → extract → research → draft →
  verify → render) plus stage 5.5 (3-step quality gate).
- Stage 5.5.0: image filename existence check (whitelist guard).
- Stage 5.5.1 auto-fix: insert unused selected frames into uncovered
  sections.
- `_detect_product_names()` in stage 5.1 outline pass, fed into the prompt
  as a "must consider" list to prevent over-merging.
- Numbered filename whitelist in draft prompt to stop LLM hallucination of
  image paths.
- Anti-AI lint rules (zero-tolerance forbidden words: 巨大 / 显著 / 革命性
  / 让我们 / 不仅仅是 / etc.).
- HTML self-contained renderer (base64-inlined images) for Feishu paste.

### Added — M1
- 18 source files (~3,548 lines of Python) covering CLI, config (5 layers),
  state with checkpointing, OpenAI-compatible LLM client, search abstraction,
  cost tracking, and all 7 stage modules.
- 21 unit tests covering imports, pure-function helpers, state save/load.

### Added — M0
- 25 documents: `docs/requirements.md` (single source of truth, 38 user
  messages traced), 5 methodology docs, 9 stage prompts, and 2 worked
  examples (golden standard + research notes).

### Fixed
- Subtitle truncation at 40 K chars → full transcript fed to outline LLM
  (Gemini 1M-context).
- Callout block wrapped in ```markdown fence → strip + prompt hard-ban.
- Section over-merging (7 → 11) via product-name detection + anti-merge
  self-check in outline prompt.
- Caption language drift to English → forced Chinese + visual verification
  pass.
- Citation count short (3 → 11) via stronger draft-prompt requirements
  (≥ 10 total, ≥ 1 per section).
- Research JSON truncation at 4 K tokens → `max_tokens=16K` + recovery
  for unclosed arrays.
