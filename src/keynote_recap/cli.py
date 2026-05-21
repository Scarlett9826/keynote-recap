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
    help="Override default LLM model (e.g. claude-opus-4 / gpt-4o).",
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
def recap(
    url: str,
    output_dir: Path | None,
    config: Path | None,
    llm: str | None,
    start_stage: str,
    end_stage: str,
    keep_video: bool,
    checkpoint: bool,
    debug: bool,
) -> None:
    """Run full 7-stage pipeline on a video URL.

    Example:

        keynote-recap recap https://www.youtube.com/watch?v=wYSncx9zLIU \\
            --output-dir ./io26 --keep-video
    """
    # Lazy import to keep CLI fast
    from .config import load_config
    from .pipeline import run_pipeline

    cfg = load_config(config_path=config, llm_override=llm, keep_video=keep_video)

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
