"""Configuration schema and loading.

Uses pydantic for validation. Config layers (later overrides earlier):

    1. Built-in defaults (this file)
    2. ~/.config/keynote-recap/config.yaml
    3. --config CLI override
    4. CLI flags (--llm, --keep-video, etc.)
    5. Env vars (OPENAI_API_KEY, OPENAI_BASE_URL, KEYNOTE_RECAP_MODEL, ...)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────
class LLMModels(BaseModel):
    """Per-stage model selection. Each can be overridden independently."""

    extract: str = "claude-sonnet-4"     # vision filter (stage 3)
    research: str = "gpt-4o-mini"         # research summarize (stage 4)
    draft: str = "claude-opus-4"          # main writer (stage 5)
    verify: str = "claude-sonnet-4"       # caption verify (stage 5.5)
    transcribe: str = "gemini-2.5-pro"    # fallback transcription (stage 1)


class LLMConfig(BaseModel):
    provider: Literal["openai-compatible", "anthropic-native"] = "openai-compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_s: int = 600
    max_retries: int = 3
    models: LLMModels = Field(default_factory=LLMModels)


class SearchConfig(BaseModel):
    provider: Literal["duckduckgo", "tavily", "webfetch_only"] = "duckduckgo"
    api_key_env: str = "TAVILY_API_KEY"     # only used for tavily
    timeout_s: int = 15
    # NOTE (v0.2.3): max_queries / max_webfetch moved to methodology.py
    # (RESEARCH_MAX_QUERIES / RESEARCH_MAX_WEBFETCH). Lowering them silently
    # starves the report of citations, raising them wastes API quota — both
    # are project-design contracts, not user preferences.


class VideoConfig(BaseModel):
    resolution: str = "1080p60"             # yt-dlp -f filter target
    keep_video: bool = True                  # default keep (zero-cost rerun)
    download_subtitles: bool = True
    languages: list[str] = Field(default_factory=lambda: ["zh-Hans", "zh", "en"])


class StagesConfig(BaseModel):
    """Pipeline stage range — start/end are user workflow flexibility.

    NOTE (v0.2.3): ``checkpoints`` (the human-review pause points) moved to
    methodology.py (M.PIPELINE_CHECKPOINTS). The set [3.0, 4.0, 5.5] is part
    of the project's design contract.
    """

    start: float = 1.0
    end: float = 6.0


class DraftConfig(BaseModel):
    """Stage 5 writing tier selection.

    NOTE (v0.2.3): All numeric thresholds (target lines, section count,
    callout count, citation min) moved to methodology.py constants. The
    only knob that remains here is ``tier`` — the project's sanctioned
    way to dial difficulty for weaker LLMs without touching methodology.
    """

    # Difficulty tier — selects which 05-draft-write-*.md prompt to load.
    # easy:     fewer forbidden phrases, looser image/citation thresholds.
    #           Suitable for medium-capability multimodal models
    #           (gemini-2.5-flash, qwen-vl-max, llama-3.1-vision).
    # standard: current 21 forbidden phrases, 25-40 images, ≥ 10 citations.
    #           Works on claude-sonnet-4 / gpt-4o / gemini-2.5-pro.
    # strict:   tighter constraints (≤ 25 char sentences, ≥ 2 citations
    #           per section). Recommended for claude-opus-4.
    #
    # Default is "strict" (M5). If you're using a weaker LLM, pass
    # `--tier easy` (or `--tier standard`) to relax constraints rather
    # than seeing low-quality output.
    tier: str = "strict"


class Config(BaseModel):
    """Top-level config.

    Methodology parameters (chunk count, frame floors, citation min,
    section count, etc.) live in ``methodology.py`` and are NOT user-tunable.
    See that module's docstring for rationale.
    """

    llm: LLMConfig = Field(default_factory=LLMConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    stages: StagesConfig = Field(default_factory=StagesConfig)
    draft: DraftConfig = Field(default_factory=DraftConfig)
    language: Literal["zh", "en"] = "zh"
    template: Literal["keynote-recap"] = "keynote-recap"  # MVP only

    # ─── runtime overrides (not in YAML) ───
    debug: bool = False
    # v0.3.7 P2: sanctioned soft-floor escape hatch. Set via
    # ``--accept-low-yield`` CLI flag. When True, stage 3 hard-floor
    # breaches (count < EXTRACT_FINAL_COUNT_MIN or useful_ratio <
    # EXTRACT_USEFUL_RATIO_MIN) are converted from fatal abort into a
    # logged override that gets stamped into report frontmatter,
    # integrity callout, and HTML banner. AGENTS.md prohibits *editing*
    # methodology constants; this flag is the project-sanctioned way to
    # ship a report that misses the floor (e.g. low-res B station source,
    # cinematic content with sparse text frames). The override is always
    # visible in the published artifact — agents cannot game it silently.
    accept_low_yield: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Loading
# ──────────────────────────────────────────────────────────────────────────────
def default_config_path() -> Path:
    """~/.config/keynote-recap/config.yaml"""
    return Path.home() / ".config" / "keynote-recap" / "config.yaml"


def load_config(
    config_path: Path | None = None,
    llm_override: str | None = None,
    llm_override_all: str | None = None,
    keep_video: bool | None = None,
) -> Config:
    """Load config with layered overrides.

    Override precedence (later wins):
        1. defaults (LLMModels class)
        2. config file (~/.config/keynote-recap/config.yaml or --config path)
        3. ``llm_override`` (--llm flag)        — sets draft only
        4. ``llm_override_all`` (--llm-all)     — sets all 4 LLM stages
        5. KEYNOTE_RECAP_MODEL env var          — sets draft only
        6. KEYNOTE_RECAP_MODEL_ALL env var      — sets all 4 LLM stages
        7. OPENAI_BASE_URL env var              — sets endpoint
    """
    # Layer 1: defaults
    cfg = Config()

    # Layer 2: file
    path = config_path or default_config_path()
    if path.exists():
        with path.open() as f:
            file_data = yaml.safe_load(f) or {}
        cfg = Config.model_validate(_deep_merge(cfg.model_dump(), file_data))

    # Layer 3 + 4: CLI overrides
    # Note: --llm / KEYNOTE_RECAP_MODEL only sets the draft model so users can
    # mix-and-match (e.g. cheap research, premium draft). To set ONE model for
    # all stages, use --llm-all / KEYNOTE_RECAP_MODEL_ALL — common when the
    # user's gateway only supports a single model.
    if llm_override:
        cfg.llm.models.draft = llm_override

    if llm_override_all:
        cfg.llm.models.extract = llm_override_all
        cfg.llm.models.research = llm_override_all
        cfg.llm.models.draft = llm_override_all
        cfg.llm.models.verify = llm_override_all

    if keep_video is not None:
        cfg.video.keep_video = keep_video

    # Layer 5: env vars
    if env_model := os.getenv("KEYNOTE_RECAP_MODEL"):
        cfg.llm.models.draft = env_model
    if env_model_all := os.getenv("KEYNOTE_RECAP_MODEL_ALL"):
        cfg.llm.models.extract = env_model_all
        cfg.llm.models.research = env_model_all
        cfg.llm.models.draft = env_model_all
        cfg.llm.models.verify = env_model_all
    if env_base := os.getenv("OPENAI_BASE_URL"):
        cfg.llm.base_url = env_base

    return cfg


def write_sample_config(path: Path) -> None:
    """Write a sample config YAML to path.

    Only environment / identity / sanctioned-tunable settings are exposed.
    Methodology parameters (frame floors, citation min, section count, etc.)
    are locked in src/keynote_recap/methodology.py — see that file's
    docstring for the rationale.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = """# keynote-recap config
# Full schema docs: https://github.com/Scarlett9826/keynote-recap/blob/main/docs/configuration.md
#
# Methodology parameters (chunk count, frame floors, citation min, section
# count, agent concurrency, etc.) are NOT here — they live in
# src/keynote_recap/methodology.py as locked constants. Modifying them is
# a code change, not a config tweak. See that file for rationale.

llm:
  provider: openai-compatible
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  timeout_s: 600
  max_retries: 3
  models:
    extract: claude-sonnet-4       # vision filter (stage 3)
    research: gpt-4o-mini           # research summarize (stage 4)
    draft: claude-opus-4            # main writer (stage 5) — most important
    verify: claude-sonnet-4         # caption verify (stage 5.5)
    transcribe: gemini-2.5-pro      # fallback transcription (stage 1)

search:
  provider: duckduckgo               # duckduckgo | tavily | webfetch_only
  timeout_s: 15                       # network-environment knob; OK to tune

video:
  resolution: 1080p60
  keep_video: true
  download_subtitles: true
  languages: [zh-Hans, zh, en]

stages:
  start: 1.0                          # which stage to start from (workflow flag)
  end: 6.0                            # which stage to end at

draft:
  tier: strict                        # strict | standard | easy
                                      # Sanctioned way to dial difficulty for
                                      # weaker LLMs. See draft.tier docstring.

language: zh                         # zh | en
template: keynote-recap              # MVP only supports keynote-recap
"""
    path.write_text(sample)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
