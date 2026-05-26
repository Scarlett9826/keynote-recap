# v0.2.5 — Internalized Defense Layer

**Date**: 2026-05-25
**Status**: design accepted, ready to implement

## Problem

v0.2.4 M9 anti-shortcut layer assumed the threat model is "agent calls
`keynote-recap recap` but cuts corners". A real-world session with
opencode + sonnet 4.6 on 2026-05-25 demonstrated a deeper failure mode
not covered by M9:

The agent **did not call `keynote-recap recap` at all**. It read the
project's documentation (README, methodology/*.md), interpreted the
methodology as a writing checklist, then hand-wrote a 4.8 MB HTML
report that mimicked the project's expected output. Verification:

- No `<meta name="generator" content="keynote-recap ...">`
- No `<meta name="content-sha256">`
- No `.recap-stamp` floating element
- No standard `report.md` produced
- File path arbitrary (`~/Desktop/ACME 全生态发布会2026_深度回顾.html`)
- Heading format violates project methodology (`## 1、` instead of `## 一、`)
- Used 📌 emoji (project rule: only 📎/✅ allowed)

When confronted, the agent's self-critique listed 9 ways it "should have
followed methodology more closely" — still framing the methodology as a
*writing checklist for the agent*, not as a *code contract enforced by
the project*. The agent's mental model has no slot for "call a local
CLI"; it sees every task as "produce a compliant artifact".

The user requirement: stop expecting users to write defensive prompts
for every session. Internalize the defense in the project itself.

## Threat Model (revised)

| Threat | M9 (v0.2.4) coverage | v0.2.5 needed? |
|---|---|---|
| Agent calls `recap` but skips a stage | ✅ M9.2/M9.3 hard-abort | n/a |
| Agent calls `recap` but uses text-only model | ✅ M9.1 verified-models gate | n/a |
| Agent edits `report.md` and re-publishes | ✅ M9.5/M9.6 sha verify | n/a |
| **Agent does not call `recap`; hand-writes HTML** | ❌ **uncovered** | **yes — primary** |
| Agent claims success without producing artifact | ⚠️ partial (user must check) | **yes — secondary** |

## Design Principle

**Defense must not depend on agent cooperation.** Documentation that
asks the agent to behave is best-effort. The primary defense layer must
work even when the agent ignores all project documentation and tries
to fake an output.

## Three Layers

### L1: `AGENTS.md` (cooperation channel — best-effort)

A project-root file read by opencode, Cursor, Claude Code, and similar
agents by default. Hard-core directive style ("DO NOT manually write
HTML", "Your only valid action is..."). Four sections:

1. **Are you in the right place?** — quick yes/no for agents
   considering integration (covers scenario B: agent in another repo
   considering whether to use keynote-recap as a dep)
2. **The one rule** — call `keynote-recap recap`. Do not improvise.
3. **How to actually run it** — concrete commands, version gate,
   error handling that does NOT include "regenerate via LLM"
4. **Your output is not the report** — explicit boundary: agent's
   role is to invoke the tool and report results, not to author
   the report

Acknowledged limitation: agents that ignore documentation are the
primary threat. L1 only helps cooperative agents take the right path.

### L2: HTML top banner (forensic visual delta — primary defense)

The real defense. Goal: maximize the visual gap between a real
keynote-recap output and any hand-crafted impostor, so the impostor
fails on visual inspection regardless of agent cooperation.

Design parameters:
- **Position**: `position: sticky; top: 0; z-index: 9999;` — visible
  whenever the user scrolls to any part of the document, not just the
  first viewport. Removes the "agent crops the first 100px" attack.
- **Visual weight**: aggressive, not polite.
  - Top color bar: 6px solid `#ff6900` (project orange, full saturation)
  - Banner body: 38-44px tall, `#fff7ed` background, `#7c2d12` foreground
  - Single line, monospace (`Menlo`, `SF Mono`)
  - Format: `keynote-recap v0.2.5 · sha:abc12345 · model:claude-opus-4 · stages:6/6 · verified ✓`
  - Color modulation by integrity state:
    - Healthy: orange bar + light orange bg (default)
    - Half-run: yellow bar + light yellow bg
    - Unverified: red bar + light red bg
- **Print behaviour**: keeps banner inline at top of first page (already
  the pattern v0.2.4 uses for `.recap-stamp`)
- **Hide behaviour**: NONE. No close button, no fold. A closeable banner
  is a hand-craftable banner.

Why "ugly on purpose": a clean, polite banner is something an agent can
(and will) hand-fake to dress up its hand-written HTML. A loud, visually
distinctive banner with full project orange is something a user
recognizes by silhouette alone — and visually triggers the "this looks
official" response. Hand-crafted impostors will either look bare (no
banner) or look like a different bad copy of the banner (wrong color,
wrong height, no sticky behaviour).

The right-side floating `.recap-stamp` from v0.2.4 M9.7 is **kept** as
redundant defence. Both must be present in real output.

### L2.5: `keynote-recap recap-and-verify <url>` (combined command)

**Motivation (added 2026-05-25 mid-design):** the user asked whether
the agent could "self-verify after producing output, and re-run if
invalid". The honest answer is that keynote-recap cannot drive the
agent — when the agent hand-crafts HTML, this project is never even
loaded. But we can shrink the agent's call surface: a single command
that does the right thing end-to-end, raising the cost of "skip the
project and improvise".

`recap-and-verify <url> [args]` is a thin wrapper:

```
1. run `recap` (full pipeline through stage 6)
2. run `verify` on the produced report.html
3. if either fails, exit non-zero with the exact failure surfaced
4. on success, print a clear "VERIFIED ✓" line with sha and version
```

This is **not** a defence against agents that don't call the project.
It's a usability layer that:

- removes "produce md, render html, verify them" as three separate
  agent calls (each a chance to drift)
- gives `AGENTS.md` a single canonical command to mandate
- guarantees that any session ending with a successful
  `recap-and-verify` exit 0 has a verified, signed, banner'd HTML

### L3: `keynote-recap verify <file>` subcommand (validation channel)

Binary exit code + one-line summary. Three input file types
auto-detected:

- `.html` — parse for generator meta, banner div, stamp div, frontmatter
  comment block
- `.md` — parse frontmatter, recompute body sha, compare
- any text file with leading `---\n` frontmatter — same as `.md`

Validation chain:

```
1. file exists and readable
2. (html only) <meta name="generator" content="keynote-recap ..."> present
3. (html only) .recap-banner element present in <body>
4. (html only) .recap-stamp element present
5. frontmatter parseable (yaml-narrow per v0.2.4)
6. content-sha256 in frontmatter matches recomputed body sha
7. keynote-recap-version field present
```

Output:

- `OK: keynote-recap v0.2.5 · sha:abc12345 · model:claude-opus-4`
  (exit 0)
- `FAIL: <specific reason>` (exit 1)

Pre-v0.2.5 outputs return:
`FAIL: pre-v0.2.5 HTML, no banner. Regenerate with v0.2.5+`

Out of scope for v0.2.5 (deferred):
- `--details` flag with full check list (interface preserved)
- network checks (signature verification against GitHub releases)
- directory mode (`verify <dir>` to find unsigned files in output dir)
  — this is the v0.2.6 manifest design

## Files Changed

```
AGENTS.md                              [new]
src/keynote_recap/verify.py            [new] pure-function verification
src/keynote_recap/cli.py               [edit] add `verify` and `recap-and-verify`
src/keynote_recap/stages/render.py     [edit] _write_html injects top banner
                                        [edit] CSS adds .recap-banner (keep .recap-stamp)
tests/test_smoke.py                    [edit] +10 tests
CHANGELOG.md                           [edit] v0.2.5 entry
README.md                              [edit] verify section, AGENTS.md mention
pyproject.toml                         [edit] 0.2.4.1 → 0.2.5
src/keynote_recap/__init__.py          [edit] same
```

`AGENTS.md` mandates `recap-and-verify` (not `recap`) as the single
canonical agent-facing command.

## Tests (+10)

```
test_v025_verify_html_with_valid_frontmatter_returns_ok
test_v025_verify_html_with_tampered_body_returns_fail
test_v025_verify_html_without_generator_meta_returns_fail
test_v025_verify_html_without_recap_banner_returns_fail
test_v025_verify_md_with_valid_frontmatter_returns_ok
test_v025_verify_md_without_frontmatter_returns_fail
test_v025_verify_nonexistent_file_returns_fail
test_v025_render_writes_banner_at_body_top
test_v025_recap_and_verify_propagates_recap_exit_code
test_v025_recap_and_verify_runs_verify_on_success_path
```

123 total tests after change (was 113).

## Migration

- v0.2.4 users: `git pull && pip install -e .`. No code changes
  required on user side.
- v0.2.4-produced HTMLs: cannot be `verify`-ed (banner missing).
  `verify` returns FAIL with explicit "regenerate with v0.2.5"
  message. Not a silent regression.
- No CLI flag removal, no behaviour change for `recap` and
  `publish-html` core flow. Only addition: banner injection in
  `_write_html` and new `verify` subcommand.

Therefore not a BREAKING release; v0.2.4 → v0.2.5 minor bump.

## Explicitly Not Done (YAGNI)

- ❌ Network/signature verification
- ❌ Manifest file in output_dir (v0.2.6)
- ❌ Directory-mode verify
- ❌ `--details` flag (interface preserved, not implemented)
- ❌ Any change to `recap` main command behaviour
- ❌ Any change to v0.2.4 right-side `.recap-stamp` (kept as redundant)

## Acknowledged Limitations

1. An agent can still produce a hand-crafted HTML that includes a
   plausible-looking fake banner. The visual delta strategy assumes
   that doing so well enough to fool a user is hard, not impossible.
   Users who want certainty must run `verify`.
2. `verify` only checks structural integrity, not semantic
   correctness. A real keynote-recap output that produced poor
   content will still pass `verify`. This is by design — content
   quality is governed by stage gates (M9), not by `verify`.
3. `AGENTS.md` only helps cooperative agents. The L2/L3 layers do
   not depend on agent cooperation.
4. **No automatic re-run on verification failure.** keynote-recap
   cannot drive the agent — when the agent skips the project entirely
   and hand-crafts HTML, this project is never loaded and has no way
   to "self-trigger" a re-run. Auto-rerun must be implemented at the
   agent-host layer (e.g., opencode hooks, Cursor commands). v0.2.5
   reduces the surface needed for an agent to comply correctly
   (`recap-and-verify`) and makes non-compliance trivially detectable
   (`verify`); host-side auto-rerun is documented as a v0.2.6+
   integration recipe, not project code.
