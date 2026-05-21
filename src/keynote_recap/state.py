"""Pipeline state — persisted to <output>/state.json after every stage.

Allows --start-stage to resume from any checkpoint without redoing earlier work.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class VideoMeta(BaseModel):
    """Stage 1 output."""

    url: str
    title: str = ""
    uploader: str = ""
    duration_s: float = 0.0
    resolution: str = ""
    video_path: str = ""              # downloaded mp4
    audio_path: str = ""              # extracted audio (if needed)
    subtitle_path: str = ""           # .srt or .vtt
    subtitle_lang: str = ""           # actual lang detected
    transcript: str = ""              # plain text transcript


class FrameCandidate(BaseModel):
    """Stage 2 output: PIL-scored candidate frame."""

    filename: str
    timestamp_s: float
    score: float                       # frame_scorer 0-100
    text_density: float = 0.0
    edge_density: float = 0.0
    context_subtitle: str = ""         # ±15s subtitle window


class SelectedFrame(BaseModel):
    """Stage 3 output: vision-LLM-selected frame."""

    filename: str
    timestamp_s: float
    category: str                      # demo|product|data|architecture|partner_logos|other
    caption: str                        # full caption with context
    recommended_section: str            # which section it belongs to
    info_density: float                 # 0-1
    relevance: float                    # 0-1
    source: Literal["frame_extract", "official"] = "frame_extract"


class FactToVerify(BaseModel):
    """Stage 4.1 output."""

    id: str
    category: str                       # product_name|version|date|pricing|...
    transcript_quote: str
    transcript_timestamp_s: float
    what_to_verify: str
    priority: Literal["high", "medium", "low"] = "medium"


class VerifiedFact(BaseModel):
    """Stage 4.2 output."""

    id: str
    transcript_quote: str
    verified_content: str
    source_url: str
    source_name: str
    confidence: Literal["high", "medium", "low"] = "high"


class CostEntry(BaseModel):
    """Single LLM call cost record."""

    timestamp: str
    stage: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class State(BaseModel):
    """Full pipeline state."""

    # ─── Identity ───
    url: str
    output_dir: str
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_completed_stage: float = 0.0

    # ─── Stage 1: download ───
    video: VideoMeta | None = None

    # ─── Stage 2: segment ───
    candidate_frames: list[FrameCandidate] = Field(default_factory=list)

    # ─── Stage 3: extract ───
    selected_frames: list[SelectedFrame] = Field(default_factory=list)
    rejected_frames: list[dict[str, Any]] = Field(default_factory=list)

    # ─── Stage 4: research ───
    facts_to_verify: list[FactToVerify] = Field(default_factory=list)
    verified_facts: list[VerifiedFact] = Field(default_factory=list)
    research_notes_path: str = ""              # markdown file
    unknowns: list[str] = Field(default_factory=list)
    source_urls: list[dict[str, str]] = Field(default_factory=list)

    # ─── Stage 5: draft ───
    outline_path: str = ""
    report_md_path: str = ""

    # ─── Stage 5.5: verify ───
    coverage_check_passed: bool = False
    caption_verify_path: str = ""
    lint_report_path: str = ""

    # ─── Stage 6: render ───
    report_html_path: str = ""

    # ─── Cost tracking ───
    cost_entries: list[CostEntry] = Field(default_factory=list)

    # ──────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────
    def save(self, path: Path | str | None = None) -> Path:
        """Save state to <output>/state.json."""
        if path is None:
            path = Path(self.output_dir) / "state.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2, exclude_none=False))
        return path

    @classmethod
    def load(cls, path: Path | str) -> State:
        path = Path(path)
        return cls.model_validate_json(path.read_text())

    @classmethod
    def new(cls, url: str, output_dir: Path | str) -> State:
        return cls(url=url, output_dir=str(output_dir))

    def total_cost_usd(self) -> float:
        return sum(e.cost_usd for e in self.cost_entries)
