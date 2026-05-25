"""CLI entry point for keynote-recap.

Subcommands:
    recap   — run full 7-stage pipeline on a video URL
    config  — print resolved config / generate sample config
    stage   — run individual stage (debug)
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.traceback import install as rich_traceback_install

from . import __version__

rich_traceback_install(show_locals=False)
console = Console()


@click.group()
@click.version_option(__version__, prog_name="keynote-recap")
def main() -> None:
    """keynote-recap — turn keynote videos into illustrated Chinese recap reports."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# `recap` — full pipeline
# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.argument("url", type=str)
@click.option(
    "--output-dir", "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory (default: ./runs/<slug>).",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Config file path (default: ~/.config/keynote-recap/config.yaml).",
)
@click.option(
    "--llm",
    type=str,
    default=None,
    help="Override the draft (stage 5) model only. Use --llm-all to set all stages.",
)
@click.option(
    "--llm-all",
    type=str,
    default=None,
    help="Override ALL LLM stages (extract/research/draft/verify) with one model. "
         "Use this if your gateway only supports a single model. "
         "Same as KEYNOTE_RECAP_MODEL_ALL env var.",
)
@click.option(
    "--tier",
    type=click.Choice(["easy", "standard", "strict"]),
    default=None,
    help="Draft prompt tier (default: strict — methodology rules are hard "
         "contract: forbidden phrases, ≥ 8 citations, every chapter has "
         "核心判断). Pass 'easy' for medium-capability multimodal models "
         "(gemini-2.5-flash, qwen-vl-max); 'standard' for "
         "claude-sonnet-4 / gpt-4o.",
)
@click.option(
    "--start-stage",
    type=click.Choice(["1", "2", "3", "4", "5", "5.5", "6", "7"]),
    default="1",
    help="Pipeline start stage.",
)
@click.option(
    "--end-stage",
    type=click.Choice(["1", "2", "3", "4", "5", "5.5", "6", "7"]),
    default="6",
    help="Pipeline end stage (inclusive).",
)
@click.option(
    "--keep-video/--delete-video",
    default=True,
    help="Keep downloaded video file (default: keep, allows zero-cost rerun).",
)
@click.option(
    "--checkpoint/--no-checkpoint",
    default=True,
    help="Pause for human review at checkpoints (after stage 3, 4, 5.5).",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip preflight model-capability check and run anyway.",
)
def recap(
    url: str,
    output_dir: Path | None,
    config: Path | None,
    llm: str | None,
    llm_all: str | None,
    tier: str | None,
    start_stage: str,
    end_stage: str,
    keep_video: bool,
    checkpoint: bool,
    debug: bool,
    force: bool,
) -> None:
    """Run full 7-stage pipeline on a video URL.

    Example:

        keynote-recap recap https://www.youtube.com/watch?v=wYSncx9zLIU \\
            --output-dir ./io26 --keep-video
    """
    # Lazy import to keep CLI fast
    from .config import load_config
    from .pipeline import run_pipeline

    cfg = load_config(
        config_path=config,
        llm_override=llm,
        llm_override_all=llm_all,
        keep_video=keep_video,
    )

    if tier is not None:
        cfg.draft.tier = tier

    if output_dir is None:
        from .util import slugify_url
        output_dir = Path("runs") / slugify_url(url)

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]keynote-recap v{__version__}[/]")
    console.print(f"[dim]URL:        {url}[/]")
    console.print(f"[dim]Output:     {output_dir}[/]")
    console.print(f"[dim]LLM:        {cfg.llm.models.draft}[/]")
    console.print(f"[dim]Draft tier: {cfg.draft.tier}[/]")
    console.print(f"[dim]Stages:     {start_stage} → {end_stage}[/]")
    console.print()

    # Preflight env check (M7 / v0.2.2): catches missing ffmpeg, yt-dlp,
    # API keys, low disk *before* any time is spent downloading.
    env_warnings = _preflight_env(cfg, output_dir, force=force)
    if env_warnings is None:  # blocker
        sys.exit(2)

    # Preflight: warn / abort if model is known text-only or unverified.
    proceed, model_warnings = _preflight_models(cfg, force=force)
    if not proceed:
        sys.exit(2)

    try:
        run_pipeline(
            url=url,
            output_dir=output_dir,
            config=cfg,
            start_stage=float(start_stage),
            end_stage=float(end_stage),
            checkpoint=checkpoint,
            debug=debug,
            preflight_env_warnings=env_warnings,
            preflight_model_warnings=model_warnings,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        if debug:
            raise
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Preflight environment check (M7 / v0.2.2)
# ──────────────────────────────────────────────────────────────────────────────
def _preflight_env(cfg, output_dir: Path, force: bool = False) -> list[str] | None:
    """Print env check summary; return list of warning strings, or None if blocker.

    Catches missing ffmpeg / yt-dlp / API keys / low disk space so the user
    knows immediately what's wrong rather than crashing 5 minutes in with an
    opaque traceback.

    Returns:
        None  if a blocker is hit and ``force`` is False (caller should sys.exit).
        list  of warning summaries (may be empty) suitable for persistence into
              ``state.preflight_env_warnings``.
    """
    from . import preflight_env as pe

    api_key_env = cfg.llm.api_key_env
    checks = pe.run_all_checks(output_dir=output_dir, api_key_env=api_key_env)

    console.print("[bold]Preflight: environment check[/]")
    for c in checks:
        if c.ok:
            console.print(f"  [green]\u2713[/] {c.what}: [dim]{c.detail}[/]")
        elif c.severity == "blocker":
            console.print(f"  [red]\u2717[/] {c.what}: {c.detail}")
        else:
            console.print(f"  [yellow]\u26a0[/] {c.what}: {c.detail}")

    blockers = [c for c in checks if (not c.ok) and c.severity == "blocker"]
    if blockers and not force:
        console.print()
        console.print("[bold red]Aborted:[/] one or more required tools / settings "
                      "are missing. Fix and retry:")
        for c in blockers:
            console.print()
            console.print(f"  [bold]{c.what}[/] — {c.detail}")
            if c.fix:
                for line in c.fix.splitlines():
                    console.print(f"    [cyan]{line}[/]")
        console.print()
        console.print("[dim]Override with[/] [cyan]--force[/] [dim]if you really "
                      "want to try anyway (the run will likely crash).[/]")
        return None

    if blockers and force:
        console.print()
        console.print("[yellow]\u26a0 --force set; continuing despite missing tools.[/] "
                      "Expect a hard crash on the affected stage.")

    console.print()
    return pe.warning_summaries(checks)


# ──────────────────────────────────────────────────────────────────────────────
# Preflight model-capability check
# ──────────────────────────────────────────────────────────────────────────────
def _preflight_models(cfg, force: bool = False) -> tuple[bool, list[str]]:
    """Print a model-capability summary; return (proceed, warnings).

    The two stages that require vision are ``extract`` (stage 3) and
    ``verify`` (stage 5.5.2). For each:

    - ``VERIFIED_MULTIMODAL``  → ✓ green, proceed silently
    - ``KNOWN_TEXT_ONLY``       → ✗ red, abort unless ``--force``
    - ``UNKNOWN``               → ⚠ yellow, abort unless ``--force``
                                  (M7 / v0.2.2 — was soft-warn previously;
                                  too many silent-quality-loss reports)

    Returns:
        (proceed, warnings) where ``warnings`` is a list of strings that
        will be persisted into ``state.preflight_model_warnings`` so the
        final report can surface them in the quality banner.
    """
    from .preflight import ModelTier, VERIFIED_MODELS_DOC, check_model_capability

    # Stages that strictly need a multimodal model
    vision_stages = {
        "extract (stage 3 frame filter)": cfg.llm.models.extract,
        "verify (stage 5.5.2 caption verify)": cfg.llm.models.verify,
    }

    console.print("[bold]Preflight: model capability check[/]")
    has_text_only = False
    has_unknown = False
    warnings: list[str] = []
    for stage_name, model_name in vision_stages.items():
        result = check_model_capability(model_name)
        if result.tier == ModelTier.VERIFIED_MULTIMODAL:
            console.print(f"  [green]✓[/] {stage_name}: [cyan]{model_name}[/] — {result.note}")
        elif result.tier == ModelTier.KNOWN_TEXT_ONLY:
            console.print(
                f"  [red]✗[/] {stage_name}: [cyan]{model_name}[/] — {result.note}"
            )
            has_text_only = True
            warnings.append(f"{stage_name} uses known text-only model {model_name}: {result.note}")
        else:  # UNKNOWN
            console.print(
                f"  [yellow]⚠[/] {stage_name}: [cyan]{model_name}[/] — {result.note}"
            )
            has_unknown = True
            warnings.append(f"{stage_name} uses unverified model {model_name}: {result.note}")

    blocked = has_text_only or has_unknown

    if blocked and not force:
        console.print()
        if has_text_only:
            console.print("[bold red]Aborted:[/] one or more vision stages use a "
                          "known text-only model.")
        else:
            console.print("[bold yellow]Aborted:[/] one or more vision stages use a "
                          "model not on the verified-multimodal list.")
        console.print()
        console.print(VERIFIED_MODELS_DOC)
        console.print()
        console.print("[dim]Override with[/] [cyan]--force[/] [dim]to run anyway. "
                      "If the model lacks image support the prompt-level capability probe "
                      "will abort the run with a clear error; if it has weak image support "
                      "the run will complete but the report will carry a yellow quality "
                      "banner so readers know not to blame the project for the output.[/]")
        return False, warnings

    if blocked and force:
        console.print()
        if has_text_only:
            console.print(
                "[yellow]\u26a0 --force set; continuing despite text-only model.[/] "
                "Stage 3 / 5.5.2 will likely fail at the prompt-level capability probe."
            )
        else:
            console.print(
                "[yellow]\u26a0 --force set; continuing with unverified vision model.[/] "
                "The final report will carry a quality banner indicating the model "
                "is not on the verified list."
            )

    console.print()
    return True, warnings


# ──────────────────────────────────────────────────────────────────────────────
# `config` — config inspection & generation
# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option(
    "--init",
    is_flag=True,
    help="Write a sample config to ~/.config/keynote-recap/config.yaml.",
)
def config(init: bool) -> None:
    """Print resolved config or generate sample config."""
    from .config import default_config_path, load_config, write_sample_config

    if init:
        path = default_config_path()
        if path.exists():
            console.print(f"[yellow]Already exists:[/] {path}")
            sys.exit(1)
        write_sample_config(path)
        console.print(f"[green]Wrote sample config:[/] {path}")
        return

    cfg = load_config()
    console.print_json(cfg.model_dump_json(indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# `doctor` — preflight only, no pipeline run
# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Config file path (default: ~/.config/keynote-recap/config.yaml).",
)
@click.option(
    "--llm",
    type=str,
    default=None,
    help="Override the draft model to test against.",
)
@click.option(
    "--llm-all",
    type=str,
    default=None,
    help="Override ALL LLM stages with one model (e.g. test if your gateway model works).",
)
def doctor(config: Path | None, llm: str | None, llm_all: str | None) -> None:
    """Check current config for known model-compatibility issues.

    Run this before starting a long pipeline to catch bad model choices early.
    Exits non-zero if a known text-only model is configured for a vision stage.
    """
    from .config import load_config
    from .preflight import VERIFIED_MODELS_DOC

    cfg = load_config(config_path=config, llm_override=llm, llm_override_all=llm_all)

    console.print(f"[bold cyan]keynote-recap doctor v{__version__}[/]")
    console.print()
    console.print("[bold]Resolved per-stage models:[/]")
    console.print(f"  extract:  [cyan]{cfg.llm.models.extract}[/]   [dim](stage 3, needs vision)[/]")
    console.print(f"  research: [cyan]{cfg.llm.models.research}[/]   [dim](stage 4)[/]")
    console.print(f"  draft:    [cyan]{cfg.llm.models.draft}[/]      [dim](stage 5, main writer)[/]")
    console.print(f"  verify:   [cyan]{cfg.llm.models.verify}[/]     [dim](stage 5.5, needs vision)[/]")
    console.print()

    # Run env check against current working dir (doctor doesn't know an
    # output dir; this gives a representative disk-space reading).
    env_warnings = _preflight_env(cfg, Path.cwd(), force=False)
    env_ok = env_warnings is not None

    proceed, _ = _preflight_models(cfg, force=False)

    if env_ok and proceed:
        console.print("[green]All preflight checks passed.[/]")
        console.print()
        console.print("[dim]Reference list (verified models):[/]")
        console.print(VERIFIED_MODELS_DOC)
    else:
        sys.exit(2)


# ──────────────────────────────────────────────────────────────────────────────
# `stage` — run single stage (debug)
# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.argument(
    "stage_name",
    type=click.Choice([
        "download", "segment", "extract", "research",
        "draft", "verify", "render",
    ]),
)
@click.option(
    "--state",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to state.json from a previous run.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging.",
)
def stage(stage_name: str, state: Path, debug: bool) -> None:
    """Run a single stage on existing state (debug helper)."""
    from .config import load_config
    from .pipeline import run_single_stage
    from .state import State

    cfg = load_config()
    s = State.load(state)

    console.print(f"[bold cyan]Running stage:[/] {stage_name}")
    run_single_stage(stage_name, state=s, config=cfg, debug=debug)


if __name__ == "__main__":
    main()
