"""Pipeline state — persisted to <output>/state.json after every stage.

Allows --start-stage to resume from any checkpoint without redoing earlier work.
"""
from __future__ import annotations

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
    # M6: is the frame from a live keynote scene (stage / speaker / PPT / live demo)
    # or an inserted official render / marketing clip? Used by 5.5.6 source-mix
    # check (live ratio must be >= 70% in strict tier).
    is_live: bool = True
    # M6: human-readable summary of what specific info the frame conveys with
    # caption hidden — populated by stage 3 vision LLM as a self-discipline
    # check. Frames where this is empty or generic ("好看 / 漂亮") indicate
    # weak info density and should have been rejected.
    what_can_be_read: str = ""


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
    structure_check_passed: bool = True   # default True so legacy state.json reload doesn't trigger retry
    placeholder_detected: bool = False    # 5.5.0: missing frame filenames in report.md
    lint_hard_failed: bool = False        # 5.5.3: any L1 forbidden phrase / emoji / transcription tell
    bucket_placement_passed: bool = True  # 5.5.4b (M6 D1): images in correct chapter bucket
    image_mix_passed: bool = True         # 5.5.6 (M6 D2): live ratio + total floor
    topic_coverage_passed: bool = True    # 5.5.7 (M6 D4): high-freq topic coverage
    caption_verify_path: str = ""
    lint_report_path: str = ""

    # ─── Quality gate retry tracking (M5/M6) ───
    draft_retry_count: int = 0
    extract_retry_count: int = 0          # M6: stage 3 retried once for image-mix/topic-coverage
    final_quality_warnings: list[str] = Field(default_factory=list)
    quality_passed: bool = True

    # ─── Expectation-management warnings (M7 / v0.2.2) ───
    # Surfaced both at stage banners and in the final HTML report so users can
    # tell apart "project-level quality gate" failures from environment / model
    # capability issues that the project cannot control.
    preflight_env_warnings: list[str] = Field(default_factory=list)
    preflight_model_warnings: list[str] = Field(default_factory=list)
    runtime_warnings: list[str] = Field(default_factory=list)
    models_used: dict[str, str] = Field(default_factory=dict)
    model_tiers: dict[str, str] = Field(default_factory=dict)
    # v0.2.3: project-controlled per-stage agent concurrency (1 if not eligible
    # or model not verified; up to AGENT_PARALLEL_VERIFIED_CAP otherwise).
    # Surfaced in stage banner and report responsibility section.
    stage_parallelism: dict[str, int] = Field(default_factory=dict)
    # v0.2.4 (M9.4/M9.5): which stage numbers were skipped + why. Drives
    # report.md frontmatter and the integrity-callout template selection.
    # Stage numbers are floats matching last_completed_stage (e.g. 1.0, 4.0).
    stages_skipped: list[float] = Field(default_factory=list)
    stages_skip_reasons: dict[str, str] = Field(default_factory=dict)
    stages_completed: list[float] = Field(default_factory=list)
    # v0.2.4 (M9.2): user-supplied transcript path. The sanctioned escape
    # hatch when yt-dlp can't fetch subtitles (Bilibili 412, region locks,
    # private videos with manual transcript). Set via --transcript-file.
    transcript_override_path: str = ""

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
