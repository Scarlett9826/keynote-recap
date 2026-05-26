"""CLI entry point for keynote-recap.

Subcommands:
    recap              — run full 7-stage pipeline on a video URL
    recap-and-verify   — recap + verify in one shot (v0.2.5; the canonical
                         agent-facing entry — see AGENTS.md)
    publish-html       — re-render report.md → report.html with sha verify
    verify             — validate any .html / .md as a real keynote-recap output
    config             — print resolved config / generate sample config
    doctor             — preflight only, no pipeline run
    stage              — run individual stage (debug)
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
    "--transcript-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a user-supplied transcript (.srt, .vtt, or .txt). "
         "Use this when yt-dlp cannot fetch subtitles "
         "(Bilibili 412, region locks, private videos). "
         "v0.2.4: stage 1 hard-fails without transcript; this is the "
         "sanctioned escape hatch.",
)
@click.option(
    "--accept-low-yield",
    is_flag=True,
    default=False,
    help="Sanctioned escape for stage 3 hard floors (count < 35 or "
         "useful_ratio < 50%). Use when the source is legitimately "
         "low-info (low-res / cinematic / sparse-text). The report is "
         "still produced, but every artifact carries a 'low-yield-override' "
         "stamp (frontmatter + integrity callout + yellow HTML banner). "
         "v0.3.7. AGENTS.md prohibits editing methodology constants — "
         "use this flag instead.",
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
    llm_all: str | None,
    tier: str | None,
    start_stage: str,
    end_stage: str,
    keep_video: bool,
    checkpoint: bool,
    transcript_file: Path | None,
    accept_low_yield: bool,
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

    cfg = load_config(
        config_path=config,
        llm_override=llm,
        llm_override_all=llm_all,
        keep_video=keep_video,
    )

    if tier is not None:
        cfg.draft.tier = tier

    # v0.3.7 P2: propagate --accept-low-yield to runtime config.
    cfg.accept_low_yield = accept_low_yield

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
    if cfg.accept_low_yield:
        console.print(
            "[yellow]⚠ accept-low-yield: stage 3 hard floors converted to "
            "soft override — report will carry low-yield stamp[/]"
        )
    console.print()

    # Preflight env check (M7 / v0.2.2): catches missing ffmpeg, yt-dlp,
    # API keys, low disk *before* any time is spent downloading.
    env_warnings = _preflight_env(cfg, output_dir)
    if env_warnings is None:  # blocker
        sys.exit(2)

    # Preflight: text-only / unknown vision model is a hard abort (v0.2.4
    # M9.1: --force was removed; no backdoor). To use a custom model,
    # add it to preflight._VERIFIED_VISION_MODELS via PR.
    proceed, model_warnings = _preflight_models(cfg)
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
            transcript_override_path=str(transcript_file) if transcript_file else "",
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
def _preflight_env(cfg, output_dir: Path) -> list[str] | None:
    """Print env check summary; return list of warning strings, or None if blocker.

    Catches missing ffmpeg / yt-dlp / API keys / low disk space so the user
    knows immediately what's wrong rather than crashing 5 minutes in with an
    opaque traceback.

    v0.2.4 (M9.1): blockers are hard-aborted; ``--force`` was removed.

    Returns:
        None  if a blocker is hit (caller should sys.exit).
        list  of warning summaries (may be empty) suitable for persistence into
              ``state.preflight_env_warnings``.
    """
    from . import preflight_env as pe

    api_key_env = cfg.llm.api_key_env
    base_url = cfg.llm.base_url or ""
    checks = pe.run_all_checks(
        output_dir=output_dir, api_key_env=api_key_env, base_url=base_url,
    )

    console.print("[bold]Preflight: environment check[/]")
    for c in checks:
        if c.ok:
            console.print(f"  [green]\u2713[/] {c.what}: [dim]{c.detail}[/]")
        elif c.severity == "blocker":
            console.print(f"  [red]\u2717[/] {c.what}: {c.detail}")
        elif c.what == "api_key":
            # v0.3.5: api_key warning rendered as ℹ blue instead of ⚠ yellow.
            # External agent wrappers (cron drivers, opencode hooks,
            # claude-desktop runners) saw ⚠ + "will fail with 401" and
            # aborted before ever invoking the CLI, even when the SDK
            # could resolve the key from a gateway / keychain / proxy.
            # Severity remains "warning" so state.preflight_env_warnings
            # still records it for the report banner — we just don't
            # shout at the agent from the CLI.
            console.print(f"  [blue]\u2139[/] {c.what}: [dim]{c.detail}[/]")
        else:
            console.print(f"  [yellow]\u26a0[/] {c.what}: {c.detail}")

    blockers = [c for c in checks if (not c.ok) and c.severity == "blocker"]
    if blockers:
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
        return None

    console.print()
    return pe.warning_summaries(checks)


# ──────────────────────────────────────────────────────────────────────────────
# Preflight model-capability check
# ──────────────────────────────────────────────────────────────────────────────
def _preflight_models(cfg) -> tuple[bool, list[str]]:
    """Print a model-capability summary; return (proceed, warnings).

    v0.3.2: ``UNKNOWN`` is downgraded from hard abort to advisory warning.
    Rationale: gateway-prefixed model names (``your-gateway-anthropic/your-vendor/
    claude-opus-4-7`` etc.) and SDK-injected proxy routes generated a
    flood of false-positive aborts in agent-host setups. The substring
    matcher in ``preflight.py`` already recognises real claude/gemini/
    gpt-4o under any prefix; what remains as ``UNKNOWN`` is genuinely
    new model IDs that the user is testing — those should warn, not
    block.

    ``KNOWN_TEXT_ONLY`` remains a hard abort: text-only models on a
    vision stage silently produce garbage and that signal is worth
    preserving (preflight is the only place we catch it).

    Vision stages = ``extract`` (stage 3) + ``verify`` (stage 5.5.2):

    - ``VERIFIED_MULTIMODAL``  → ✓ green, proceed
    - ``KNOWN_TEXT_ONLY``       → ✗ red, hard abort
    - ``UNKNOWN``               → ⚠ yellow, proceed with advisory

    Returns ``(proceed, warnings)``. ``warnings`` is persisted into
    ``state.preflight_model_warnings`` so the final report banner can
    surface "ran with unverified model X" if quality looks off.
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
        else:  # UNKNOWN — advisory only (v0.3.2)
            console.print(
                f"  [yellow]⚠[/] {stage_name}: [cyan]{model_name}[/] — {result.note}"
            )
            has_unknown = True
            warnings.append(f"{stage_name} uses unverified model {model_name}: {result.note}")

    if has_text_only:
        console.print()
        console.print("[bold red]Aborted:[/] one or more vision stages use a "
                      "known text-only model.")
        console.print()
        console.print(VERIFIED_MODELS_DOC)
        console.print()
        console.print(
            "[dim]v0.3.2: gateway-prefixed names like ``mygw/claude-opus-4`` "
            "are now recognised as VERIFIED via substring match. Genuinely "
            "new IDs surface as UNKNOWN and proceed with a warning. "
            "KNOWN_TEXT_ONLY remains a hard abort because text-only "
            "models silent-fail on vision stages.[/]"
        )
        return False, warnings

    if has_unknown:
        console.print()
        console.print("[yellow]Note:[/] one or more stages use an unverified "
                      "model. Proceeding; quality banner will surface this. "
                      "If output looks off, switch to a verified model:")
        console.print(VERIFIED_MODELS_DOC)
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
    console.print(f"  provider: [green]{cfg.llm.provider}[/]")
    console.print(f"  base_url: [dim]{cfg.llm.base_url}[/]")
    console.print(f"  extract:  [cyan]{cfg.llm.models.extract}[/]   [dim](stage 3, needs vision)[/]")
    console.print(f"  research: [cyan]{cfg.llm.models.research}[/]   [dim](stage 4)[/]")
    console.print(f"  draft:    [cyan]{cfg.llm.models.draft}[/]      [dim](stage 5, main writer)[/]")
    console.print(f"  verify:   [cyan]{cfg.llm.models.verify}[/]     [dim](stage 5.5, needs vision)[/]")
    console.print()

    # Run env check against current working dir (doctor doesn't know an
    # output dir; this gives a representative disk-space reading).
    env_warnings = _preflight_env(cfg, Path.cwd())
    env_ok = env_warnings is not None

    proceed, _ = _preflight_models(cfg)

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


# ──────────────────────────────────────────────────────────────────────────────
# `publish-html` — re-render report.md → report.html with sha verification
# ──────────────────────────────────────────────────────────────────────────────
@main.command("publish-html")
@click.argument("report_md", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output HTML path (default: <report_md>.html alongside input).",
)
def publish_html(report_md: Path, output: Path | None) -> None:
    """Re-render a keynote-recap report.md → report.html.

    Verifies the report.md frontmatter content-sha256 matches its body
    before rendering. Refuses to render if the body has been edited
    after keynote-recap wrote it.

    This is the only sanctioned path to produce a fresh HTML from
    report.md. Agents that "summarize" or "rewrite" report.md cannot
    use this command — sha mismatch will abort.

    The rendered HTML carries a stamp (meta tag + bottom-right marker)
    so downstream consumers can verify provenance at a glance.
    """
    from .frontmatter import verify_frontmatter

    text = report_md.read_text()
    ok, msg, meta = verify_frontmatter(text)

    console.print(f"[bold]publish-html[/] {report_md}")
    if not ok:
        console.print(f"  [red]\u2717 verification failed:[/] {msg}")
        console.print()
        if msg == "no frontmatter":
            console.print(
                "  This report.md has no keynote-recap frontmatter. It was "
                "either produced by a pre-v0.2.4 build or written by hand."
            )
            console.print(
                "  [dim]Re-run keynote-recap to produce a properly-signed "
                "report.md, or accept that this file is not an official "
                "keynote-recap output.[/]"
            )
        elif msg == "no content-sha256 in frontmatter":
            console.print(
                "  Frontmatter is present but missing the content-sha256 field. "
                "This file was likely written by hand or with an old version."
            )
        else:
            console.print(
                "  [bold]The report body has been modified after keynote-recap wrote it.[/]"
            )
            console.print(
                "  This is the M9.6 sha-verification gate. It exists to stop "
                "agents from publishing 'compressed' or 'reworded' versions "
                "of the original report and labeling them as keynote-recap "
                "output."
            )
            console.print()
            console.print("  [bold]To proceed, choose one:[/]")
            console.print("    1. Re-run keynote-recap to regenerate a clean report.md")
            console.print("    2. Manually re-compute the sha and write it back to "
                          "frontmatter (NOT recommended — defeats the purpose)")
        sys.exit(2)

    console.print(f"  [green]\u2713[/] sha verified ({meta.get('content-sha256', '')[:12]}…)")
    console.print(f"  [dim]generated by keynote-recap {meta.get('keynote-recap-version', '?')}[/]")

    out_path = output or report_md.with_suffix(".html")

    # Use the existing render pipeline. We need a State with report_md_path.
    # Easiest: reconstruct minimal state from frontmatter + invoke
    # stages.render._render_html(text, out_path, state).
    from .stages.render import render_report_md_to_html

    render_report_md_to_html(report_md, out_path, meta)
    console.print(f"  [green]\u2713 wrote[/] {out_path}")


# ──────────────────────────────────────────────────────────────────────────────
# `verify` — validate a .html / .md as a real keynote-recap output (v0.2.5, L3)
# ──────────────────────────────────────────────────────────────────────────────
@main.command("verify")
@click.argument("path", type=click.Path(exists=False, dir_okay=False, path_type=Path))
def verify_cmd(path: Path) -> None:
    """Validate a file as a genuine, untampered keynote-recap output.

    Auto-detects .html / .md. Prints one summary line and exits:

        exit 0  — OK: keynote-recap v0.2.5 · sha:abc12345 · file=report.html
        exit 1  — FAIL: <specific reason>

    What it checks:

      .html — generator meta, content-sha256 meta, .recap-banner div
              (v0.2.5+), .recap-stamp div (v0.2.4+ redundant defence)
      .md   — frontmatter present, keynote-recap-version field present,
              content-sha256 matches body bytes (tamper detection)

    Use cases:

      1. After running `recap`, verify the output before sharing it.
      2. Before forwarding any HTML/MD claimed to be a keynote-recap
         report, prove it's genuine.
      3. Detect agents that hand-crafted a report and mislabeled it
         as keynote-recap output (the file will fail verify).

    This command never modifies anything; it is a read-only oracle.
    """
    from .verify import verify_file

    result = verify_file(path)
    console.print(result.summary)
    if not result.ok:
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# `recap-and-verify` — single canonical agent-facing entry (v0.2.5, L2.5)
# ──────────────────────────────────────────────────────────────────────────────
@main.command("recap-and-verify", context_settings={"ignore_unknown_options": True})
@click.argument("url", type=str)
@click.argument("recap_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def recap_and_verify(ctx: click.Context, url: str, recap_args: tuple[str, ...]) -> None:
    """Run `recap` and then `verify` on the produced HTML, in one shot.

    This is the canonical command AGENTS.md mandates. It removes
    "produce md, render html, verify them" as three separate agent
    calls (each a chance to drift) and gives a single exit code that
    means "everything is genuinely there".

    Any options passed after URL are forwarded verbatim to `recap`
    (e.g. --output-dir, --transcript-file, --tier, --start-stage).

    Exit codes:

      0  — recap finished AND verify passed on report.html
      1  — recap finished but verify failed (should never happen with
           a valid recap; if it does, file a bug)
      2  — recap itself failed (env / model / pipeline error)
      130 — interrupted by user

    Example:

        keynote-recap recap-and-verify https://www.bilibili.com/video/BV1xxx \\
            --output-dir ./out/acme-launch-2026 --keep-video
    """
    # Step 1: invoke the existing `recap` command via Click's invoke.
    # We pass the URL and forward all extra args. If recap exits non-zero,
    # Click raises SystemExit which we let propagate.
    console.print("[bold cyan]recap-and-verify: step 1/2 — recap[/]")
    console.print()
    try:
        ctx.invoke_recap_args = (url, *recap_args)  # type: ignore[attr-defined]
        # Click's `invoke` with click commands needs us to parse args via
        # the command's own parser. Easiest: re-enter via main_command CLI
        # parsing on a synthetic argv, but that's brittle. Instead, call
        # the underlying callback by reconstructing kwargs from recap's
        # click options. Simplest robust approach: use Click's `invoke`
        # with the parsed params.
        recap_cmd = main.get_command(ctx, "recap")
        assert recap_cmd is not None
        # Parse args through recap's own parser to get a proper params dict
        with recap_cmd.make_context(
            "recap",
            list((url, *recap_args)),
            parent=ctx,
        ) as recap_ctx:
            recap_cmd.invoke(recap_ctx)
    except SystemExit as e:
        # `recap` calls sys.exit on its own error paths; surface that code.
        code = e.code if isinstance(e.code, int) else 2
        if code != 0:
            console.print()
            console.print(f"[bold red]recap-and-verify: recap stage failed (exit {code})[/]")
            sys.exit(code)
        # exit 0 falls through to verify

    # Step 2: locate the produced report.html and verify it.
    console.print()
    console.print("[bold cyan]recap-and-verify: step 2/2 — verify[/]")

    # Determine output dir the same way `recap` does.
    out_dir: Path | None = None
    args_list = list(recap_args)
    for i, tok in enumerate(args_list):
        if tok in ("--output-dir", "-o") and i + 1 < len(args_list):
            out_dir = Path(args_list[i + 1])
            break
        if tok.startswith("--output-dir="):
            out_dir = Path(tok.split("=", 1)[1])
            break
    if out_dir is None:
        from .util import slugify_url
        out_dir = Path("runs") / slugify_url(url)

    html_path = out_dir / "report.html"
    if not html_path.exists():
        console.print(
            f"[bold red]recap-and-verify failed:[/] expected {html_path} but it "
            "does not exist. The recap stage reported success but produced no "
            "HTML — file a bug at "
            "https://github.com/Scarlett9826/keynote-recap"
        )
        sys.exit(1)

    from .verify import verify_file
    result = verify_file(html_path)
    console.print(result.summary)
    if not result.ok:
        console.print()
        console.print(
            "[bold red]recap-and-verify failed:[/] recap exited 0 but verify "
            "rejected the produced HTML. This indicates a bug — file at "
            "https://github.com/Scarlett9826/keynote-recap"
        )
        sys.exit(1)

    console.print()
    console.print(f"[bold green]✓ recap-and-verify done[/] — {html_path}")


if __name__ == "__main__":
    main()
