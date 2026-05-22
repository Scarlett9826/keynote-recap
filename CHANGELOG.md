# Changelog

All notable changes to **keynote-recap** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — M4 (small-model support)

Optimization pass aimed at users on cheaper / medium-capability LLM
gateways (gemini-2.5-flash, qwen-vl-max, llama-3.1-vision, GPT-4o-mini,
single-vendor proxies). Goal: meaningful runs on models below
claude-opus-4 quality, plus fail-fast on models that won't work at all.

#### Vision capability probe (P1)

- `prompts/03-extract-vision-filter.md` and `prompts/05-5-caption-verify.md`
  now lead with a "Capability self-check" section. Models without vision
  must reply with the exact prefix `ERROR_NO_VISION_CAPABILITY` and stop,
  instead of fabricating captions from the subtitle text.
- `src/keynote_recap/util.py`: `VisionCapabilityError` exception +
  `detect_vision_capability_error()` helper. The detector tolerates code
  fences and avoids false-positives on legitimate JSON output.
- `stages/extract.py`: stage 3 now hard-fails with a clear remediation
  message ("set KEYNOTE_RECAP_MODEL=gemini-2.5-pro / claude-sonnet-4 /
  gpt-4o") when the probe fires.
- `stages/verify.py`: stage 5.5.2 now (a) loads its system prompt from
  the prompt file (previously hard-coded — a latent bug) and (b) marks
  the sub-check as skipped with `skip_reason: no_vision_capability` on
  probe failure rather than crashing 5.5.

#### CLI preflight + `doctor` subcommand

- `src/keynote_recap/preflight.py`: regex-based model classifier with
  three tiers: verified_multimodal / known_text_only / unknown.
  Whitelist: claude-{opus,sonnet}-{4,3.5,3.7}, gemini-{1.5,2.0,2.5}-pro,
  gpt-4o, gpt-4-turbo. Blacklist: mimo-*, gpt-4o-mini, gpt-3.5-*,
  deepseek-{v3,r1}, qwen-{max,plus,turbo,3.x}, llama-3.x. Tolerant of
  provider prefixes (`openai/gpt-4o`).
- `keynote-recap recap`: new preflight check before stage 1; aborts with
  exit 2 if a vision stage uses a known text-only model. Override with
  `--force` (which still warns the prompt-level probe will trip).
- `keynote-recap doctor`: new subcommand for standalone preflight without
  running the pipeline. Prints resolved per-stage models + capability
  verdict + reference list.
- `--llm-all` flag (and `KEYNOTE_RECAP_MODEL_ALL` env var): override ALL
  4 LLM stages with one model. Existing `--llm` only sets draft, which
  is the wrong default for users on single-model gateways.

#### Difficulty tiers for the draft prompt (P2)

- `prompts/05-draft-write-easy.md` (2745 chars, -37% vs standard):
  - 5 forbidden phrases (down from 21)
  - 15-40 images (down from 25-40 floor)
  - ≥ 5 citations (down from ≥ 10)
  - 400-900 lines (down from 600-900)
  - External methodology links inlined (medium models don't fetch)
- `prompts/05-draft-write.md`: unchanged; remains the standard tier.
- `prompts/05-draft-write-strict.md`: incremental constraints on top of
  standard (≤ 25 char sentences, ≥ 2 citations per section, ≥ 5 tables,
  9 additional forbidden phrases, "opposing view" paragraph required in
  every '一点观察' bullet). Recommended for claude-opus-4.
- `config.py`: `DraftConfig.tier` field (default `standard`).
- `stages/draft.py`: `_pick_draft_prompt()` resolves tier → file path,
  falls back to standard on unknown values.
- `cli.py`: `--tier {easy,standard,strict}` flag; the resolved tier is
  printed in the recap startup banner.

#### Forward-fill outline checklist (P3)

- `prompts/05-draft-outline.md`: replaced the after-the-fact "self-check
  for over-merging" instructions (which medium models consistently
  ignored — they treat output completion as `done` and never loop back)
  with a forward fill-in table covering 10 commonly-merged product
  categories (UCP, Neural Expressive, Pics/Stitch/Flow, glasses, Fitbit,
  Omni, Search, science, TPU, pricing). Models must answer yes/no for
  each row before writing the outline, then map yes-rows 1:1 to ##
  sections. Forward checklists are a much stronger signal for medium
  models than reverse self-checks.

#### Single-gateway config presets

- `docs/examples/config.preset-gemini-only.yaml` — all stages on Gemini
  2.5 Pro/Flash; ~\$0.40/keynote (M2 baseline reference stack).
- `docs/examples/config.preset-claude-only.yaml` — all stages on Claude
  family; sonnet for vision, opus + tier=`strict` for draft; ~\$2.50.
- `docs/examples/config.preset-openai-only.yaml` — gpt-4o for vision/draft,
  gpt-4o-mini for research only; ~\$1.20.
- `docs/examples/config.preset-mixed-cheap.yaml` — multi-vendor proxy
  (e.g. OpenRouter); gemini for vision, sonnet-4 for draft, gpt-4o-mini
  for research; ~\$0.60.
- `docs/examples/README.md`: preset selection table + "doctor before
  recap" workflow.

#### Documentation

- `README.md`: new "Model Selection" section before the quickstart, with
  verified vs known-bad model tables. Hot-fixed to main as commit
  `26ccea9` for users hitting the live link before the rest of v0.2 ships.
- `USAGE.md`: matching § 1.1.5 with the same tables, plus three usage
  patterns (`--llm-all`, config-file mixing, CLI override) and the
  `keynote-recap doctor` workflow.

### Tests

- 28 → 52 (24 new):
  - 8 for vision capability probe (detector cases, prompt file presence,
    error subclass, prompt file loading)
  - 5 for preflight model classifier (verified / text-only / unknown
    cases across 21 model names) and `--llm-all` scope correctness
  - 8 for draft tier system (default tier, per-tier file resolution,
    case-insensitivity, unknown fallback, quantitative size check)
  - 3 for config presets (existence, schema validation, gemini-only
    routes vision to Gemini)

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
