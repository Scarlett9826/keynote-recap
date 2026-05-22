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
    max_queries: int = 30
    max_webfetch: int = 50
    timeout_s: int = 15


class VideoConfig(BaseModel):
    resolution: str = "1080p60"             # yt-dlp -f filter target
    keep_video: bool = True                  # default keep (zero-cost rerun)
    download_subtitles: bool = True
    languages: list[str] = Field(default_factory=lambda: ["zh-Hans", "zh", "en"])


class StagesConfig(BaseModel):
    start: float = 1.0
    end: float = 6.0
    checkpoints: list[float] = Field(default_factory=lambda: [3.0, 4.0, 5.5])


class FrameFilterConfig(BaseModel):
    """Stage 2 + 3 filter parameters."""

    # Stage 2: PIL frame_scorer 初筛
    candidate_count: int = 80                # frame_scorer 输出数
    sample_interval_s: float = 5.0           # 每 N 秒抽 1 帧
    min_text_density: float = 0.05           # 文本/边缘密度下限

    # Stage 3: vision LLM 精筛
    final_count_min: int = 30
    final_count_max: int = 50
    info_density_min: float = 0.7
    relevance_min: float = 0.7


class DraftConfig(BaseModel):
    """Stage 5 writing parameters."""

    target_lines_min: int = 600
    target_lines_max: int = 900
    section_count_min: int = 8
    section_count_max: int = 14
    callout_block_min: int = 8                # 整体概要块数
    callout_block_max: int = 12
    citation_min: int = 8                     # `> 📎 补充信源` 块最低数


class Config(BaseModel):
    """Top-level config."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    stages: StagesConfig = Field(default_factory=StagesConfig)
    frame_filter: FrameFilterConfig = Field(default_factory=FrameFilterConfig)
    draft: DraftConfig = Field(default_factory=DraftConfig)
    language: Literal["zh", "en"] = "zh"
    template: Literal["keynote-recap"] = "keynote-recap"  # MVP only

    # ─── runtime overrides (not in YAML) ───
    debug: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Loading
# ──────────────────────────────────────────────────────────────────────────────
def default_config_path() -> Path:
    """~/.config/keynote-recap/config.yaml"""
    return Path.home() / ".config" / "keynote-recap" / "config.yaml"


def load_config(
    config_path: Path | None = None,
    llm_override: str | None = None,
    keep_video: bool | None = None,
) -> Config:
    """Load config with layered overrides."""
    # Layer 1: defaults
    cfg = Config()

    # Layer 2: file
    path = config_path or default_config_path()
    if path.exists():
        with path.open() as f:
            file_data = yaml.safe_load(f) or {}
        cfg = Config.model_validate(_deep_merge(cfg.model_dump(), file_data))

    # Layer 3 + 4: CLI overrides
    if llm_override:
        cfg.llm.models.draft = llm_override

    if keep_video is not None:
        cfg.video.keep_video = keep_video

    # Layer 5: env vars
    if env_model := os.getenv("KEYNOTE_RECAP_MODEL"):
        cfg.llm.models.draft = env_model
    if env_base := os.getenv("OPENAI_BASE_URL"):
        cfg.llm.base_url = env_base

    return cfg


def write_sample_config(path: Path) -> None:
    """Write a sample config YAML to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = """# keynote-recap config
# Full schema docs: https://github.com/Scarlett9826/keynote-recap/blob/main/docs/configuration.md

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
  max_queries: 30
  max_webfetch: 50
  timeout_s: 15

video:
  resolution: 1080p60
  keep_video: true
  download_subtitles: true
  languages: [zh-Hans, zh, en]

stages:
  start: 1.0
  end: 6.0
  checkpoints: [3.0, 4.0, 5.5]      # human review pause points

frame_filter:
  candidate_count: 80
  sample_interval_s: 5.0
  final_count_min: 30
  final_count_max: 50

draft:
  target_lines_min: 600
  target_lines_max: 900
  section_count_min: 8
  section_count_max: 14
  callout_block_min: 8
  callout_block_max: 12
  citation_min: 8

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
