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

    if output_dir is None:
        from .util import slugify_url
        output_dir = Path("runs") / slugify_url(url)

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]keynote-recap v{__version__}[/]")
    console.print(f"[dim]URL:        {url}[/]")
    console.print(f"[dim]Output:     {output_dir}[/]")
    console.print(f"[dim]LLM:        {cfg.llm.models.draft}[/]")
    console.print(f"[dim]Stages:     {start_stage} → {end_stage}[/]")
    console.print()

    # Preflight: warn / abort if model is known text-only.
    # Checks the most-used model; per-stage overrides may still differ.
    if not _preflight_models(cfg, force=force):
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
# Preflight model-capability check
# ──────────────────────────────────────────────────────────────────────────────
def _preflight_models(cfg, force: bool = False) -> bool:
    """Print a model-capability summary; return False to abort if user picked
    a model the project knows will silent-fail on vision stages.

    The two stages that require vision are ``extract`` (stage 3) and
    ``verify`` (stage 5.5.2). We check both; if either is known-text-only
    we abort unless ``--force`` is set.

    Returns:
        True if pipeline should continue, False if user must fix config first.
    """
    from .preflight import ModelTier, VERIFIED_MODELS_DOC, check_model_capability

    # Stages that strictly need a multimodal model
    vision_stages = {
        "extract (stage 3 frame filter)": cfg.llm.models.extract,
        "verify (stage 5.5.2 caption verify)": cfg.llm.models.verify,
    }

    console.print("[bold]Preflight: model capability check[/]")
    has_blocker = False
    has_unknown = False
    for stage_name, model_name in vision_stages.items():
        result = check_model_capability(model_name)
        if result.tier == ModelTier.VERIFIED_MULTIMODAL:
            console.print(f"  [green]✓[/] {stage_name}: [cyan]{model_name}[/] — {result.note}")
        elif result.tier == ModelTier.KNOWN_TEXT_ONLY:
            console.print(
                f"  [red]✗[/] {stage_name}: [cyan]{model_name}[/] — {result.note}"
            )
            has_blocker = True
        else:  # UNKNOWN
            console.print(
                f"  [yellow]⚠[/] {stage_name}: [cyan]{model_name}[/] — {result.note}"
            )
            has_unknown = True

    if has_blocker and not force:
        console.print()
        console.print("[bold red]Aborted:[/] one or more vision stages use a "
                      "known text-only model.")
        console.print()
        console.print(VERIFIED_MODELS_DOC)
        console.print()
        console.print("[dim]Override with[/] [cyan]--force[/] [dim]if you really want to "
                      "try (the prompt-level capability probe will still abort the run "
                      "when the model fails to see images).[/]")
        return False

    if has_blocker and force:
        console.print()
        console.print("[yellow]⚠ --force set; continuing despite text-only model.[/] "
                      "Stage 3 / 5.5.2 will likely fail at the prompt-level capability probe.")

    if has_unknown:
        console.print()
        console.print("[dim]Some models are not on the verified list. If they support "
                      "image input the run will succeed; otherwise the prompt-level "
                      "capability probe will abort with a clear error.[/]")

    console.print()
    return True


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

    ok = _preflight_models(cfg, force=False)

    if ok:
        console.print("[green]All vision-required stages have a workable model.[/]")
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
