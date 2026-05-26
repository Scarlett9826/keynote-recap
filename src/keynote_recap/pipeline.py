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
from rich.panel import Panel
from rich.prompt import Confirm

from . import methodology as M
from .config import Config
from .cost_tracker import format_summary
from .preflight import ModelTier, check_model_capability
from .stages import download, draft, extract, render, research, segment, verify
from .stages.extract import ExtractFloorError
from .state import State

console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Stage banner (M7 / v0.2.2)
# ──────────────────────────────────────────────────────────────────────────────
# What model each stage uses, what task it does, and what guards apply.
# Surfaced as a console panel before the stage runs so users see in real time
# how the project's design maps onto the actual run.
_STAGE_INFO: dict[str, dict[str, str]] = {
    "download": {
        "model_attr": "",
        "task": "fetch video + subtitles via yt-dlp",
        "guards": "—",
    },
    "segment": {
        "model_attr": "",
        "task": "ffmpeg sample frames + frame_scorer initial filter",
        "guards": "12-chunk floor (>= 3 per chunk)",
    },
    "extract": {
        "model_attr": "extract",
        "task": "vision LLM 3-principle filter (info / relevance / dedup)",
        "guards": "5.5.6 useful ratio >= 70%, 5.5.7 topic coverage (v0.3.6 F5)",
    },
    "research": {
        "model_attr": "research",
        "task": "extract facts + verify via web search",
        "guards": "verified-source allowlist",
    },
    "draft": {
        "model_attr": "draft",
        "task": "outline + body + callout + bucket-constrained image placement",
        "guards": "5.5.0/1/3/4b/5 hard gates",
    },
    "verify": {
        "model_attr": "verify",
        "task": "vision-LLM caption verify + anti-AI lint",
        "guards": "all 5.5.x; failure -> retry tier 1 or 2",
    },
    "render": {
        "model_attr": "",
        "task": "markdown -> self-contained HTML",
        "guards": "tri-color quality banner + responsibility section",
    },
}


def _print_stage_banner(stage_name: str, num: float, config: Config, state: State) -> None:
    """Print a 4-line panel showing model / task / guards before each stage.

    Helps users realize *during* the run that, e.g., stage 3 is using their
    custom model, not the project's recommended one.
    """
    info = _STAGE_INFO.get(stage_name, {})
    model_attr = info.get("model_attr", "")
    task = info.get("task", "")
    guards = info.get("guards", "—")

    if model_attr:
        model_name = getattr(config.llm.models, model_attr, "")
        check = check_model_capability(model_name)
        if check.tier == ModelTier.VERIFIED_MULTIMODAL:
            tier_label = "[green]verified multimodal[/]"
        elif check.tier == ModelTier.KNOWN_TEXT_ONLY:
            tier_label = "[red]known text-only[/]"
        else:
            tier_label = "[yellow]unverified[/]"
        # Persist for later report rendering.
        state.models_used[stage_name] = model_name
        state.model_tiers[stage_name] = check.tier.value
        model_line = f"model:  [cyan]{model_name}[/]  ({tier_label})"

        # v0.2.3: project-controlled agent parallelism. Inferred from model
        # tier; user cannot override. Shows in banner so users see what
        # decision the project made for them.
        parallel = M.parallel_for_stage(stage_name, check.tier.value)
        if stage_name in M.AGENT_PARALLEL_ELIGIBLE_STAGES:
            if parallel > 1:
                parallel_line = f"\nagent:  parallel {parallel} (auto — verified model)"
            else:
                parallel_line = (
                    f"\nagent:  sequential (model tier '{check.tier.value}' "
                    f"not eligible for parallelism)"
                )
        else:
            parallel_line = ""
    else:
        model_line = "model:  [dim](no LLM call)[/]"
        parallel_line = ""

    body = f"{model_line}{parallel_line}\ntask:   {task}\nguards: {guards}"
    console.print(Panel(body, title=f"stage {num} / {stage_name}", expand=False))


# ──────────────────────────────────────────────────────────────────────────────
# Runtime capability probes (M7 / v0.2.2)
# ──────────────────────────────────────────────────────────────────────────────
def _probe_extract_output(state: State) -> str | None:
    """If stage 3 selected very few frames, the vision model is probably weak.

    Returns a warning string, or None if output looks healthy.
    """
    n = len(state.selected_frames)
    if n < 5:
        return (
            f"stage 3 only produced {n} frames (< 5). Vision model "
            f"'{state.models_used.get('extract', '?')}' may have weak image "
            f"understanding; report image quality may suffer."
        )
    return None


def _probe_research_output(state: State) -> str | None:
    """If research returned zero verified facts but had things to verify, the
    research model probably doesn't support web tools / the search is misconfigured.
    """
    if state.facts_to_verify and not state.verified_facts:
        return (
            f"stage 4 had {len(state.facts_to_verify)} facts to verify but "
            f"verified 0. Model '{state.models_used.get('research', '?')}' may "
            f"not support web tools, or the search provider is misconfigured."
        )
    return None


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
    if not state.image_section_fit_passed:
        issues.append(
            f"5.5.4 image-section fit: {state.image_section_fit_mismatch_count} "
            f"images likely placed in wrong section (heuristic: caption tokens "
            f"don't appear in section title or body); LLM picked semantically "
            f"unrelated chapter for these frames"
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
            "5.5.6 image mix: total frames < 35 or useful ratio < 50% "
            "(too many low-info frames: empty screens / transitions / noise)"
        )
    if not state.topic_coverage_passed:
        issues.append(
            "5.5.7 topic coverage: a high-frequency topic in the transcript "
            "has zero associated frames (vision LLM was too aggressive)"
        )
    if not state.per_section_floor_passed:
        issues.append(
            "5.5.1b per-section floor: a chapter has 0 images, OR a mainline "
            "chapter has < 4 images (frame distribution uneven; retry stage 3)"
        )
    if state.caption_verify_wrong_count > M.EXTRACT_CAPTION_VERIFY_WRONG_MAX:
        issues.append(
            f"5.5.2 caption verify: {state.caption_verify_wrong_count} wrong "
            f"captions (> tolerance {M.EXTRACT_CAPTION_VERIFY_WRONG_MAX}); "
            f"vision LLM misidentified frames; retry stage 3 with stricter "
            f"caption-fidelity directive"
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
    preflight_env_warnings: list[str] | None = None,
    preflight_model_warnings: list[str] | None = None,
    transcript_override_path: str = "",
) -> State:
    """Run pipeline from start_stage to end_stage (inclusive)."""
    config.debug = debug

    state_path = output_dir / "state.json"
    if state_path.exists() and start_stage > 1.0:
        state = State.load(state_path)
        console.print(f"[dim]Resumed from {state_path} (last completed: stage {state.last_completed_stage})[/]\n")
    else:
        state = State.new(url=url, output_dir=output_dir)

    # v0.2.4 (M9.2): user-supplied transcript path
    if transcript_override_path:
        state.transcript_override_path = transcript_override_path

    # Persist preflight warnings (M7) so the final report can surface them.
    if preflight_env_warnings:
        state.preflight_env_warnings = list(preflight_env_warnings)
    if preflight_model_warnings:
        state.preflight_model_warnings = list(preflight_model_warnings)

    for name, (num, runner) in STAGES.items():
        if num < start_stage or num > end_stage:
            continue
        if num <= state.last_completed_stage and start_stage <= state.last_completed_stage:
            console.print(f"[dim]Skipping stage {num} ({name}) — already done[/]")
            continue

        _print_stage_banner(name, num, config, state)

        try:
            state = runner(state, config)
        except ExtractFloorError as e:
            # p14: stage-3 hard-floor breach. Source comments claim "caught by
            # pipeline retry orchestration" but pre-p14 nothing actually caught
            # this — it crashed the whole pipeline. Honour the contract: retry
            # stage 3 once with floor breach injected as retry_context, then if
            # it still fails, mark image_mix_passed=False and stop (don't
            # crash; downstream stages can't proceed without selected_frames).
            if name != "extract" or state.extract_retry_count > 0:
                # Not extract, or already retried — fall through to generic.
                raise
            console.print(
                f"\n[bold yellow]⚠ Stage 3 floor breach:[/] {e}\n"
                f"   Retrying stage 3 once with breach details injected.\n"
            )
            state.extract_retry_count = 1
            state.save()
            try:
                state = runner(state, config, retry_context=[str(e)])
            except ExtractFloorError as e2:
                console.print(
                    f"[bold red]Stage 3 retry also failed:[/] {e2}\n"
                    f"   Marking image_mix_passed=False; pipeline stops here "
                    f"(downstream stages need selected_frames)."
                )
                state.image_mix_passed = False
                if num not in state.stages_skipped:
                    state.stages_skipped.append(num)
                state.stages_skip_reasons["3"] = f"ExtractFloorError: {e2}"
                state.save()
                if debug:
                    raise
                return state
        except Exception as e:
            console.print(f"[bold red]Stage {num} ({name}) failed:[/] {e}")
            # v0.2.4 (M9.4): record this stage as skipped so frontmatter +
            # integrity callout reflect reality.
            if num not in state.stages_skipped:
                state.stages_skipped.append(num)
            # Use short stage label ("1" / "5.5") matching _fmt_stage in draft.py
            stage_key = str(int(num)) if num == int(num) else str(num)
            state.stages_skip_reasons[stage_key] = f"{type(e).__name__}: {e}"
            state.save()
            if debug:
                raise
            return state

        # v0.2.4 (M9.4): track which stages actually ran successfully.
        if num not in state.stages_completed:
            state.stages_completed.append(num)

        # ─── Runtime capability probes (M7) ───
        # Detect "model technically ran but produced suspiciously thin output"
        # and surface it as a runtime warning so users don't blame the project.
        if name == "extract":
            warn = _probe_extract_output(state)
            if warn:
                console.print(f"[yellow]\u26a0 runtime probe:[/] {warn}")
                state.runtime_warnings.append(warn)
        elif name == "research":
            warn = _probe_research_output(state)
            if warn:
                console.print(f"[yellow]\u26a0 runtime probe:[/] {warn}")
                state.runtime_warnings.append(warn)

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
                    # v0.3.1 C3: feed prior failures to extract so it can target them
                    state = extract.run(state, config, retry_context=extract_fails)
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
                # v0.3.1 C4: re-collect after stage 3 retry — extract gates may
                # now pass even if draft gates still fail; the Tier-2 draft retry
                # block below will pick up only the still-failing draft issues.

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

        # Checkpoint pause (M.PIPELINE_CHECKPOINTS — methodology-locked)
        if checkpoint and num in M.PIPELINE_CHECKPOINTS and num < end_stage:
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
