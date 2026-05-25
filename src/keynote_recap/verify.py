"""Validation channel for keynote-recap outputs (v0.2.5, L3).

This module provides the pure-function backbone for ``keynote-recap
verify <file>``. Given an HTML or Markdown file produced by the
project, it answers a single question: *is this still a real
keynote-recap output, untampered with?*

It is the **validation channel** in the v0.2.5 internalized-defense
design (see ``docs/plans/2026-05-25-internalized-defense-design.md``,
section "L3"). Where the L2 banner makes a hand-crafted impostor look
visually wrong to humans, ``verify`` makes it look structurally wrong
to a script: missing generator meta, missing banner div, missing
content-sha256, or — for markdown — body bytes that no longer hash to
the value the frontmatter claims.

This file is intentionally CLI-free. It returns structured
``VerifyResult`` objects; printing and exit codes are the caller's job
(see ``cli.py``). That keeps the same checks usable from tests and
from any future host integration.

Stdlib only: ``re``, ``dataclasses``, ``pathlib``. The ``content-sha256``
re-computation and frontmatter parsing are delegated to
``keynote_recap.frontmatter`` — the single source of truth for what
"a valid keynote-recap report" means at the bytes level.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import parse_frontmatter, verify_frontmatter

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Check:
    """A single named structural check and its outcome."""

    name: str
    ok: bool
    detail: str


@dataclass
class VerifyResult:
    """Aggregate result of running all applicable checks on a file."""

    ok: bool
    summary: str
    file_kind: str  # "html" | "md" | "unknown"
    checks: list[Check] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regexes — kept narrow on purpose; we want exact matches for the strings
# render.py emits, not a forgiving HTML parser.
# ---------------------------------------------------------------------------

_GENERATOR_META_RE = re.compile(
    r'<meta\s+name="generator"\s+content="keynote-recap\s+([^"]+)"\s*/?>'
)
_CONTENT_SHA_META_RE = re.compile(
    r'<meta\s+name="content-sha256"\s+content="([0-9a-f]{64})"\s*/?>'
)
# We deliberately match only ``class="recap-banner"`` / ``class="recap-stamp"``
# (and class lists containing them). render.py controls the exact markup; this
# module only asserts presence.
_RECAP_BANNER_RE = re.compile(r'class\s*=\s*"[^"]*\brecap-banner\b[^"]*"')
_RECAP_STAMP_RE = re.compile(r'class\s*=\s*"[^"]*\brecap-stamp\b[^"]*"')


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def verify_html_text(text: str) -> VerifyResult:
    """Run the HTML check chain against a raw HTML string.

    Order matches the validation chain in the v0.2.5 design doc; the
    first failing check determines the ``summary`` and short-circuits
    ``ok``. All other checks still run so callers (``--details`` in a
    future flag) can see the full picture.
    """
    checks: list[Check] = []

    # 1. <meta name="generator" content="keynote-recap X.Y.Z">
    gen_match = _GENERATOR_META_RE.search(text)
    if gen_match:
        version = gen_match.group(1).strip()
        checks.append(Check("generator_meta", True, f"keynote-recap {version}"))
    else:
        version = ""
        checks.append(Check("generator_meta", False, "missing"))

    # 2. <meta name="content-sha256" content="...">
    sha_match = _CONTENT_SHA_META_RE.search(text)
    if sha_match:
        sha = sha_match.group(1)
        checks.append(Check("content_sha256_meta", True, f"sha:{sha[:8]}"))
    else:
        sha = ""
        checks.append(Check("content_sha256_meta", False, "missing"))

    # 3. .recap-banner (v0.2.5+)
    has_banner = bool(_RECAP_BANNER_RE.search(text))
    checks.append(
        Check("recap_banner", has_banner, "present" if has_banner else "missing")
    )

    # 4. .recap-stamp (v0.2.4 redundant defence; kept)
    has_stamp = bool(_RECAP_STAMP_RE.search(text))
    checks.append(
        Check("recap_stamp", has_stamp, "present" if has_stamp else "missing")
    )

    # Build summary — match the failure messages spelled out in the spec.
    if not gen_match:
        summary = (
            'FAIL: HTML missing <meta name="generator" content="keynote-recap ...">'
        )
        return VerifyResult(False, summary, "html", checks)

    if not sha_match:
        summary = 'FAIL: HTML missing <meta name="content-sha256">'
        return VerifyResult(False, summary, "html", checks)

    # Friendly degradation: pre-v0.2.5 had stamp but no banner.
    if not has_banner and has_stamp:
        summary = (
            "FAIL: pre-v0.2.5 HTML — has stamp but no banner. "
            "Regenerate with v0.2.5+"
        )
        return VerifyResult(False, summary, "html", checks)

    if not has_banner:
        summary = (
            "FAIL: HTML missing .recap-banner element "
            "(v0.2.5+ HTML must have it)"
        )
        return VerifyResult(False, summary, "html", checks)

    if not has_stamp:
        summary = "FAIL: HTML missing .recap-stamp element"
        return VerifyResult(False, summary, "html", checks)

    summary = f"OK: keynote-recap v{version} · sha:{sha[:8]}"
    return VerifyResult(True, summary, "html", checks)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def verify_md_text(text: str) -> VerifyResult:
    """Run the markdown check chain against a raw markdown string."""
    checks: list[Check] = []

    meta, _body = parse_frontmatter(text)

    if not meta:
        checks.append(Check("frontmatter_present", False, "no frontmatter"))
        summary = (
            "FAIL: markdown has no frontmatter — not a keynote-recap report"
        )
        return VerifyResult(False, summary, "md", checks)

    checks.append(Check("frontmatter_present", True, f"{len(meta)} keys"))

    version = meta.get("keynote-recap-version")
    if not version:
        checks.append(Check("keynote_recap_version", False, "missing"))
        summary = (
            "FAIL: markdown missing keynote-recap-version field in frontmatter"
        )
        return VerifyResult(False, summary, "md", checks)
    checks.append(Check("keynote_recap_version", True, str(version)))

    # Re-use the canonical sha verifier from frontmatter.py — that module
    # owns the definition of "valid keynote-recap markdown".
    sha_ok, sha_msg, _meta2 = verify_frontmatter(text)
    if not sha_ok:
        # verify_frontmatter handles three failure modes; we already covered
        # "no frontmatter". The remaining ones are "no content-sha256" and
        # "sha mismatch".
        if "no content-sha256" in sha_msg:
            checks.append(Check("content_sha256", False, "missing"))
            summary = (
                "FAIL: markdown missing content-sha256 field in frontmatter"
            )
            return VerifyResult(False, summary, "md", checks)

        # sha mismatch — surface both hashes so the user can see drift.
        checks.append(Check("content_sha256", False, sha_msg))
        expected_full = str(meta.get("content-sha256", ""))
        # Recompute actual to mirror the spec's failure string.
        from .frontmatter import compute_body_sha256
        _meta_only, body_only = parse_frontmatter(text)
        actual_full = compute_body_sha256(body_only)
        summary = (
            "FAIL: content-sha256 mismatch — body has been edited after "
            "keynote-recap wrote it "
            f"(frontmatter says {expected_full[:8]}…, "
            f"body actually hashes to {actual_full[:8]}…)"
        )
        return VerifyResult(False, summary, "md", checks)

    sha = str(meta.get("content-sha256", ""))
    checks.append(Check("content_sha256", True, f"sha:{sha[:8]}"))

    summary = f"OK: keynote-recap v{version} · sha:{sha[:8]}"
    return VerifyResult(True, summary, "md", checks)


# ---------------------------------------------------------------------------
# File entry point
# ---------------------------------------------------------------------------


_HTML_SUFFIXES = {".html", ".htm"}
_MD_SUFFIXES = {".md"}


def verify_file(path: Path) -> VerifyResult:
    """Auto-detect ``.html`` vs ``.md`` and run the corresponding checks.

    Failure modes:

    - File does not exist or is unreadable → FAIL with that reason.
    - Unknown suffix → try markdown verification; if no frontmatter,
      FAIL "unknown file kind" rather than blaming markdown checks.
    """
    if not path.exists():
        return VerifyResult(
            ok=False,
            summary=f"FAIL: file does not exist: {path}",
            file_kind="unknown",
            checks=[Check("file_exists", False, str(path))],
        )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return VerifyResult(
            ok=False,
            summary=f"FAIL: cannot read file {path}: {e}",
            file_kind="unknown",
            checks=[Check("file_readable", False, str(e))],
        )

    suffix = path.suffix.lower()

    if suffix in _HTML_SUFFIXES:
        result = verify_html_text(text)
    elif suffix in _MD_SUFFIXES:
        result = verify_md_text(text)
    else:
        # Unknown suffix: anything with a leading frontmatter block is
        # still a keynote-recap-style report. Fall through to md verify;
        # if that produces "no frontmatter", reframe the error so the
        # user sees "unknown file kind" rather than a markdown-specific
        # message.
        meta, _body = parse_frontmatter(text)
        if not meta:
            return VerifyResult(
                ok=False,
                summary=f"FAIL: unknown file kind: {path.suffix or '(no suffix)'}",
                file_kind="unknown",
                checks=[Check("file_kind", False, path.suffix or "(no suffix)")],
            )
        result = verify_md_text(text)

    # Append filename to the OK summary for human context (per spec example).
    if result.ok:
        result.summary = f"{result.summary} · file={path.name}"
    return result
