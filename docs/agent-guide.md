# Agent guide — practical failure routing for keynote-recap

This document is for AI agents (or humans driving them) running
`keynote-recap recap-and-verify` end-to-end. It complements `AGENTS.md`
(which is the **what-not-to-do** contract) with a **what-to-do-when-it-breaks**
playbook.

If you have not read `AGENTS.md`, stop and read it first. The red lines
there override anything practical here.

> **The one rule, again**: invoke `keynote-recap recap-and-verify <url>`.
> Don't hand-craft reports, don't edit `report.md`, don't manually
> reproduce the pipeline. The CLI carries integrity gates that detect
> tampering — you will be caught.

---

## Table of contents

1. [Sanity ladder before the first run](#1-sanity-ladder-before-the-first-run)
2. [Failure routing by stage](#2-failure-routing-by-stage)
3. [Cross-stage runtime issues](#3-cross-stage-runtime-issues)
4. [Red banner triage](#4-red-banner-triage)
5. [Config templates](#5-config-templates)
6. [Lessons from real runs](#6-lessons-from-real-runs)

---

## 1. Sanity ladder before the first run

After installing or updating config, run in order:

```bash
keynote-recap config         # echo resolved config — prove the file parses
keynote-recap doctor         # preflight env + model-capability check
keynote-recap recap-and-verify <a-1min-test-video> --output-dir ./output/test
```

**API key check is non-negotiable**. The config file's `llm.api_key_env`
names an environment variable; the value of that variable is sent as the
auth header. Even if your gateway "looks like" it doesn't need a key,
`os.getenv()` happens before any request. If the var isn't set, stage 3
will abort with `Environment variable XXX not set`. **`doctor` warns
about this but does not abort** — set the variable explicitly before
running `recap-and-verify`, even if the gateway is internal.

```bash
export OPENAI_API_KEY="sk-..."   # or whatever your config names
```

---

## 2. Failure routing by stage

When `recap-and-verify` exits non-zero, **find the stderr message
verbatim** in the table below and surface the matched fix to the user.
Never improvise — the project's abort messages already include hints;
your job is to relay them, not rewrite them.

### Stage 0 — preflight env

| Symptom (stderr) | Root cause | Fix |
|---|---|---|
| `python: ... < 3.10 required` | Python below 3.10 | Upgrade Python; rerun. |
| `ffmpeg: not found` | ffmpeg not on PATH | `brew install ffmpeg` (macOS) / system equivalent. |
| `yt-dlp: not found` | yt-dlp not installed | `pip install -U yt-dlp`. |
| `disk: < N GB free` | not enough disk for video + frames | Free space; videos can be 1–5 GB. |
| `⚠ api_key: $VAR is not set` | **advisory, not blocker** | Continue, but set the var anyway — first LLM call will 401 otherwise. |

### Stage 0 — preflight model capability

| Symptom | Root cause | Fix |
|---|---|---|
| `extract: <model> — text-only / unverified` | `models.extract` not vision-capable | Set `models.extract` to a verified multimodal model (claude-sonnet-4 / gpt-4o / gemini-2.5-pro). See [§5](#5-config-templates). |
| `verify: <model> — text-only / unverified` | same for stage 5.5.2 caption verify | same fix on `models.verify`. |

### Stage 1 — download

| Symptom | Root cause | Fix |
|---|---|---|
| `yt-dlp: HTTP Error 412` (Bilibili) | login wall / region | Download manually first: `yt-dlp --cookies-from-browser chrome -o video.mp4 <url>`, then pass the local mp4 path as URL. The CLI does **not** expose `--cookies-from-browser` directly today. |
| `Format(s) 1080P 60帧 ... missing` (Bilibili 360p fallback) | not logged in to Bilibili | Same as above — download manually with cookies, then pass local mp4. |
| `no subtitles found` | source has no auto/manual subs | Re-run with `--transcript-file ./manual.srt`. |
| `unsupported URL` | yt-dlp doesn't know this site | Download manually; pass local mp4 path as URL. |

### Stage 2 — segment (cheap; rarely fails)

Mostly deterministic ffmpeg + scene-detect. If it fails, surface stderr
verbatim — almost always a corrupt download.

### Stage 3 — extract (v0.3.1 hard gates)

| Symptom | Root cause | Fix |
|---|---|---|
| `ExtractFloorError: selected_frames count N < <floor>` | Vision LLM rejected too aggressively, or source video too low-res/short | Pipeline auto-retries stage 3 once with breach injected as `[RETRY GUIDANCE]`. If retry still fails, `image_mix_passed=False` and the final report carries a red banner. Common real cause: B 站 360p fallback (no cookies) — get higher-quality source. |
| `ExtractFloorError: live ratio X% < 50%` | too many marketing renders / b-roll, too few live keynote frames | Same retry path. If retry still fails, the source might be a heavily-edited recap rather than live keynote. |
| `VisionCapabilityError: model cannot see images` | configured `models.extract` is text-only despite `doctor` passing | Fix `models.extract`; rerun. |
| Heuristic-scorer fallback path activated (frames have `category=other` / fixed `info_density=0.7`) | every vision batch failed (network / 5xx / auth) | **This is a silent degradation**. The pipeline continues but the report's images are not vision-vetted. Surface this clearly to the user; do **not** treat the resulting report as valid. Check API health and rerun. |

The **caption-verify wrong count** gate (5.5.2 sample of 10) trips a
stage-3 retry when wrong count > 1
(`EXTRACT_CAPTION_VERIFY_WRONG_MAX`). Pipeline does this, not you.

### Stage 4 — research

| Symptom | Root cause | Fix |
|---|---|---|
| `duckduckgo_search` import error | DDG renamed to `ddgs` | `pip install -U keynote-recap`. |
| All searches returned 0 results | rate-limited or network | Set `search.api_key_env: TAVILY_API_KEY` and provide a Tavily key — research stage degrades gracefully but is poorer without it. |

### Stage 5 — draft

| Symptom | Root cause | Fix |
|---|---|---|
| `BadRequestError: response_format` | `provider: openai-compatible` against an Anthropic-native gateway | Set `llm.provider: anthropic-native`. |
| `401 / 403` from LLM | wrong api_key_env or expired key | Re-export the var; rerun. |
| `--tier strict` produces empty body | model can't follow strict prompt's 21 forbidden phrases | Drop to `--tier standard`; for low-capability multimodal, `--tier easy`. |

### Stage 5.5 — verify (lint gates)

These are **hard gates** that produce a red banner. The pipeline either
auto-retries (image-related) or marks `quality_passed=False` and exits.
**Do not edit `report.md` to "fix" a red banner** — sha256 in
frontmatter will mismatch and `verify` rejects.

| Gate | Soft / Hard | Trigger |
|---|---|---|
| `[5.5.0] image filenames` | HARD → stage-3 retry | any caption references a non-existent file |
| `[5.5.1] coverage` | HARD → stage-3 retry | any `## 章节` has 0 images |
| `[5.5.1b] per-section / per-mainline floor` | HARD → stage-3 retry | per-section < 1 OR per-mainline < 4 |
| `[5.5.2] caption verify` | HARD → stage-3 retry | sample-10 wrong count > 1 |
| `[5.5.3] anti-AI lint L1` | HARD → stage-5 retry | forbidden emoji (📌) / phrases / overhype |
| `[5.5.3] anti-AI lint L2` | SOFT (yellow banner) | weaker style violations |
| `[5.5.4] image-section fit` | SOFT (yellow) | static keyword-overlap heuristic mismatch |
| `[5.5.4b] bucket placement` | HARD → stage-5 retry | image landed in wrong chapter bucket |
| `[5.5.5] structure` | HARD (red banner) | missing **核心判断**, < 4 quotes, < 8 table rows, title format wrong |
| `[5.5.6] image source mix` | HARD → stage-3 retry | total < floor or live ratio < floor |
| `[5.5.7] topic coverage` | HARD → stage-3 retry | any topic from transcript has 0 frames |

---

## 3. Cross-stage runtime issues

These can hit any LLM-driven stage (3 / 4 / 5 / 5.5 / 6).

| Symptom | Root cause | Fix |
|---|---|---|
| Process at 0% CPU for several minutes during an LLM stage | Half-dead TCP connection — server stopped sending tokens mid-stream but didn't close the socket | **Fixed in p14**: `httpx.Timeout(read=120s)` triggers fast-fail; tenacity retries 3x. If you see this on `>= p14`, the gateway is genuinely broken — let retries exhaust before killing. |
| Pipeline hangs without producing output for >10 min on a stage that normally takes <2 min | Stage looping internally on transient model errors | Capture stderr, look for repeated retry messages, then kill and rerun with `--start-stage <next>`. |
| `httpx.ReadTimeout: ... read operation timed out` after ~120s | Working as intended — read floor caught a hang | Tenacity will retry. If all 3 retries time out, surface to user. |
| Process killed by SIGKILL but `output/<slug>/` files reappear/disappear | Stale background `keynote-recap` / `yt-dlp` / `ffmpeg` from prior aborted run | `pgrep -fl 'keynote-recap\|yt-dlp\|ffmpeg'`, `kill -9`, clean output dir, rerun. |

---

## 4. Red banner triage

`report.html` and `report.md` carry one of three banners:

- 🟢 **green** — `quality_passed=True` and zero L1 / hard-gate failures
- 🟡 **yellow** — `quality_passed=True` with L2 warnings
- 🔴 **red** — `quality_passed=False` OR any hard gate failed OR
  `quality_passed` field never set (early return)

### Red banner — first questions

1. **Did the pipeline actually finish?** Look at stderr for "Quality
   gate did not run". If yes, the pipeline aborted before stage 5.5
   finalised. Treat as exit-2 failure.
2. **Which gate failed?** Open `output/<slug>/lint_report.md`. It
   enumerates every 5.5.x gate with PASS / FAIL and the specific reason.

### What you must NEVER do with a red banner

- ❌ Edit `report.md` to "fix" the issue. Sha256 in frontmatter is
  recomputed by `publish-html` and `verify`; any edit fails the gate.
- ❌ Delete the banner from `report.html`. `verify` detects its absence.
- ❌ Re-render with `publish-html` after editing `report.md` (fails sha
  check).
- ❌ Tell the user "the recap is ready" — it is not. A red banner means
  the artifact is publication-blocked.
- ❌ Manually reproduce the methodology and write a clean copy.
  `AGENTS.md` §1 forbids this; banner + verify will catch it.
- ❌ Manually edit `state.json` to mark stages "complete" so the
  pipeline skips. Stages 4/5/5.5 read `selected_frames` and the
  resulting "report" reflects whatever was injected — including
  rescue-path placeholders. The user will see images that don't match
  the talk.

### What you SHOULD do with a red banner

1. Re-run `recap-and-verify` once — pipeline resumes from cached state.
2. If still red: paste `lint_report.md` excerpt verbatim to the user
   and let them choose:
   - try a different source URL (most common fix for image-quality gates)
   - drop `--tier strict` to `--tier standard` (style gate failures)
   - accept the red banner (rare; only if user understands the report
     is not vetted)
   - debug deeper (open issues)

---

## 5. Config templates

`~/.config/keynote-recap/config.yaml`. Generate the default shell with:

```bash
keynote-recap config --init
```

Then replace the `llm.*` block with one of the templates below.

### Verified multimodal models (must use one of these)

| Model | Provider | Context | Notes |
|---|---|---|---|
| `claude-opus-4` / `claude-sonnet-4` | Anthropic | 200K | Best for `--tier strict`. |
| `gpt-4o` / `gpt-4-turbo` | OpenAI | 128K | Standard. |
| `gemini-2.5-pro` | Google | 1M | Best price/perf. |

**Known to NOT work** (will silent-fail on stage 3 / 5.5.2):

- `gpt-4o-mini`, `gpt-3.5-*` (text variants)
- `deepseek-v3`, `deepseek-r1` (text-only)
- any `*-text` / `*-instruct` model without explicit vision support

### Template A — corporate anthropic-native gateway

For corporate / proxied LLM gateways exposing Claude via the native
Anthropic Messages protocol:

```yaml
llm:
  provider: anthropic-native
  base_url: https://<your-internal-gateway>/anthropic/v1
  api_key_env: <YOUR_KEY_ENV_VAR>
  timeout_s: 600
  max_retries: 3
  models:
    extract:    <prefix>/claude-sonnet-4
    research:   <prefix>/claude-sonnet-4
    draft:      <prefix>/claude-sonnet-4
    verify:     <prefix>/claude-sonnet-4
    transcribe: <prefix>/claude-sonnet-4

search:
  provider: duckduckgo
  timeout_s: 15

video:
  resolution: 1080p60
  keep_video: true
  download_subtitles: true
  languages: [zh-Hans, zh, en]

stages:
  start: 1
  end: 6

draft:
  tier: strict
```

Common gotchas:

- `provider: anthropic-native` — gateway speaks `/anthropic/v1/messages`,
  not OpenAI's `/v1/chat/completions`. Using `openai-compatible` returns
  `BadRequestError: response_format`.
- Some gateways require a vendor / route prefix on the model ID (e.g.
  `myproxy/claude-sonnet-4`). Without it: "model not found".
- `api_key_env` is *just a name*, not a binding to OpenAI; the
  anthropic-native backend reads whatever env var is named here and
  sends the value as the Anthropic `x-api-key` header.

### Template B — direct OpenAI

```yaml
llm:
  provider: openai-compatible
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  timeout_s: 600
  max_retries: 3
  models:
    extract:  gpt-4o
    research: gpt-4o
    draft:    gpt-4o
    verify:   gpt-4o
```

### Template C — direct Anthropic

```yaml
llm:
  provider: anthropic-native
  base_url: https://api.anthropic.com
  api_key_env: ANTHROPIC_API_KEY
  models:
    extract:  claude-sonnet-4-20250514
    research: claude-sonnet-4-20250514
    draft:    claude-sonnet-4-20250514
    verify:   claude-sonnet-4-20250514
```

### Template D — OpenRouter (multi-provider)

```yaml
llm:
  provider: openai-compatible
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY
  models:
    extract:  anthropic/claude-sonnet-4
    research: anthropic/claude-sonnet-4
    draft:    anthropic/claude-sonnet-4
    verify:   anthropic/claude-sonnet-4
```

---

## 6. Lessons from real runs

These are anti-patterns observed in actual agent sessions. They led to
bad reports — sometimes silently. Do not repeat them.

### Anti-pattern: "Stage 1 doesn't accept local files, so I'll inject state"

**Observed**: agent encountered Bilibili 412, downloaded video manually
with `yt-dlp --cookies-from-browser`, then tried to pass the local mp4
path. CLI rejected it (URLs only). Agent then **wrote a fake `state.json`
with a constructed `VideoMeta` dict** and used `--start-stage 2` to
skip stage 1.

**Why it broke**: stage 3 then failed (no API key), but the agent's
state injection had already advanced `last_completed_stage` past stage
1. The next run saw stage 3 "completed via rescue path" (heuristic
scorer, not vision LLM) and continued to stage 4–6, producing a
**report whose 35 selected frames were chosen by file-size heuristic,
not vision analysis**. `verify` returned exit 0 (signature was valid)
but the report content was meaningless.

**Correct path**: if Bilibili 412, surface to user, ask them to log
into Bilibili in browser; or have user run `yt-dlp` themselves and use
the manual fetch as a separate documented step. Do **not** synthesise
state.

### Anti-pattern: "API key missing — let me set a placeholder so it doesn't abort"

**Observed**: `OPENAI_API_KEY` not set. Agent set
`OPENAI_API_KEY=placeholder` to satisfy the `os.getenv()` check, hoping
the gateway would inject the real key.

**Why it broke**: gateway returned 401 on every call. Vision batches
all failed → rescue-path heuristic scorer activated → fixed
`info_density=0.7`, `category=other` for all frames. Report generated
but vision-blind.

**Correct path**: stop and ask the user for the real key. If you can't
get it, abort cleanly. A 401-driven rescue path is silent degradation,
not a partial success.

### Anti-pattern: "verify exit 0, so the report is good"

**Observed**: agent declared success based solely on `keynote-recap
verify` returning 0.

**Why it broke**: `verify` checks integrity (sha256, banner presence,
frontmatter). It does **not** check whether stage 3 used vision LLM
vs rescue path, or whether the frames actually match the talk. The
report can be self-consistently signed and still be content-wrong.

**Correct path**: also check `state.json` for
`stages_completed` (stage 3 must be there, not just `last_completed_stage`)
and `quality_passed=True`, **and** spot-check 2–3 frames against the
captions before declaring success to the user.

### Anti-pattern: "skill SKILL.md says do X, but I'll do Y because Y seems faster"

**Observed**: skill / `AGENTS.md` told the agent not to edit `state.json`.
Agent did anyway because "the pipeline structure was wrong for my
case".

**Why it broke**: see first anti-pattern. The pipeline's state
machine is the contract. Skipping ahead breaks downstream stages
silently.

**Correct path**: if the canonical command doesn't fit, **stop and
report the gap to the user**. Do not work around it. Workarounds in
this pipeline produce reports that look real but aren't.

---

## Verify subcommand exit codes

`keynote-recap verify <file>`:

- **exit 0** — `OK: keynote-recap vX.Y.Z · sha:abc12345 · file=...`
- **exit 1** — `FAIL: <reason>`. Common reasons:
  - `missing <meta name="generator">`
  - `missing .recap-banner element`
  - `content-sha256 mismatch (body edited)`
  - `frontmatter missing keynote-recap-version`

If `verify` fails after a successful `recap`, re-run `recap-and-verify`
once. If it still fails, that's a bug — file an issue with the user's
permission.
