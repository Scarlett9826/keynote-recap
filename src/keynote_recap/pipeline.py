"""Pipeline orchestrator: run all 7 stages with checkpoints.

Stages:
    1.0  download   — yt-dlp video + subtitles
    2.0  segment    — ffmpeg sample + frame_scorer initial filter
    3.0  extract    — vision LLM three-principle filter
    4.0  research   — extract facts + verify via web search
    5.0  draft      — outline + body + callout
    5.5  verify     — coverage + caption verify + anti-AI lint
    6.0  render     — markdown → self-contained HTML
    7.0  publish    — (optional, not implemented in MVP)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.prompt import Confirm

from .config import Config
from .cost_tracker import format_summary
from .stages import download, draft, extract, render, research, segment, verify
from .state import State

console = Console()


# Stage registry: name → (numeric, runner)
STAGES: dict[str, tuple[float, Callable[[State, Config], State]]] = {
    "download": (1.0, download.run),
    "segment":  (2.0, segment.run),
    "extract":  (3.0, extract.run),
    "research": (4.0, research.run),
    "draft":    (5.0, draft.run),
    "verify":   (5.5, verify.run),
    "render":   (6.0, render.run),
}


def _collect_draft_failures(state: State) -> list[str]:
    """Failures that should be fixed by re-running stage 5 (draft).

    These are writing-side problems: the frame selection was OK but the
    drafting LLM produced poor markdown structure / forbidden phrases /
    placed images in the wrong chapter despite the buckets.
    """
    issues: list[str] = []
    if state.placeholder_detected:
        issues.append(
            "5.5.0 image filename: report references frame files that don't exist "
            "(LLM invented placeholder names instead of using selected_frames list)"
        )
    if not state.coverage_check_passed:
        issues.append("5.5.1 coverage: one or more chapters missing images")
    if state.lint_hard_failed:
        issues.append(
            "5.5.3 anti-AI lint: forbidden phrases/emoji/transcription tells found"
        )
    if not state.bucket_placement_passed:
        issues.append(
            "5.5.4b bucket placement: images placed cross-bucket "
            "(LLM ignored per-chapter frame buckets)"
        )
    if not state.structure_check_passed:
        issues.append(
            "5.5.5 structure: missing 核心判断/quotes/tables, or chapter heading malformed"
        )
    return issues


def _collect_extract_failures(state: State) -> list[str]:
    """Failures that require re-running stage 3 (extract — vision filter).

    These are frame-selection problems: stage 5 cannot fix them because the
    selected_frames pool itself is bad.
    """
    issues: list[str] = []
    if not state.image_mix_passed:
        issues.append(
            "5.5.6 image mix: total frames < 25 or live ratio < 70% "
            "(too many marketing renders / inserts vs. live keynote frames)"
        )
    if not state.topic_coverage_passed:
        issues.append(
            "5.5.7 topic coverage: a high-frequency topic in the transcript "
            "has zero associated frames (vision LLM was too aggressive)"
        )
    return issues


# Backward-compat alias for any external caller; prefer the two new helpers.
def _collect_quality_failures(state: State) -> list[str]:
    return _collect_extract_failures(state) + _collect_draft_failures(state)


def run_pipeline(
    *,
    url: str,
    output_dir: Path,
    config: Config,
    start_stage: float = 1.0,
    end_stage: float = 6.0,
    checkpoint: bool = True,
    debug: bool = False,
) -> State:
    """Run pipeline from start_stage to end_stage (inclusive)."""
    config.debug = debug

    state_path = output_dir / "state.json"
    if state_path.exists() and start_stage > 1.0:
        state = State.load(state_path)
        console.print(f"[dim]Resumed from {state_path} (last completed: stage {state.last_completed_stage})[/]\n")
    else:
        state = State.new(url=url, output_dir=output_dir)

    for name, (num, runner) in STAGES.items():
        if num < start_stage or num > end_stage:
            continue
        if num <= state.last_completed_stage and start_stage <= state.last_completed_stage:
            console.print(f"[dim]Skipping stage {num} ({name}) — already done[/]")
            continue

        try:
            state = runner(state, config)
        except Exception as e:
            console.print(f"[bold red]Stage {num} ({name}) failed:[/] {e}")
            state.save()
            if debug:
                raise
            return state

        # ─── Quality gate (after stage 5.5 verify): two-tier retry policy ───
        # Tier 1: extract failures (image mix / topic coverage) → re-run from stage 3.
        #         Stage 5 cannot fix selected_frames being wrong.
        # Tier 2: draft failures (lint / placeholder / bucket placement / coverage)
        #         → re-run only stage 5 (draft).
        # Each tier retries at most once; remaining issues become banner warnings.
        if num == 5.5:
            # Tier 1: extract retry (highest priority)
            extract_fails = _collect_extract_failures(state)
            if extract_fails and state.extract_retry_count == 0:
                console.print(
                    f"\n[bold yellow]⚠ Frame-selection gate failed:[/] "
                    f"{len(extract_fails)} hard issues — re-running stage 3 (vision filter).\n"
                )
                for issue in extract_fails:
                    console.print(f"   • {issue}")
                state.extract_retry_count = 1
                # Roll back to before stage 3 so extract + research(skip) + draft + verify all re-run
                state.last_completed_stage = 2.0
                state.save()
                try:
                    state = STAGES["extract"][1](state, config)
                    # research is expensive and not affected by frame selection;
                    # only re-run if research_notes_path is missing
                    if not state.research_notes_path:
                        state = STAGES["research"][1](state, config)
                    state = STAGES["draft"][1](state, config)
                    state = STAGES["verify"][1](state, config)
                except Exception as e:
                    console.print(f"[bold red]Stage 3 retry failed:[/] {e}")
                    state.save()
                    if debug:
                        raise
                    return state
                # Re-collect after stage 3 retry (may now reveal pure-draft issues)

            # Tier 2: draft retry
            draft_fails = _collect_draft_failures(state)
            if draft_fails and state.draft_retry_count == 0:
                console.print(
                    f"\n[bold yellow]⚠ Draft-quality gate failed:[/] "
                    f"{len(draft_fails)} hard issues — re-running stage 5 (draft) once.\n"
                )
                for issue in draft_fails:
                    console.print(f"   • {issue}")
                state.draft_retry_count = 1
                state.last_completed_stage = 4.0
                state.save()
                try:
                    state = STAGES["draft"][1](state, config)
                    state = STAGES["verify"][1](state, config)
                except Exception as e:
                    console.print(f"[bold red]Stage 5 retry failed:[/] {e}")
                    state.save()
                    if debug:
                        raise
                    return state

            # Final assessment after all retries
            still_failing = _collect_quality_failures(state)
            if still_failing:
                state.quality_passed = False
                state.final_quality_warnings = still_failing
                console.print(
                    f"\n[bold yellow]⚠ Quality gate still failing[/]: "
                    f"{len(still_failing)} issues remain — banner will be added to report.\n"
                )
                for issue in still_failing:
                    console.print(f"   • {issue}")
            else:
                state.quality_passed = True
                console.print("[green]✓ Quality gate passed[/]\n")
            state.save()

        # Checkpoint pause
        if checkpoint and num in config.stages.checkpoints and num < end_stage:
            console.print(f"\n[yellow]Checkpoint after stage {num}.[/]")
            console.print(f"  Output dir: {output_dir}")
            console.print(f"  State:      {state_path}")
            if not Confirm.ask("Continue to next stage?", default=True):
                console.print("[yellow]Paused. Resume with: keynote-recap recap <url> --start-stage <next>[/]")
                return state
            console.print()

    # Cost summary
    console.print()
    console.print(format_summary(state))
    console.print()

    # Final report path
    if state.report_html_path:
        console.print("[bold green]✓ Pipeline complete[/]")
        console.print(f"  Markdown: {state.report_md_path}")
        console.print(f"  HTML:     {state.report_html_path}")

    return state


def run_single_stage(stage_name: str, *, state: State, config: Config, debug: bool = False) -> State:
    """Debug helper: run one stage on existing state."""
    config.debug = debug
    if stage_name not in STAGES:
        raise ValueError(f"Unknown stage: {stage_name}")
    num, runner = STAGES[stage_name]
    state = runner(state, config)
    console.print()
    console.print(format_summary(state))
    return state
