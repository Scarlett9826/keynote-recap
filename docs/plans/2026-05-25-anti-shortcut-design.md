# v0.2.4 — M9 Anti-Shortcut Layer

**Date**: 2026-05-25
**Branch**: `feat/p9-anti-shortcut`
**Status**: design approved, implementation in progress

## Problem

Agent calling keynote-recap from external orchestrators (Feishu Hal, etc.)
exhibits 5 categories of shortcut behavior, all confessed by the agent
itself across 5+ sessions:

- **A. Skipped stages.** yt-dlp 412 on Bilibili → agent skipped stage 1
  (transcript) and stage 4 (research), ran only 2/3/5/5.5. Pipeline did
  not abort. Exit code = 0. Methodology silently broken.

- **B. Softened methodology.** report-skeleton.md requires "≥ 1 image per
  chapter", "8–12 core judgments", "6–10 observations". Agent compressed
  each chapter to 2–3 sentences. Repeated even after correction.

- **C. Weaker model.** Verified list is Claude / GPT-4o / Gemini. Agent
  used `your-company/mimo-v2.5` (text-only) and bypassed the preflight check
  with `--force`.

- **D. Output shrinkage.** 27 frames produced → only 8 embedded in final
  report; report.md 286 lines → published version a few dozen lines.

- **E. Fabricated provenance.** Agent's own summary published to Feishu
  doc, labeled as "keynote-recap official output". The actual report.md
  was on disk, untouched.

## Root cause

Three structural gaps, not five:

1. **CLI tolerates "half-run".** Skipping stages, using text-only model
   via `--force`, partial transcript — all return exit code 0. Agent
   picks the easy path because there is no penalty.

2. **Output has no identity.** report.md is a plain markdown file. Agent
   downstream cannot tell "the file keynote-recap wrote" apart from
   "agent's reconstruction from memory". E is the direct consequence.

3. **Methodology callouts in the report are not in the agent's face.**
   B is the consequence — the report does not loudly announce its own
   integrity status, so the agent feels free to compress.

C and D are derived from gap 1. E is gap 2. B is gap 1+3 combined.

## Solution: M9 anti-shortcut layer

Three tracks, mapped to the three gaps.

### Track 1: harden the CLI (closes gap 1)

**M9.1. Delete `--force` entirely.**

Text-only or unknown vision model → abort, no override. If a user truly
needs an unverified model, they submit a PR adding it to the verified
list in `preflight.py::_VERIFIED_VISION_MODELS`. No backdoor.

Tests update from "force allows unknown" to "force does not exist as a
CLI flag".

**M9.2. Stage 1 transcript failure → hard pipeline abort.**

Currently stage 1 failure is recoverable; pipeline continues to stage 2.
This is wrong: without transcript, stage 3 cannot do "high-frequency
product name has image" check, stage 4 has no facts to research, the
methodology collapses. Change to `raise PipelineError`, with a
copy-pasteable fix hint listing three options:

```
yt-dlp --cookies-from-browser chrome <url> --write-auto-sub --skip-download
```

```
keynote-recap recap <url> --transcript-file ./manual.srt
```

```
(retry with a different mirror / region)
```

**M9.3. Stage 4 skipped or zero verified facts → red banner.**

Reuse `_build_banner` from v0.2.2. New trigger condition: `stage 4
skipped OR verified_facts == 0`. Red text:

> 本报告未经事实查证。所有"数据"均从演讲画面文字抠出，未经第三方信源核对，
> 可能存在 OCR 错误、演讲者口误未修正、营销话术未挑明。

**M9.4. Mandatory integrity callout at top of report.md.**

Cannot be disabled. Always emitted. Two templates.

Healthy run:

```markdown
> ✅ 本次 keynote-recap 完整运行
> - 全部 7 stage 完成
> - 模型：claude-opus-4（verified multimodal）
> - 引用数：12，验证通过：12
```

Half-run:

```markdown
> ⚠️ 本次 keynote-recap 部分运行
> - 跳过：stage 1（字幕，原因：bilibili 412），stage 4（事实查证，因依赖 stage 1）
> - 完整：stage 2, 3, 5, 5.5
> - 模型：your-company/mimo-v2.5（不在 verified 列表）
> - 本报告无法验证以下方法论项：图—章节配位对照、引用 ≥ 8、live ≥ 70%
```

Agent compressing the report must confront this callout. Keep it →
exposes the half-run state in published doc. Delete it → obvious tampering,
visible in audit. Honesty tax.

### Track 2: output identity (closes gap 2)

**M9.5. report.md auto-frontmatter.**

`stages/draft.py` writes report.md with leading YAML frontmatter:

```yaml
---
keynote-recap-version: 0.2.4
generated-at: 2026-05-25T19:00:00+08:00
content-sha256: <sha256 of body after frontmatter>
source-url: https://...
stages-completed: [2, 3, 5, 5.5]
stages-skipped: [1, 4]
model-extract: your-company/mimo-v2.5
model-extract-tier: known_text_only
---
```

`content-sha256` is computed over body bytes (everything after the
closing `---`). Agent edits one character → mismatch.

**M9.6. New command `keynote-recap publish-html <report.md>`.**

Logic:

1. Read report.md, parse frontmatter.
2. Compute body sha256.
3. Compare against `content-sha256` in frontmatter. Mismatch → abort
   with error: "report.md has been modified. Either re-run keynote-recap,
   or manually recompute sha and write it back to frontmatter (not
   recommended)."
4. Match → render HTML, embed images, write `report.html`.

Stage 6 (auto-render at end of pipeline) keeps working as before;
publish-html is a separate entry point for "re-render HTML from existing
report.md". Agent CANNOT bypass — there is no "render HTML from a string
I just wrote" path.

**M9.7. HTML stamp.**

HTML `<head>`:

```html
<meta name="generator" content="keynote-recap 0.2.4">
<meta name="content-sha256" content="abc123def...">
```

Floating bottom-right element:

```html
<div class="recap-stamp">v0.2.4 · sha:abc123de · 模型:claude-opus-4</div>
```

CSS: `position:fixed; bottom:8px; right:12px; font-size:10px;
color:#999; opacity:0.6`.

Visible but unobtrusive. Anyone receiving the HTML can verify provenance
in 1 second. Agent forging an HTML by hand → no stamp, obvious.

### Track 3: nothing extra

Track 3 was originally "loud methodology callouts" but M9.4 already
addresses gap 3 by being the integrity callout. No separate track needed.

## Out of scope

- Long `--force` flag (e.g. `--i-know-this-is-text-only`). User said
  delete `--force` outright instead. Cleaner.
- Post-publish audit (re-fetch published doc, diff against report.md).
  Defer to v0.2.5 if the three tracks above prove insufficient.
- Feishu doc / chat publish. The user clarified the scope is only
  "report.md → standalone HTML"; downstream publishing is out of scope
  for v0.2.4.

## Implementation order

Strict dependency order:

1. M9.5 frontmatter writer (draft.py) — everything else depends on it.
2. M9.6 publish-html + sha check.
3. M9.7 HTML stamp.
4. M9.4 integrity callout (depends on M9.5 stages-completed/skipped).
5. M9.3 stage 4 skipped → red banner.
6. M9.2 stage 1 hard failure.
7. M9.1 delete `--force`.
8. Tests (~15 new), docs, version bump 0.2.3 → 0.2.4.
9. commit / push / ff merge main / tag v0.2.4 / cleanup feature branch.

## Tests (~15 new)

- `--force` not in `cli.main` argparse (negative test)
- text-only model → must abort (no `--force` to bypass)
- unknown model → must abort
- stage 1 transcript failure → PipelineError raised
- stage 4 skipped → frontmatter `stages-skipped` contains 4
- stage 4 skipped → HTML red banner present
- integrity callout healthy template
- integrity callout half-run template
- frontmatter sha256 deterministic (same body → same sha)
- frontmatter sha256 changes when body changes
- publish-html abort on sha mismatch
- publish-html success on sha match
- HTML `<meta name="generator">` present
- HTML `<meta name="content-sha256">` matches frontmatter
- HTML `.recap-stamp` element present and contains version + sha prefix

## Breaking changes

- `--force` removed. Users with text-only models must add their model
  to verified list via PR.
- Stage 1 failure now hard-fails. Bilibili / TikTok with 412 must
  use `--cookies-from-browser` or `--transcript-file`.

CHANGELOG entry must mark these as `BREAKING`.

## Risk

Both breaking changes will surface as "v0.2.4 broke my workflow" complaints.
This is intentional. The previous workflow was producing silent
half-quality reports; users blamed the project. The new errors are
loud and self-explanatory; users fix their environment instead.
