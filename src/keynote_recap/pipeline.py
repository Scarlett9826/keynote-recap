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


def _collect_quality_failures(state: State) -> list[str]:
    """Inspect verify-stage flags on state; return human-readable failure list.

    Empty list → quality gate passed; non-empty → retry draft once
    (or, after retry, surface as banner warnings on the rendered report).
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
    if not state.structure_check_passed:
        issues.append(
            "5.5.5 structure: missing 核心判断/quotes/tables, or chapter heading malformed"
        )
    return issues


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

        # ─── Quality gate (after stage 5.5 verify): retry draft once if hard-fail ───
        if num == 5.5 and state.draft_retry_count == 0:
            hard_fails = _collect_quality_failures(state)
            if hard_fails:
                console.print(
                    f"\n[bold yellow]⚠ Quality gate failed:[/] "
                    f"{len(hard_fails)} hard issues detected — re-running draft once.\n"
                )
                for issue in hard_fails:
                    console.print(f"   • {issue}")
                state.draft_retry_count = 1
                # Roll back to before stage 5 so draft + verify re-run
                state.last_completed_stage = 4.0
                state.save()
                # Re-run stage 5 (draft) and stage 5.5 (verify) inline
                try:
                    state = STAGES["draft"][1](state, config)
                    state = STAGES["verify"][1](state, config)
                except Exception as e:
                    console.print(f"[bold red]Retry draft/verify failed:[/] {e}")
                    state.save()
                    if debug:
                        raise
                    return state
                # After retry, record any remaining failures as warnings (but proceed)
                still_failing = _collect_quality_failures(state)
                if still_failing:
                    state.quality_passed = False
                    state.final_quality_warnings = still_failing
                    console.print(
                        f"\n[bold yellow]⚠ Retry still failed[/]: "
                        f"{len(still_failing)} issues remain — banner will be added to report.\n"
                    )
                    for issue in still_failing:
                        console.print(f"   • {issue}")
                else:
                    state.quality_passed = True
                    console.print("[green]✓ Quality gate passed after retry[/]\n")
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
