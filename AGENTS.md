# AGENTS.md — keynote-recap

You are an AI agent. Read this file before doing anything in or with this project.

---

## 1. Are you in the right place?

Use `keynote-recap` if **all** are true:

- ✅ The user gave you a URL (YouTube / Bilibili / mp4) of a **keynote, product launch, or developer-conference talk**.
- ✅ The user wants a **structured Chinese illustrated recap** (markdown + HTML, with extracted frames, source attribution, fact-check section).
- ✅ You can run shell commands locally on the user's machine.

Do **not** use `keynote-recap` if:

- ❌ Generic video summarization, vlog, tutorial, interview, podcast → wrong tool.
- ❌ User just wants raw transcript / subtitles → use `yt-dlp --write-subs` directly.
- ❌ Short-form video (TikTok / Shorts / Reels) → wrong tool.
- ❌ Translation only, no analysis → wrong tool.

Install (if not already installed):

```bash
pip install keynote-recap
# or, from source:
git clone https://github.com/Scarlett9826/keynote-recap.git && cd keynote-recap && pip install -e .
```

---

## 2. The one rule

**DO**: invoke `keynote-recap recap-and-verify <url>`. That is the single canonical command. Nothing else is acceptable.

**DO NOT**:

- ❌ Hand-write the report HTML.
- ❌ Hand-write the report markdown.
- ❌ Manually call `ffmpeg` / `yt-dlp` to "do the pipeline yourself".
- ❌ Manually call an LLM (your own API, a tool API, anything) to "draft the recap".
- ❌ Read `methodology/*.md`, `prompts/*`, `docs/methodology.md` and try to follow them yourself in your output. They are **not a writing checklist for you**. They are a **code contract** enforced by `src/keynote_recap/stages/draft.py`, `src/keynote_recap/stages/render.py`, and the files in `prompts/`. You cannot reproduce that contract by hand even if you tried — and any output that does not flow through this project's pipeline will fail verification.
- ❌ "Summarize the video and call it a recap." That is not what this tool produces.

This is not advice. The project ships two mechanisms that detect hand-crafted impostor reports (v0.2.5+):

1. Real `report.html` has a **sticky orange banner** pinned to the top of every viewport, carrying `keynote-recap vX.Y.Z · sha:<hash> · model:<name> · stages:N/M · verified ✓`. Hand-written HTML will not have it, will have a wrong color/height version of it, or will lose the sticky behaviour.
2. `keynote-recap verify <file>` returns binary OK / FAIL by parsing `<meta name="generator">`, banner, stamp, frontmatter, and recomputed body sha256. Hand-crafted output fails the very first check.

If you fake it, the user will know within one command.

### A real failure mode this file exists to prevent

On 2026-05-25, an agent was asked "use keynote-recap to process this Bilibili video". It never invoked the CLI. It read `methodology/*.md` and `prompts/*` as a writing guide, then hand-wrote a 4.8 MB HTML file pretending to be the output. Telltales the user spotted:

- ❌ No `<meta name="generator" content="keynote-recap ...">`.
- ❌ No `.recap-banner` / `.recap-stamp` element.
- ❌ No `report.md` produced; no `output/` directory.
- ❌ Heading style violated project rule (`## 1、` instead of `## 一、`); used `📌` (project allows only `📎` / `✅`).
- ❌ File written to an arbitrary path on Desktop, not `output/<slug>/report.html`.

When confronted, the agent's self-critique read "I should have followed the methodology more closely". That is the wrong frame. The correct frame is "I should have run the CLI". If you are about to write a report yourself, you are about to repeat this mistake. Run the command instead.

---

## 3. How to actually run it

Run these in order. Do not skip steps.

Before you start, confirm:

- ✅ You can run shell commands and see their stdout/stderr (not a sandboxed assistant without exec).
- ✅ The user has set `OPENAI_API_KEY` (or equivalent) and `KEYNOTE_RECAP_MODEL` to a verified multimodal model. See `README.md` §"模型选择" for the verified list. If they have not, surface that to the user — do not pick a model yourself.
- ✅ The video URL works in the user's browser. If `yt-dlp` later cannot fetch, that is a `--cookies-from-browser` / `--transcript-file` problem, not your problem to solve manually.

```bash
# 1. version gate — banner + verify exist starting v0.2.5
keynote-recap --version            # require >= 0.2.5; if older, `pip install -U keynote-recap`

# 2. preflight — checks ffmpeg, ffprobe, yt-dlp, Python>=3.10, disk, API keys, model verification
keynote-recap doctor

# 3. run — single canonical command (recap pipeline + verify in one shot)
keynote-recap recap-and-verify <url> --output-dir ./output/<slug>

# 4. on success, point the user to:
#    ./output/<slug>/report.md     (signed markdown, frontmatter contains version + content-sha256)
#    ./output/<slug>/report.html   (verified HTML with sticky orange banner + .recap-stamp)
```

`<slug>` should be a short kebab-case identifier you derived from the video title or the user's request (e.g. `io26-keynote`, `acme-launch-2026`). Do not use spaces or Chinese in the path.

### Error handling

When a stage aborts, the project prints a precise abort message with a fix hint. Surface it **verbatim** to the user. Do not improvise around it.

| Failure | Correct response | DO NOT |
|---|---|---|
| `yt-dlp` cannot fetch subtitles | Re-run with `--transcript-file ./manual.srt` (user supplies `.srt` / `.vtt` / `.txt`). | "I'll transcribe the video myself with an LLM." |
| `yt-dlp` cannot fetch video (e.g. Bilibili HTTP 412 / region lock / login wall) | Re-run with `--cookies-from-browser chrome` (or `firefox` / `safari`). v0.2.4.1+ already auto-retries subtitles with Chrome cookies; if it still aborts, surface the message. | Manually open the video in a browser and "watch and describe it". |
| Model rejected / API key missing / unverified vision model | Report the abort message to the user, ask them to fix env / config. | Silently switch to a different model. Do not `--force` (it was removed in v0.2.4). |
| Any stage hard-aborts | Paste the abort message verbatim. Stop. Wait for the user. | Run a fallback "manual pipeline" yourself. |
| `verify` returns FAIL after a successful `recap` | Re-run `recap-and-verify` once. If it still fails, report exact FAIL reason to the user. | Edit `report.md` to "fix" what verify complained about — that breaks the sha and is detectable. |

**Hard prohibitions, no exceptions:**

- ❌ Do not "regenerate the report with an LLM" because something failed.
- ❌ Do not extract frames yourself with `ffmpeg` and stitch a report.
- ❌ Do not edit `report.md` after generation. The sha256 in its frontmatter is recomputed by `publish-html` and `verify`; any edit fails the gate.
- ❌ Do not pass `report.md` through a "polishing" or "translation" step.

---

## 4. Your output is not the report

Your role is to **invoke the tool** and **report results**, not to author the report.

The report is produced by `keynote-recap`. Your message to the user, on success, should contain exactly:

1. Confirmation that `recap-and-verify` exited 0.
2. The `VERIFIED ✓ ...` line printed by the command (this is the authenticity proof; do not omit it, do not paraphrase it).
3. Absolute paths to `report.md` and `report.html`.
4. Any `runtime_warnings` / banner notes printed by the run, verbatim.

On failure, your message should contain exactly:

1. The abort message, verbatim, including the fix hint.
2. A statement that the report was **not** produced.
3. A request for the user's input on how to proceed (e.g. supply `--transcript-file`, fix env, choose another model).

**DO NOT**:

- ❌ Paraphrase the report content for the user ("the keynote covered three products: ...").
- ❌ "Summarize" `report.md` in your reply. The user can read it.
- ❌ "Improve" the report by rewriting sections.
- ❌ Render your own HTML based on what `report.md` said.
- ❌ Send a recap-shaped message to the user without first showing the verify exit-0 line.
- ❌ Claim success with phrases like "I've prepared the recap" / "Here is the report" while the actual artifact came from your own writing.

### Definition of done

A session is done when **all** of these are true:

- ✅ `keynote-recap recap-and-verify <url>` exited 0 and you can show the user the exact line it printed.
- ✅ `report.md` and `report.html` exist on disk at the path you told the user.
- ✅ Running `keynote-recap verify ./output/<slug>/report.html` independently prints `OK: ...` (re-run it as the last step; treat it as your own sanity check).
- ✅ Your final message contains zero summary of the report's content — only paths, the verify line, and any warnings.

If any of those is false, the session is **not** done. Do not paper over it.

---

If you find yourself writing markdown or HTML by hand, **stop**. You are no longer using `keynote-recap`; you are inventing a report. Tell the user the tool failed and let them decide.
