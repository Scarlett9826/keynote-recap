"""YAML frontmatter for report.md — provenance + tamper detection.

v0.2.4 (M9.5/M9.6) introduces self-identifying report.md files. Every
report carries:

- ``keynote-recap-version`` — what produced it
- ``content-sha256`` — sha256 of body bytes after the frontmatter, so
  any post-hoc edit by an agent or human is detectable
- ``stages-completed`` / ``stages-skipped`` — which methodology pieces
  were actually run
- ``model-extract`` + tier — what model + capability was used

The single source of truth for "is this still the file keynote-recap
wrote?" is ``content-sha256``. ``publish-html`` refuses to render if it
mismatches.

We deliberately do NOT use a YAML library: stdlib only, narrow format,
hand-written parser. Frontmatter is a tiny fixed schema; a YAML lib
would let agents inject arbitrary keys we'd then have to validate.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

FRONTMATTER_DELIMITER = "---"
FRONTMATTER_RE = re.compile(
    r"\A---\n(.*?)\n---\n", re.DOTALL
)


def compute_body_sha256(body: str) -> str:
    """Return sha256 hex of body bytes (UTF-8). Stable across platforms.

    Body must NOT include the surrounding frontmatter; caller strips it
    first via ``parse_frontmatter`` or by handing in a raw body string.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def render_frontmatter(meta: dict[str, Any]) -> str:
    """Render a tiny restricted YAML frontmatter block.

    Supports str, int, float, bool, list[str|int|float] only. No nested
    objects. Keys emitted in insertion order. Strings are NOT quoted
    unless they contain ``:`` or ``#`` or start with whitespace; this
    is fine for our schema (URLs, sha hex, model names, tier enums).
    """
    lines = [FRONTMATTER_DELIMITER]
    for k, v in meta.items():
        lines.append(f"{k}: {_render_value(v)}")
    lines.append(FRONTMATTER_DELIMITER)
    lines.append("")  # trailing newline so body starts on its own line
    return "\n".join(lines)


def _render_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        items = ", ".join(_render_scalar(x) for x in v)
        return f"[{items}]"
    return _render_scalar(v)


def _render_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Quote if value contains characters that would break our naive parser.
    if any(c in s for c in (":", "#", "\n")) or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split ``text`` into (frontmatter_dict, body).

    If ``text`` lacks frontmatter, returns ``({}, text)``.

    Parser is intentionally narrow: only ``key: value`` lines, only the
    types ``render_frontmatter`` emits. Lists are parsed as ``[a, b, c]``.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block = m.group(1)
    body = text[m.end():]

    meta: dict[str, Any] = {}
    for raw_line in block.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _parse_value(value.strip())
    return meta, body


def _parse_value(raw: str) -> Any:
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(x.strip()) for x in inner.split(",")]
    return _parse_scalar(raw)


def _parse_scalar(raw: str) -> Any:
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"')
    # number?
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def attach_frontmatter(meta: dict[str, Any], body: str) -> str:
    """Compose final report.md = frontmatter + body, with sha256 of body
    automatically populated into meta['content-sha256'] beforehand.
    """
    meta = dict(meta)  # don't mutate caller's
    meta["content-sha256"] = compute_body_sha256(body)
    return render_frontmatter(meta) + body


def verify_frontmatter(text: str) -> tuple[bool, str, dict[str, Any]]:
    """Verify report.md content-sha256 matches its body.

    Returns (ok, message, frontmatter_dict).
    - (False, "no frontmatter", {}) — file has no frontmatter at all
    - (False, "no content-sha256", meta) — frontmatter present but missing field
    - (False, "sha mismatch: ...", meta) — body has been edited
    - (True, "ok", meta) — body is intact
    """
    meta, body = parse_frontmatter(text)
    if not meta:
        return False, "no frontmatter", {}
    expected = meta.get("content-sha256")
    if not expected:
        return False, "no content-sha256 in frontmatter", meta
    actual = compute_body_sha256(body)
    if actual != expected:
        return (
            False,
            f"sha mismatch: frontmatter says {expected[:12]}…, "
            f"body actually hashes to {actual[:12]}…",
            meta,
        )
    return True, "ok", meta
