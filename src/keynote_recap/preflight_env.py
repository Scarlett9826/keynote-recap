"""Preflight environment check (M7 / v0.2.2).

Catches all the "user's machine doesn't actually have what we need" failures
*before* we spend 2 minutes downloading a 2GB video, then crash on stage 2
with an opaque ``FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'``.

Each check returns an :class:`EnvCheck` carrying:

  - ``ok``            — pass / fail
  - ``what``          — short human label (e.g. ``"ffmpeg"``)
  - ``detail``        — one-line failure detail (or success note)
  - ``fix``           — copy-pastable shell command to remediate (None if ok)
  - ``severity``      — ``"blocker"`` (must fix) | ``"warning"`` (advisory)

A blocker fails the run. A warning is surfaced both on the CLI and in the
final report's quality banner.

The checks intentionally do NOT call any LLM endpoint or burn a token to
validate API keys: we only check that the env var is *set*. Real validation
happens implicitly on the first stage-3 call.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class EnvCheck:
    """Single environment-check result."""

    ok: bool
    what: str
    detail: str
    fix: str | None = None
    severity: Literal["blocker", "warning"] = "blocker"


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────
_INSTALL_HINT_FFMPEG = (
    "macOS:   brew install ffmpeg\n"
    "Ubuntu:  sudo apt-get install -y ffmpeg\n"
    "Windows: choco install ffmpeg  (or download from ffmpeg.org)"
)

_INSTALL_HINT_YTDLP = (
    "pip install -U yt-dlp\n"
    "(or: brew install yt-dlp / pipx install yt-dlp)"
)


def check_python_version() -> EnvCheck:
    """Project requires Python 3.10+."""
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        return EnvCheck(
            ok=True,
            what="python",
            detail=f"Python {major}.{minor} (>= 3.10 required)",
        )
    return EnvCheck(
        ok=False,
        what="python",
        detail=f"Python {major}.{minor} found; project requires >= 3.10",
        fix="Install Python 3.10+ via pyenv / homebrew / official installer.",
        severity="blocker",
    )


def _which_with_version(binary: str, version_flag: str = "-version") -> str | None:
    """Return one-line version string, or None if binary missing / unrunnable."""
    if shutil.which(binary) is None:
        return None
    try:
        r = subprocess.run(
            [binary, version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else ""
        return first_line.strip() or "(version unknown)"
    except (subprocess.TimeoutExpired, OSError, IndexError):
        return "(version probe failed)"


def check_ffmpeg() -> EnvCheck:
    """ffmpeg is required by stages 1 (download fallback) and 2 (frame sample)."""
    ver = _which_with_version("ffmpeg", "-version")
    if ver is None:
        return EnvCheck(
            ok=False,
            what="ffmpeg",
            detail="ffmpeg not found on PATH — stage 2 (frame sampling) will crash.",
            fix=_INSTALL_HINT_FFMPEG,
            severity="blocker",
        )
    return EnvCheck(ok=True, what="ffmpeg", detail=ver)


def check_ffprobe() -> EnvCheck:
    """ffprobe is bundled with ffmpeg but verify separately to give a clear error."""
    ver = _which_with_version("ffprobe", "-version")
    if ver is None:
        return EnvCheck(
            ok=False,
            what="ffprobe",
            detail="ffprobe not found on PATH (usually shipped with ffmpeg).",
            fix=_INSTALL_HINT_FFMPEG,
            severity="blocker",
        )
    return EnvCheck(ok=True, what="ffprobe", detail=ver)


def check_yt_dlp() -> EnvCheck:
    """yt-dlp is required for stage 1 (download).

    Older yt-dlp versions break frequently against YouTube; warn if too old.
    """
    if shutil.which("yt-dlp") is None:
        # yt-dlp may also be installed as Python module; check that too.
        try:
            import yt_dlp  # noqa: F401
            return EnvCheck(
                ok=True,
                what="yt-dlp",
                detail=f"yt-dlp Python module {getattr(__import__('yt_dlp'), '__version__', 'unknown')}",
            )
        except ImportError:
            return EnvCheck(
                ok=False,
                what="yt-dlp",
                detail="yt-dlp not found on PATH and not installed as Python module.",
                fix=_INSTALL_HINT_YTDLP,
                severity="blocker",
            )

    ver = _which_with_version("yt-dlp", "--version")
    return EnvCheck(ok=True, what="yt-dlp", detail=f"yt-dlp {ver}")


def check_disk_space(output_dir: Path, required_gb: float = 5.0) -> EnvCheck:
    """A 60-min 1080p video can be 2-3 GB; intermediate frames add 0.5-1 GB.

    Warn (not block) if free space < required_gb.
    """
    target = output_dir if output_dir.exists() else output_dir.parent
    while not target.exists() and target != target.parent:
        target = target.parent

    try:
        free_bytes = shutil.disk_usage(target).free
    except OSError as e:
        return EnvCheck(
            ok=False,
            what="disk",
            detail=f"Could not check disk space at {target}: {e}",
            severity="warning",
        )

    free_gb = free_bytes / (1024 ** 3)
    if free_gb < required_gb:
        return EnvCheck(
            ok=False,
            what="disk",
            detail=(
                f"Only {free_gb:.1f} GB free at {target} "
                f"(recommend >= {required_gb:.0f} GB for video + frames + outputs)."
            ),
            fix="Free up space, or pass --output-dir pointing at a larger volume.",
            severity="warning",
        )
    return EnvCheck(ok=True, what="disk", detail=f"{free_gb:.1f} GB free at {target}")


def check_api_key(env_var_name: str) -> EnvCheck:
    """Verify the configured LLM API key env var is set (NOT that it's valid).

    Real validity check happens on first LLM call; doing it here would burn
    tokens and slow down every run.

    v0.2.5.1 hotfix: severity is ``warning``, not ``blocker``. v0.2.5
    silently upgraded this to ``blocker`` (un-declared BREAKING) which broke
    workflows where the LLM endpoint is reached via a non-standard env var
    (corporate gateways, agent-host injected proxies, etc.). The proper
    place for "the key is actually wrong" is the first LLM call — it
    surfaces a 401 there with a clear provider message. Pre-flighting only
    catches "the variable is literally unset", which is advisory-grade.
    """
    val = os.environ.get(env_var_name, "").strip()
    if not val:
        return EnvCheck(
            ok=False,
            what="api_key",
            detail=f"${env_var_name} is not set — LLM stages will fail "
                   "with 401 unless the SDK reads the key from another "
                   "source (e.g. an agent-host proxy).",
            fix=f"export {env_var_name}=<your-api-key>",
            severity="warning",
        )
    # Light sanity: most keys are >= 20 chars
    if len(val) < 20:
        return EnvCheck(
            ok=False,
            what="api_key",
            detail=f"${env_var_name} is set but suspiciously short ({len(val)} chars).",
            fix=f"Verify the value of {env_var_name}.",
            severity="warning",
        )
    return EnvCheck(
        ok=True,
        what="api_key",
        detail=f"${env_var_name} is set ({len(val)} chars).",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Aggregate
# ──────────────────────────────────────────────────────────────────────────────
def run_all_checks(output_dir: Path, api_key_env: str) -> list[EnvCheck]:
    """Run every preflight env check; caller decides what to do with results."""
    return [
        check_python_version(),
        check_ffmpeg(),
        check_ffprobe(),
        check_yt_dlp(),
        check_disk_space(output_dir),
        check_api_key(api_key_env),
    ]


def has_blocker(checks: list[EnvCheck]) -> bool:
    return any((not c.ok) and c.severity == "blocker" for c in checks)


def warning_summaries(checks: list[EnvCheck]) -> list[str]:
    """Returns human-readable strings for non-blocker failures.

    Used to populate ``state.preflight_env_warnings`` so the final report can
    surface them in the quality banner.
    """
    return [
        f"{c.what}: {c.detail}"
        for c in checks
        if (not c.ok) and c.severity == "warning"
    ]
