# Changelog

All notable changes to **keynote-recap** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.5] — Agent-friendly preflight phrasing (2026-05-26)

### Fixed

- **doctor preflight no longer scares external agent wrappers into
  aborting**. Pre-v0.3.5, when ``OPENAI_API_KEY`` (or whatever
  ``cfg.llm.api_key_env`` named) was not literally set in the calling
  shell, ``keynote-recap doctor`` rendered::

      ⚠ api_key: $OPENAI_API_KEY is not set — LLM stages will fail with
        401 unless the SDK reads the key from another source ...

  This was technically correct: the check is ``severity="warning"``
  (advisory, never aborts the CLI itself, fixed in v0.2.5.1). But every
  agent wrapper we tested — opencode hooks, cron drivers, claude-desktop
  runners — over-read ``⚠`` + the words ``"fail"`` and ``"401"`` and
  aborted *itself* before invoking the CLI, refusing to even try.
  v0.3.5 fully neutralizes both the wording and the rendering so
  agents can no longer mis-classify this as an error condition:

  1. Detail wording rewritten to pure status: ``$OPENAI_API_KEY not in
     shell env; SDK will resolve from gateway / keychain / proxy on
     first call.`` Words ``fail`` / ``401`` / ``missing`` / ``unset`` /
     ``error`` / ``abort`` are forbidden in the rendered output (test
     ``test_v035_doctor_stdout_has_no_alarming_words_when_api_key_unset``
     enforces this).
  2. ``cli._preflight_env`` special-cases ``what == "api_key"`` and
     renders ``ℹ`` blue instead of ``⚠`` yellow. Other warning-severity
     checks keep ``⚠``; this isolates the visual change to the one
     check that was causing agent abort, without weakening the
     surrounding warning vocabulary.
  3. ``EnvCheck.fix`` for this case is now ``None`` (was
     ``"export $X=..."``). The SDK owns key resolution; we don't
     prescribe.
  4. Severity remains ``"warning"`` — ``state.preflight_env_warnings``
     and the report banner still record the diagnostic for audit.
     Only the *display* layer was softened.

### Changed

- ``preflight_env.check_api_key`` returns ``EnvCheck(severity="warning",
  fix=None, detail="<env-var> not in shell env; SDK will resolve from
  gateway / keychain / proxy on first call.")`` when the env var is
  missing. Old detail string and ``export ...`` fix string are gone.

### Tests

- 2 new tests; total **216** (was 214).
- ``test_v035_doctor_stdout_has_no_alarming_words_when_api_key_unset``:
  renders the api-key-unset bullet through ``_preflight_env`` and
  asserts every alarming word (``fail``, ``401``, ``missing``,
  ``unset``, ``error``, ``abort``) is absent from stdout. This is the
  hard gate.
- ``test_v035_api_key_check_uses_info_glyph_in_cli``: bullet line for
  ``api_key`` contains ``ℹ`` (U+2139), not ``⚠`` (U+26A0).
- ``test_preflight_env_api_key_check_unset`` updated: detail must be
  word-neutral, ``fix`` must be ``None``.

### Deliberately NOT changed

- We did not introduce a third severity tier (``"info"``) in the
  ``EnvCheck`` dataclass even though it was the natural fit. Reason:
  ``warning_summaries()`` filters ``severity == "warning"``, and the
  report banner / state persistence chain depends on this for audit.
  Reclassifying api_key as ``"info"`` would silently drop it from
  ``state.preflight_env_warnings`` — losing the audit trail. The
  cli-layer special-case is narrower and reversible.
- We did not touch model-capability warnings (``UNKNOWN`` model →
  ⚠). Those are *real* advisories an operator should see; they are
  not symptomatic of the false-error problem this release fixes.
- We did not change the abort behavior of any blocker check. doctor
  still aborts if ``ffmpeg`` / ``ffprobe`` / ``yt-dlp`` are missing or
  Python is too old.

## [0.3.4] — Chinese-caption fit & cn-compound bucket bridging (2026-05-26)

### Fixed

- **P1: ``_fuzzy_section_match`` adds 3-gram trigram fallback for Chinese
  compound tokens**. Stage 3 vision LLM emits ``recommended_section``
  *before* stage 5 generates the real outline, so its phrasing rarely
  matches outline chapter titles word-for-word. Pre-v0.3.4, "武汉智能工厂"
  vs "八、ACME智能工厂" failed token / substring match → frame went into
  the unassigned bucket → draft LLM placed it wherever it wanted (one
  of the root causes of "wrong-section" complaints). v0.3.4 adds a
  trigram overlap path: ≥ 2 shared 3-grams (e.g. 智能工 + 能工厂) =
  match. Threshold 2 (not 1) keeps single-trigram noise out (e.g.
  "智能" alone appears in ten unrelated chapters). Cn-eng synonym
  pairs ("搜索体验" ↔ "Search") are intentionally NOT bridged — that
  needs semantic understanding, not n-gram tricks; future P1-a work
  will solve it via a stage-5 re-bucket LLM call if the heuristic
  proves insufficient.

- **P3: ``check_image_section_fit`` (5.5.4) now judges Chinese-dense
  captions instead of silently passing them**. Pre-v0.3.4 gate required
  ``len(cap_tokens) >= 4`` where tokens come from whitespace/punctuation
  splitting. Real Chinese caption "ACME家电智能工厂介绍武汉装配线片段"
  splits to **1** token → never reached the mismatch decision → fit
  always passed regardless of content. Now the gate also accepts
  ``len(cap_trigrams) >= 8`` (≈ 10 Chinese chars), and trigram
  overlap with ``section_ngrams`` counts as section-signal. Mismatch
  diagnostic dict now carries ``trigram_hits`` / ``body_trigram_hits``
  for retry-directive informativeness. v0.3.3 P5 already wired 5.5.4
  into the retry loop; v0.3.4 P3 fixes its blind-spot for Chinese
  reports specifically.

### Notes

- **P2 deliberately NOT fixed in this release**. Re-reading the code
  showed P2 (draft LLM ignoring per-chapter buckets) is already covered
  by the v0.3.3 stack: 5.5.4b ``check_bucket_placement`` is a HARD gate,
  cross-bucket placement triggers stage 5 retry, and the prompt already
  instructs strict bucket adherence. Adding more prompt warnings would
  be cargo-cult.

- **Scope discipline**: this release applies the "diminishing returns"
  rule. Found while reading: P2 was non-issue; P1 has a "treat the
  symptom (fuzzy improve) vs treat the disease (LLM re-bucket with real
  outline)" choice, picked the symptom route because the disease route
  costs +1 LLM call per run. If real-world v0.3.4 runs still produce
  wrong-section complaints at meaningful rate, escalate to P1-a in
  v0.3.5; otherwise let it be.

- **Still not fixed (queued for v0.3.5+)**: S2 score_image silent
  failures, S4 frame→timestamp drift on VFR sources, F3 single-shot
  retry policy, F5 phash threshold. None are crash-class; all are
  margin-quality issues for specific sources (Bilibili VFR, dense PPT
  animation). U1–U4 (LLM stochasticity, hallucination, RPM throttling,
  silent model upgrades) remain fundamental and unfixable.

## [0.3.3] — Three-flow robustness pass: extract / draft / verify shock-absorbers (2026-05-26)

### Fixed

- **F1: ``LLMClient.parse_json`` falls back to ``json_repair`` on
  ``JSONDecodeError``**. Vision LLMs sporadically emit truncated output,
  trailing commas, unquoted keys, or extra prose around the payload.
  Pre-v0.3.3, any of these crashed the *entire* batch in stage 3
  (≈ 8 frames lost per incident, observed roughly 1 in 10 runs at
  ``BATCH_SIZE=10``). The fallback recovers in 9/9 typical corruption
  classes (truncated, trailing comma, unquoted keys, mixed quotes,
  fenced markdown, prefix prose, suffix prose, mid-string truncation,
  bare list). Well-formed JSON skips the repair path entirely (zero
  overhead on the happy path); a ``LLMClient._json_repair_invocations``
  counter exposes how often the fallback fires for monitoring. The
  earlier (be837c6 → b4162bb) attempt was reverted because it was
  bundled with a count-floor regression and a stale-frames-dir lookup
  hack; v0.3.3 ships only the fallback in isolation.

- **F2: stage 3 batch merge no longer crashes on schema-malformed
  vision-LLM output**. ``info_density: "high"`` (string instead of
  float), bare lists at the top level, non-dict entries inside
  ``selected_frames``, and non-string filenames now coerce defensively
  with the original default values. Each coercion appends a one-line
  diagnostic to ``state.runtime_warnings`` (deduped, capped at 10) and
  surfaces in the report banner. Before: any single bad-type field
  raised ``ValueError`` and dropped the whole batch.

- **F4: caption_verify (5.5.2) excludes rescue frames from the sample**.
  Rescue frames carry placeholder captions like ``[补救入选] 来自 ...``
  which the vision LLM deterministically marks as ``wrong``, inflating
  ``caption_verify_wrong_count`` past tolerance and triggering a stage 3
  retry that promotes more rescue frames — an unwinnable loop. Now
  ``verify_captions`` samples up to 10 non-rescue frames first; rescue
  frames only fill in if the non-rescue pool is too small. Rescue
  frames retain the ``[补救入选]`` prefix in the report so readers see
  the disclaimer; the optional Tier-C "re-vision rescue captions" path
  was rejected as low-yield (rescue frames *are* low-info-density by
  definition; a second LLM look-back rarely produces a discriminating
  caption and adds 0.05–0.15 USD per run).

- **P5: 5.5.4 image-section-fit heuristic now feeds the retry decision
  instead of being a console-only warning**. Previously, an image of
  "Pixel Halo" placed inside ``## 五、Search`` would print a yellow
  ``[5.5.4] image-section fit: 1 likely mismatches`` line and ship the
  report with ``quality_passed=True``. v0.3.3 writes
  ``state.image_section_fit_passed`` and
  ``state.image_section_fit_mismatch_count``; mismatch count above
  ``M.EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX`` (default 3, ≈ 8.5% of
  35 frames) now appears in ``_collect_draft_failures`` and triggers a
  stage 5 retry (the LLM rewrites with stricter section-fit prompting).
  Threshold deliberately wide because the underlying token-overlap
  heuristic over-fires on Chinese compound headings; tighter token
  splitting is queued for v0.3.4 (P3).

- **F6: ``EXTRACT_FINAL_COUNT_MAX`` raised 50 → 65**. The 50 cap left
  no headroom: rescue + perceptual-hash dedupe occasionally landed at
  33–34 frames, below the 35 floor, tripping ``ExtractFloorError`` and
  forcing an unnecessary retry on what was otherwise a healthy run.
  65 gives 30 frames of headroom for dedupe collapse without changing
  the floor (still 35). Math sanity: 14 chapters × per-section ≥ 1 +
  2 mainline × extra-per-mainline 3 = 20 absolute lower bound; the
  ceiling stays well above any methodology-imposed floor.

### Added

- **New methodology constant**:
  ``EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX = 3`` (P5).
- **New state fields**: ``image_section_fit_passed: bool = True``,
  ``image_section_fit_mismatch_count: int = 0`` (P5).
- **New runtime dependency**: ``json-repair >= 0.30`` (F1; pure-python,
  no native deps).
- **12 new regression tests** covering all five fixes above, including
  a guard test that locks ``json-repair`` as a *runtime* dep (not a
  dev/optional dep) so installations from PyPI carry the fallback.

### Notes

- Three-flow scope reminder: this release fixes 5 of the 14 audit
  findings spanning截图 (S1–S4) / 筛图 (F1–F7) / 配图 (P1–P5). The
  remaining items (S2 score_image silent failures, S4 frame→timestamp
  drift on variable-frame-rate sources, F3 single-shot retry policy,
  F5 phash threshold, P1/P2 bucket fuzzy-match weakness, P3 Chinese
  token-split miscalibration) are documented as known limitations and
  queued for v0.3.4. None of those are crash-class; they degrade
  output quality at the margins. Items U1–U4 (LLM stochasticity,
  caption hallucination, RPM throttling, silent model upgrades) are
  fundamental to LLM-driven pipelines and not fixable in code.

- The user-visible promise this release does *not* make: zero errors.
  No LLM-driven system can promise that. This release reduces the
  "single bad LLM batch kills a whole stage" failure mode from
  observable-per-run to rare-tail.

## [0.3.2] — Restore "in-window model works without re-entering api-key" (2026-05-26)

### Fixed

- **LLMClient no longer hard-fails when ``cfg.api_key_env`` is unset**.
  v0.3.0 introduced the ``_OpenAIBackend`` / ``_AnthropicBackend`` split;
  both backends ``raise RuntimeError`` in ``__init__`` if the configured
  env var was missing. This broke every workflow where the LLM SDK is
  expected to find the key on its own — corporate gateways injecting
  auth via headers, agent-host proxies (opencode / claude-desktop /
  cursor) routing traffic through internal endpoints, SDKs reading
  from keychain or alternate env vars (``ANTHROPIC_API_KEY`` for the
  anthropic-native backend), etc. v0.3.2 restores the v0.2.4 contract:
  print an advisory note and let the SDK own resolution. The first LLM
  call surfaces a real 401 with a provider-authored message if no key
  is reachable. Aligns with the v0.2.5.1 hotfix that did the same for
  ``preflight_env.check_api_key``.

- **Preflight ``UNKNOWN`` model is now an advisory warning, not a hard
  abort**. v0.2.4 made unverified models a blocker to prevent silent
  garbage from text-only models on vision stages. The implementation
  side-effect: gateway-prefixed model IDs like
  ``your-company-llm-anthropic/your-vendor/claude-opus-4-7`` were routinely
  hitting ``UNKNOWN`` and aborting the run, even though the substring
  matcher in ``preflight.py`` already classifies them correctly as
  VERIFIED. v0.3.2 splits the two cases: ``KNOWN_TEXT_ONLY`` stays a
  hard abort (the silent-fail risk is real), but ``UNKNOWN`` proceeds
  with a yellow advisory and is surfaced in the final quality banner.
  This restores the workable v0.2.3-era behaviour for agent-host
  setups that wrap models with routing prefixes.

- **Test isolation hardening**: ``test_draft_tier_default_is_strict``
  now sets ``HOME`` to a tmp_path so it asserts the *built-in default*
  rather than whatever ``~/.config/keynote-recap/config.yaml`` the
  developer happens to have. Pre-existing flake unrelated to v0.3.2
  feature work but surfaced during this release's full-suite run.

### Tests

- 4 new regression tests in ``tests/test_smoke.py``:
  - ``test_v032_llm_client_does_not_raise_when_api_key_env_unset``
  - ``test_v032_llm_client_anthropic_backend_does_not_raise_when_unset``
  - ``test_v032_known_text_only_still_hard_aborts``
  - ``test_v032_preflight_recognises_gateway_prefixed_models``
- 1 test renamed and re-asserted:
  ``test_preflight_models_unknown_blocks`` →
  ``test_preflight_models_unknown_warns_but_proceeds``.
- Suite total: 180 → 194 (+14 net for v0.3.2).

### Notes

- This release does NOT touch image-quality gates, retry orchestration,
  or any v0.3.1 contract. It is purely a model/env-stability hotfix.
- Default models in ``config.py`` (``claude-sonnet-4`` / ``claude-opus-4``
  / ``gpt-4o-mini`` / ``gemini-2.5-pro``) remain unchanged; if the
  user's gateway 404s on bare names, ``--llm-all`` / ``KEYNOTE_RECAP_MODEL_ALL``
  / ``llm.models.*`` in config.yaml still work as before.

## [0.3.1] — Image-quality hard gates + retry orchestration fix (2026-05-26)

### Added

- **Hard image-quality floor at stage 3 exit** (group A). Stage 3 now
  raises ``ExtractFloorError`` if the post-filter selected_frames pool
  fails any of: total count ≥ 35 (was an advisory 30), info_density
  ≥ 0.70 (frames below the floor are dropped before the count check),
  live ratio ≥ 50% (hard abort threshold; prompt still targets ≥ 70%
  as soft goal). Triggers extract retry with a directive prompt. The
  ``rescue`` path now also defaults rescued frames to info_density
  0.70 so they survive the new floor.

- **Per-section / per-mainline image-floor gate (5.5.1b)** (A5/A6).
  After 5.5.1 chapter coverage, verify checks: every chapter has ≥ 1
  image, and the two transcript-derived "mainline" chapters have ≥ 4
  images each. Failures enter ``_collect_extract_failures`` and trigger
  a stage-3 retry with the per-section floor reason fed into the prompt.

- **Caption-verify wrong count → retry trigger (5.5.2)** (B1/B2).
  ``State.caption_verify_wrong_count`` now persists the 5.5.2 sample-10
  wrong count; ``> EXTRACT_CAPTION_VERIFY_WRONG_MAX`` (default 1) enters
  the extract failure list with a "describe ONLY what is literally
  visible" retry directive. v0.3.0 silently logged 3 wrong captions
  per run and proceeded; v0.3.1 retries.

- **Retry guidance directive** (C3). New ``_build_retry_directive``
  helper renders the prior round's failure list into a [RETRY GUIDANCE]
  block injected at the top of every stage-3 batch user_text. Failures
  carry per-category fix instructions (image-mix → more live frames;
  caption-verify → only literal pixels; per-section floor → spread
  across timeline; etc.). Retry attempts are no longer blind.

- **alt_short field on SelectedFrame** (D2). Short alt text (≤ 25
  Chinese chars) for screen readers and concise listings; populated
  by stage-3 vision LLM via the prompts/03 schema. Render falls back
  to caption[:60] when alt_short is empty (legacy frames).

- **Briefing-style first-sentence rule (strict §10)** (D1). prompts/05
  now forbids 词典释义体, 仪式开场, 议程预告 in chapter openings;
  requires 数字开打 / 时间开打 / 判断开打 mode.

- **Parallel-info → table hard constraint (strict §11)** (D3). When
  3+ products / 3+ versions / 3+ price tiers / 3+ time-series points
  appear, must use a markdown table, not 散文罗列.

### Changed

- **``State.quality_passed`` default flipped True → False** (C2 root
  cause). Any early-return path (retry exception, ``--start-stage 6``
  skipping verify, pipeline abort) now leaves the field False and
  ``render._compute_banner`` synthesizes a red banner with "Quality
  gate did not run" — silent unsigned reports are blocked. Real bug
  from your-company 2026-05-20: state had 5 gates fail but quality_passed=True
  because the True default leaked when final assessment never executed.

- **5.5.4 image-section fit considers ### subsections** (B3). The
  static keyword-overlap heuristic now tracks the most-recent ###
  subsection title within each chapter and includes its tokens (plus
  3-char sliding-window n-grams of compound tokens) in the hit pool.
  Real bug: factory frames inside ``### 8.3 制造底气—武汉智能工厂``
  were falsely flagged because the parent ``## 八、ACME空调`` chapter
  title doesn't contain 工厂.

- **Extract methodology constants centralized** (E1/E2/E3). New
  exports in ``methodology.py``: ``EXTRACT_FINAL_COUNT_MIN`` (35,
  was 30 hard-coded inconsistently), ``EXTRACT_LIVE_RATIO_MIN`` (0.50,
  hard-floor distinct from prompt's 0.70 soft target),
  ``EXTRACT_INFO_DENSITY_MIN`` (0.70), ``EXTRACT_PER_SECTION_MIN`` (1),
  ``EXTRACT_PER_MAINLINE_MIN`` (4), ``EXTRACT_CAPTION_VERIFY_WRONG_MAX``
  (1).

### Fixed

- v0.3.0 retry orchestration silently published a 22-image / 5-failed-
  gate / quality_passed=True report from the your-company 2026-05-20 run.
  Combined effect of the changes above closes 19 audit findings
  documented in ``docs/plans/2026-05-26-v031-image-quality-hard-gates.md``.

- ``state.SelectedFrame.source`` Literal now includes
  ``frame_extract_rescue`` so rescue path doesn't trigger pydantic
  ValidationError on retry.

## [0.3.0] — Anthropic-native provider support (2026-05-25)

### Added

- **Native Anthropic Messages API support.** `LLMConfig.provider` is now
  honored at the client level; setting `provider: anthropic-native`
  routes all stages through the `anthropic` SDK and the `/messages`
  endpoint instead of OpenAI's `/chat/completions`. This unblocks users
  whose corporate LLM gateway exposes Claude via the native Anthropic
  protocol (e.g. `your-vendor/claude-sonnet-4-6` model IDs reachable only
  via `/anthropic/v1/messages`). Vision payloads are converted to
  Anthropic's content-block format
  (`{type:"image", source:{type:"base64", media_type, data}}`).

- **Anthropic JSON-mode workaround.** Anthropic Messages has no
  ``response_format`` parameter. When the caller passes
  ``json_mode=True``, the backend appends a strict-JSON directive to
  the system prompt; the existing ``LLMClient.parse_json`` already
  strips markdown fences, so end-to-end behaviour matches OpenAI
  json_mode for the project's needs.

### Changed

- ``LLMClient`` is now a thin facade dispatching to ``_OpenAIBackend``
  or ``_AnthropicBackend`` based on ``cfg.llm.provider``. Public API
  (``chat`` / ``chat_with_images`` / ``parse_json`` signatures and
  return shapes) is byte-identical to v0.2.5.1; no callers in
  ``stages/*`` need changes.

- ``keynote-recap doctor`` now prints the active provider and base_url
  so config errors surface immediately.

- ``anthropic`` dependency pinned to ``>=0.40`` (was ``>=0.30``).

### Tests

- 8 new ``test_v030_anthropic_*`` tests covering: provider routing,
  default backward compat, text chat, vision payload format, json_mode
  directive injection, system role lifting, OpenAI provider regression,
  and PNG/JPEG media_type detection. All mocked — no token spend.

- Total: 132 passing (was 124 in v0.2.5.1).

### Acknowledged limitations

- Stage 3 heuristic-scorer fallback path (when ALL vision batches fail)
  has a pre-existing pydantic schema bug: ``SelectedFrame.source``
  literal does not accept the value the fallback fills in. v0.3.0 does
  NOT fix this; tracked for v0.3.1. With v0.3.0's anthropic provider
  working correctly, the fallback path is reached much less frequently.

- Anthropic prompt-caching tokens
  (``cache_creation_input_tokens`` / ``cache_read_input_tokens`` in
  usage) are not surfaced to cost_tracker. Tracked for v0.3.1.

## [0.2.5.1] — Hotfix: api_key check is advisory, not blocking (2026-05-25)

### Fixed

- **`preflight_env.check_api_key` severity downgraded from `blocker` to
  `warning`.** v0.2.5 silently upgraded "API key env var unset" to a hard
  abort (un-declared BREAKING) which broke workflows where the LLM SDK
  reaches its endpoint via a non-standard env var — corporate gateways,
  agent-host injected proxies (e.g. opencode routing `claude-sonnet-4-6`
  through an internal endpoint without populating the calling shell's
  `OPENAI_API_KEY`). The recap pipeline aborted at preflight rather than
  letting stage 1 (download) start. Restored to the v0.2.4 behaviour:
  unset key prints a yellow `⚠` warning and the run continues; the first
  LLM call surfaces a real 401 from the provider when the key is
  actually invalid. Model-capability checks (`_preflight_models`) remain
  hard aborts — text-only models on vision stages still silently produce
  garbage and that signal is worth preserving.

### Tests

- `test_preflight_env_api_key_check_unset` updated: asserts
  `severity == "warning"` (was `"blocker"` in v0.2.5).
- New `test_v0251_preflight_env_does_not_abort_when_only_api_key_missing`:
  end-to-end assertion that `cli._preflight_env` returns a warnings list
  (not `None`) when `OPENAI_API_KEY` is unset and every tool check
  passes. This regression test guards against re-introducing the v0.2.5
  abort path.

### Acknowledged limitations

- This hotfix does not solve "agent runs in an env where the LLM gateway
  isn't an OpenAI-compatible endpoint at all". For that, the user still
  needs to point `llm.base_url` and `llm.api_key_env` at a reachable
  endpoint via `~/.config/keynote-recap/config.yaml` (or shell env). The
  fix only restores the v0.2.4 contract that preflight does not gate on
  the literal presence of the env var.

## [0.2.5] — Internalized defense layer (2026-05-25)

The threat model assumed by v0.2.4 M9 was "agent calls `keynote-recap
recap` but cuts corners inside the pipeline" — text-only models, skipped
stages, post-hoc edits to `report.md`. A real-world session on
2026-05-25 (opencode + sonnet 4.6) demonstrated a deeper failure mode
M9 does not cover: the agent **never invoked `keynote-recap` at all**.
It read `methodology/*.md` as a writing checklist, then hand-wrote a
4.8 MB HTML "report" — no `<meta name="generator">`, no
`content-sha256`, no `.recap-stamp`, arbitrary file path on Desktop,
forbidden 📌 emoji, headings as `## 1、` instead of `## 一、`. M9
detected nothing because M9 only runs when the project runs.

v0.2.5 internalizes defense into the project itself, on the principle
that **the primary defense layer must work even when the agent ignores
all project documentation**. Three layers: a hard-core directive
`AGENTS.md` (cooperative-agent channel, best-effort), a sticky orange
top banner injected into every real `report.html` (forensic visual
delta, primary defense), and a `verify` subcommand that returns binary
OK / FAIL on any HTML or markdown (validation channel, deterministic).
A `recap-and-verify` wrapper is mandated as the single canonical
agent-facing command so non-compliance becomes a one-line `verify`
check away from being detected.

### Added

- **`AGENTS.md`** (project root, new file). Hard-core directive style
  agent guide read by default by opencode / Cursor / Claude Code.
  Four sections: (1) "Are you in the right place?" yes/no for agents
  considering integration; (2) "The one rule" — call
  `keynote-recap recap-and-verify`, do not improvise; (3) "How to
  actually run it" — concrete commands, version gate, error handling
  that does not include "regenerate via LLM"; (4) "Your output is not
  the report" — explicit boundary that the agent's role is to invoke
  the tool and report results, not to author the report. Documents the
  2026-05-25 hand-crafted-HTML failure mode as the concrete example
  this file exists to prevent.
- **`keynote-recap verify <file>`** subcommand. Auto-detects `.html`
  vs `.md`. Validation chain: file readable → (html only) generator
  meta + `.recap-banner` + `.recap-stamp` present → frontmatter
  parseable (yaml-narrow per v0.2.4) → recomputed body sha matches
  `content-sha256` → `keynote-recap-version` field present. Output:
  one-line `OK: keynote-recap v0.2.5 · sha:abc12345 · model:...`
  (exit 0) or `FAIL: <reason>` (exit 1). Pre-v0.2.5 HTML returns the
  friendly degraded message `FAIL: pre-v0.2.5 HTML, regenerate with
  v0.2.5+`.
- **`keynote-recap recap-and-verify <url> [recap_args...]`**
  subcommand. Thin wrapper: invoke `recap`; on success, locate
  `report.html` and run `verify`. `recap` failure → propagate exit
  code; `verify` failure → exit 1. This is the single canonical
  agent-facing command mandated by `AGENTS.md`. Removes "produce md,
  render html, verify them" as three separate agent calls (each a
  chance to drift) and guarantees that any session ending with
  `recap-and-verify` exit 0 has a verified, signed, banner'd HTML.
- **HTML top banner** (sticky). Real `report.html` now ships with a
  `<div class="recap-banner">` injected at the top of `<body>`.
  Sticky (`position: sticky; top: 0; z-index: 9999`) so it stays in
  view at any scroll position — removes the "agent crops the first
  100px" attack. 6px solid `#ff6900` color bar over a 38-44px main
  body, monospace one-liner: `keynote-recap v0.2.5 · sha:abc12345 ·
  model:claude-opus-4 · stages:6/6 · verified ✓`. Three-tone color
  modulation by `stages-skipped` integrity state: healthy (orange bar
  + `#fff7ed` bg) / half-run (yellow) / unverified — i.e. stage 1 or
  stage 4 skipped (red). **No close button, no fold, no hide
  affordance**: a closeable banner is a hand-craftable banner.
  Designed so any hand-written HTML lacking it (or carrying a
  wrong-color / wrong-height / non-sticky imitation) is visibly
  distinguishable on inspection. The v0.2.4 right-side `.recap-stamp`
  is **kept** as redundant defense — both must be present in real
  output.
- **`src/keynote_recap/verify.py`** (new module, ~281 lines). Pure
  functions: `verify_file(path)`, `verify_html_text(text)`,
  `verify_md_text(text)`, returning `VerifyResult(ok, summary,
  file_kind, checks)`. No CLI imports; reusable from tests and from
  future host-side integrations (opencode hooks, Cursor commands).

### Changed

- `_write_html` (`stages/render.py`) now injects the
  `.recap-banner` element at the top of `<body>` based on
  frontmatter metadata. Affects both pipeline paths that emit HTML —
  `recap` stage 6 and `publish-html` — so re-rendering an existing
  signed `report.md` produces a banner'd output.
- `stages/render.py` CSS adds `.recap-banner` /
  `.recap-banner-half-run` / `.recap-banner-unverified` rules for the
  three integrity tones; print stylesheet keeps the banner inline at
  top of first page (same pattern v0.2.4 uses for `.recap-stamp`).
- `cli.py` module docstring updated to list the new `verify` and
  `recap-and-verify` subcommands; `recap-and-verify` is now described
  as the canonical entry point for agent-driven invocations.

### Tests

10 new tests (123 total, was 113):

- `test_v025_verify_html_with_valid_frontmatter_returns_ok`
- `test_v025_verify_html_with_tampered_body_returns_fail`
- `test_v025_verify_html_without_generator_meta_returns_fail`
- `test_v025_verify_html_without_recap_banner_returns_fail`
- `test_v025_verify_md_with_valid_frontmatter_returns_ok`
- `test_v025_verify_md_without_frontmatter_returns_fail`
- `test_v025_verify_nonexistent_file_returns_fail`
- `test_v025_render_writes_banner_at_body_top`
- `test_v025_verify_cli_exits_0_for_valid_md`
- `test_v025_verify_cli_exits_1_for_tampered_md`

### Migration

- v0.2.4.1 users: `git pull && pip install -e .` (or
  `pip install -U keynote-recap`). No code or config changes
  required.
- **Not a BREAKING release.** `recap` and `publish-html` behaviour is
  fully preserved; the only addition to existing paths is the banner
  div injected at the top of `<body>`. No flag removal, no schema
  change, no checkpoint reordering.
- v0.2.4-produced HTML files cannot be `verify`-ed — they predate the
  banner. `verify` returns the friendly degraded `FAIL: pre-v0.2.5
  HTML, regenerate with v0.2.5+` rather than a cryptic mismatch,
  pointing the user at the concrete fix (re-run `recap-and-verify` on
  the source URL with v0.2.5+).

### Acknowledged limitations

- keynote-recap is the *callee*, not a supervisor. It **cannot
  auto-rerun the agent**: when an agent skips the project entirely
  and hand-crafts HTML, this project is never loaded and has no entry
  point to "self-trigger" a re-run. Auto-rerun on verification failure
  must live at the agent-host layer (opencode hooks, Cursor commands,
  etc.) and is documented as a v0.2.6+ integration recipe, not project
  code.
- `verify` checks **structural integrity, not content quality**. A
  real keynote-recap output that produced poor content will still pass
  `verify`. Content quality is governed by the v0.2.4 M9 stage gates,
  not by this layer.
- `AGENTS.md` only helps cooperative agents. The L2 banner and L3
  `verify` layers do **not** depend on agent cooperation — that is
  the design point. An agent can still hand-craft HTML that includes
  a plausible-looking fake banner; the visual delta strategy assumes
  doing so well enough to fool a user is hard, not impossible. Users
  who want certainty must run `verify`.

---

## [0.2.4.1] — Bilibili subtitle cookie fallback (2026-05-25)

**Patch.** Fixes a long-standing bug in `_download_subtitles` where the
yt-dlp call had no `--cookies-from-browser` retry, while `_fetch_metadata`
and `_download_video` both did. Bilibili changed policy in 2024H2 to
require login for subtitle access; the first call returns `returncode=0`
but only delivers `danmaku.xml` (not a real subtitle file). Pre-v0.2.4
the missing transcript was silently swallowed and stage 2 captions
hallucinated content; v0.2.4's M9.2 hard-aborts on missing transcript,
which correctly stopped the pipeline but also exposed this bug as a
regression for Bilibili users whose previous reports "worked".

### Fixed

- `stages/download.py::_download_subtitles` now retries with
  `--cookies-from-browser chrome` when the first attempt produces no
  usable `.srt`/`.vtt` file. Detection is based on **file presence**, not
  yt-dlp returncode, since Bilibili returns 0 without delivering the
  subtitle. Mirrors the existing fallback pattern in `_fetch_metadata`
  (line 124-131) and `_download_video` (line 152-160).

### Tests

- 3 new tests (113 total, +3):
  - `test_v0241_subtitle_no_retry_when_first_attempt_succeeds` —
    youtube-style sites still work with one call, no cookie attempt.
  - `test_v0241_subtitle_retries_with_cookies_when_first_yields_no_file`
    — Bilibili-style "success but no file" triggers cookie retry and
    succeeds on the second call.
  - `test_v0241_subtitle_returns_empty_when_both_attempts_fail` — both
    failed → returns `("", "")` so M9.2 can route to abort message.

### Migration

- None. Patch release; `pip install -U keynote-recap` (or `git pull &&
  pip install -e .` for editable installs). No flag/API changes.

### Verified

- Ran end-to-end against `BV1DiLY6DEfj` (real Bilibili URL): first call
  prints `[yellow]No subtitle file found; retry with browser cookies...[/]`,
  second call retrieves a 266 KB `subtitle.ai-zh.srt` containing the
  actual transcript ("大家晚上好/欢迎大家参加今晚的发布会...").

---

## [0.2.4] — M9 anti-shortcut layer (2026-05-25)

**BREAKING.** Two flag removals + one new hard-fail mode. Motivated by
~5 confessed sessions of agents (Feishu Hal etc.) calling keynote-recap
and shortcutting the methodology: skipping stages, using text-only
models, compressing the report into a few sentences and labeling it
"keynote-recap official output". This release makes those shortcuts
either impossible or loudly self-incriminating.

### What changed

**M9.1. `--force` removed (BREAKING).**

Previously: text-only or unverified vision model → preflight warning,
override with `--force`. Now: hard abort, no override. To use a custom
model, submit a PR adding it to
`src/keynote_recap/preflight.py::_VERIFIED_VISION_MODELS` after
manually verifying it produces correct output on a small sample.

Reason: agents repeatedly slapped `--force` on text-only models and
shipped silent-garbage reports; users blamed the project.

**M9.2. Stage 1 transcript failure → hard pipeline abort (BREAKING).**

Previously: missing transcript → soft warning, pipeline continues to
stage 2/3/5/5.5 with empty transcript. Now: `RuntimeError` with three
copy-pasteable fix options:

```
yt-dlp --cookies-from-browser chrome <url> --write-auto-sub --skip-download
```

```
keynote-recap recap <url> --transcript-file ./manual.srt
```

Or try a different mirror / region. Without transcript the methodology
cannot run (stage 3 high-freq product check, stage 4 fact research,
stage 5 grounding all need it).

New flag: `--transcript-file <path>` accepts `.srt`, `.vtt`, or `.txt`
as the sanctioned escape hatch.

**M9.3. Stage 4 skipped or zero verified facts → red banner.**

Reuses v0.2.2 tri-color banner. Trigger condition: stage 4 in
`stages_skipped`, OR stage 4 ran but produced 0 verified facts. Red
banner text: "本报告未经事实查证。所有数据均从演讲画面文字抠出，
未经第三方信源核对…" Stage 1 skip → similar dedicated red banner.

This is distinct from the existing red banner ("project quality gate
failed"): there, methodology ran and the result failed checks; here,
methodology didn't run at all.

**M9.4. Mandatory integrity callout at top of report.md.**

Always emitted, two templates:

- Healthy: `> ✅ 本次 keynote-recap 完整运行` + stage list + model + citations
- Half-run: `> ⚠️ 本次 keynote-recap 部分运行` + skipped stages + reasons
  + can't-verify methodology items + model tier

Cannot be disabled. Agent compressing the report must confront this
callout. Keep it → exposes half-run state in published doc. Delete it
→ breaks sha verification (M9.5/M9.6). Honesty tax.

**M9.5. report.md auto-frontmatter.**

`stages/draft.py` writes report.md with leading YAML frontmatter:

```yaml
---
keynote-recap-version: 0.2.4
generated-at: 2026-05-25T19:00:00+08:00
content-sha256: <sha256 of body bytes after frontmatter>
source-url: https://...
stages-completed: [2, 3, 5, 5.5]
stages-skipped: [1, 4]
model-extract: your-company/mimo-v2.5
model-extract-tier: known_text_only
---
```

Hand-written narrow YAML parser (no third-party lib) — keeps schema
locked, avoids agent injecting arbitrary keys. New module
`src/keynote_recap/frontmatter.py`.

**M9.6. New command `keynote-recap publish-html <report.md>`.**

The only sanctioned path to re-render report.md → report.html.

Logic:
1. Read report.md, parse frontmatter
2. Compute body sha256, compare to `content-sha256` in frontmatter
3. Mismatch → abort with diagnostic ("report.md has been modified after
   keynote-recap wrote it…")
4. Match → render HTML

Agents that "summarize" or "rewrite" report.md cannot use this command
— sha mismatch will abort. Agents that hand-write HTML can — but their
output won't carry the M9.7 stamp.

**M9.7. HTML provenance stamp.**

`<head>`:
```html
<meta name="generator" content="keynote-recap 0.2.4">
<meta name="content-sha256" content="abc123def...">
```

Bottom-right floating element:
```
v0.2.4 · sha:abc123de · 模型:claude-opus-4
```

CSS positions it `bottom: 8px; right: 12px; opacity: 0.6` —
visible-but-unobtrusive. Print stylesheet repositions it to inline
flow so it survives print/PDF. Anyone receiving the HTML can verify
provenance in 1 second.

### Migration

For most users (verified models, working subtitle download): no action,
report.md just gains a YAML frontmatter at the top.

For users on text-only models: add the model to `_VERIFIED_VISION_MODELS`
via PR. No backdoor.

For users on Bilibili / region-locked sources: pass `--transcript-file`
with a manually-prepared `.srt`.

### Tests

110 tests passing (+14). New coverage: `--force` not in CLI args,
preflight no longer accepts `force=` kwarg, frontmatter roundtrip,
sha tamper detection, integrity callout templates (healthy/half-run),
red banner triggers (stage 1 skipped, stage 4 skipped), HTML stamp
present, publish-html sha gate, publish-html no-frontmatter rejection.

---

## [0.2.3] — M8 methodology lock + agent parallel layer (2026-05-25)

Two structural changes that protect output quality without expanding
surface area: (1) thirteen methodology parameters are now hard-coded in
a single `methodology` module so users cannot accidentally undo design
decisions through `config.yaml`, and (2) a project-controlled
concurrency layer that opportunistically parallelizes safe stages when
the model is verified.

### What changed

**M8.1. Methodology module (`methodology.py`, new)**

A single source of truth for parameters that are *design decisions*,
not user preferences. Replaces fields scattered across `config.py`:

- `EXTRACT_FINAL_COUNT_MIN` / `EXTRACT_FINAL_COUNT_MAX` — frame floor/ceiling
- `SEGMENT_CHUNK_COUNT` / `SEGMENT_CHUNK_FLOOR` — chunk policy
- `RESEARCH_MAX_QUERIES` / `RESEARCH_MAX_WEBFETCH` — fact-check budgets
- `DRAFT_*` minimum-quality thresholds
- `PIPELINE_CHECKPOINTS` — the 7-stage commitment

Stages now read `M.X` instead of `cfg.X`. Users cannot tune these via
yaml or CLI; the only sanctioned model-quality lever remains
`draft.tier`.

**M8.2. Config slimming (`config.py`)**

Removed (fields ignored if found in old yaml):
- `frame_filter` (entire section)
- `draft.min_images` / `draft.max_images` (kept `draft.tier`)
- `stages.checkpoints`
- `search.max_queries` / `search.max_webfetch`

`write_sample_config` yaml template synced — only sanctioned-tunable
keys remain.

**M8.3. Agent parallel layer (`methodology.py`, `llm_client.py`)**

New `run_parallel(items, work, *, parallel)` helper using
`ThreadPoolExecutor` with order-preserving results. Concurrency is
project-controlled via `parallel_for_stage(stage, model_tier)`:

- Verified multimodal model + eligible stage → 4 concurrent calls
- Any other tier OR ineligible stage → 1 (sequential)

In v0.2.3 only the `extract` stage is eligible (8-frame batches are
trivially independent). `research` is intentionally NOT eligible —
its `fetch_count` budget and citation-balance heuristic are a sequential
state machine; parallelization is planned for v0.2.4 with a
fetch-then-decide refactor.

Users cannot override concurrency. No `--parallel` flag, no yaml field.
Rationale: it's a methodology decision tied to verified-model RPM
limits, not a user preference.

**M8.4. Surfaced in banner + report**

- Stage banner now shows an `agent: parallel 4` or
  `agent: sequential (model tier 'unknown' not eligible)` line so
  users can see what decision the project made for them.
- Responsibility-section table in the final report adds an
  "Agent 并发" column listing the per-stage decision.
- `state.stage_parallelism: dict[str, int]` records decisions for
  rendering and debugging.

### Migration

No action required. Old yaml files keep working; ignored fields are
silently dropped. To regenerate a clean template:

```bash
keynote-recap doctor --write-config ./config.yaml
```

### Tests

96 tests passing (+8). New coverage:

- All 13 methodology constants exposed
- `parallel_for_stage` three-tier logic (verified / unverified /
  ineligible-stage)
- `run_parallel` order preservation, sequential-when-1, exception
  propagation
- `state.stage_parallelism` field exists
- Removed config knobs no longer in `Config.model_fields`
- yaml template emits no methodology-locked keys

---

## [0.2.2] — M7 expectation management (2026-05-25)

Focused fix for "user can't tell project-design problems apart from
environment / model problems". When a colleague's machine lacks ffmpeg, or
they swap in a custom multimodal model that's weaker than the project's
verified set, the report quality drops silently and users blame the project.
This release surfaces all three failure modes loudly: at preflight, at every
stage banner, and in the final report.

### What changed

**D1. Preflight environment check (`preflight_env.py`, new module)**

Before any work begins, runs 6 checks and aborts with a copy-pastable fix
hint on any blocker:

- Python ≥ 3.10
- `ffmpeg` and `ffprobe` on PATH (with version)
- `yt-dlp` on PATH or installed as Python module
- `shutil.disk_usage(output_dir).free ≥ 5 GB` (warning, not blocker)
- The configured `cfg.llm.api_key_env` env var is set and ≥ 20 chars

Wired into both `recap` and `doctor` commands.

**D2. Preflight model check upgraded (`cli.py`)**

Previously: vision stage using an UNKNOWN model → soft warning, run
continues. Now: UNKNOWN model on a vision stage (extract / verify) is
treated like KNOWN_TEXT_ONLY — abort unless `--force`. Reason: too many
silent-quality-loss reports from users running the project against a
custom in-house model that turned out to lack image support.

**D3. Stage banner box (`pipeline.py`)**

Before each stage, prints a 4-line panel:

    ┌─ stage 3 / extract ────────────────────────┐
    │ model:  claude-opus-4 (verified multimodal)│
    │ task:   vision LLM 3-principle filter      │
    │ guards: 5.5.6 live ratio, 5.5.7 topic cov  │
    └────────────────────────────────────────────┘

Persists `models_used` and `model_tiers` into `state` so the final report
can reference them.

**D4. Runtime capability probes (`pipeline.py`)**

After stage 3: if `len(selected_frames) < 5`, append warning "vision model
may have weak image understanding" to `state.runtime_warnings`.

After stage 4: if `facts_to_verify` is non-empty but `verified_facts` is
empty, append warning "research model may not support web tools".

These catch silent-failure cases that the prompt-level capability probe
can't detect — the model technically returned output, just very thin.

**D5. Tri-color quality banner + responsibility section (`render.py`)**

Banner colors:

- **Red** — project quality gate failed after retry. Project's responsibility.
- **Yellow** — env / model preflight or runtime probe surfaced concerns.
  NOT a project quality issue; user-environment-driven.
- **None** — healthy run.

Red takes precedence when both apply. Whenever a banner is shown, an end-
of-report `<section class="responsibility">` is appended with:

- a per-stage table of model + capability tier actually used in this run
- bullet list of what the project takes responsibility for (methodology,
  bucket placement, lint, source allowlist…)
- bullet list of what the project does **not** take responsibility for
  (user environment, model self-direction, hallucination beyond verified
  facts, model vision precision ceiling, source video quality)
- one-line re-run command with stronger model + `--start-stage 5`

Healthy runs (no banner) get a clean report with no responsibility section.

**D6. State extension (`state.py`)**

Added: `preflight_env_warnings`, `preflight_model_warnings`,
`runtime_warnings`, `models_used`, `model_tiers`.

### Tests

88 passing (74 → 88, +14): preflight_env unit checks for python / ffmpeg /
api_key (set / unset / too-short); render banner trinity (red / yellow /
none); red-takes-precedence-over-yellow; runtime probes for low-frame-count
and zero-verified-facts; preflight_models unknown-blocks-without-force.

### Migration from 0.2.1

No state.json schema break — new fields default to empty. Users on 0.2.1
keep working. Anyone using a custom non-mainstream LLM may now hit the
preflight block; pass `--force` once to confirm, and the report will carry
a yellow banner explaining the limitation.

---

## [0.2.1] — M6 image pipeline overhaul (2026-05-25)

Targeted fix for the failure mode where reports came out with too few images
and/or all images being marketing renders instead of live keynote frames.
This release rewrites the image pipeline as a four-stage data contract with
hard gates at every step.

### What changed

- **D1 — deterministic image-to-section bucket placement**
  ([draft.py](src/keynote_recap/stages/draft.py)): frames are bucketed by
  `recommended_section` BEFORE the draft LLM sees them. Each chapter gets a
  per-bucket frame list with the rule "use any subset within this bucket;
  cross-bucket use is forbidden". Image placement becomes a constrained
  pick-from-list problem instead of a generative guess.

- **D2 — live vs. inserted-render classification**
  ([prompts/03-extract-vision-filter.md](prompts/03-extract-vision-filter.md),
  [extract.py](src/keynote_recap/stages/extract.py)): stage 3 vision LLM now
  emits an `is_live` field per frame; non-live frames get `（插播官方渲染）`
  prefix in caption. Verify gate 5.5.6 enforces `live ratio ≥ 70%` and
  `total frames ≥ 25` — failure triggers stage 3 retry.

- **D3 — per-chunk floor in stage 2 sampling**
  ([segment.py](src/keynote_recap/stages/segment.py)): video is split into
  12 time chunks; each chunk is guaranteed at least 3 candidate frames
  regardless of absolute score. Prevents whole transcript stretches from
  being dropped just because their PIL scores are uniformly low.

- **D4 — topic coverage gate**
  ([verify.py](src/keynote_recap/stages/verify.py)): stage 5.5.7 ensures
  every product/protocol mentioned ≥5× in the transcript appears in at
  least one selected frame's caption / recommended_section /
  what_can_be_read. Failure triggers stage 3 retry.

- **Pipeline retry policy split into two tiers**
  ([pipeline.py](src/keynote_recap/pipeline.py)): extract-stage failures
  (image mix / topic coverage) re-run from stage 3; draft-stage failures
  (lint / placeholder / bucket placement / coverage / structure) re-run
  only stage 5. Each tier retries at most once.

- **5.5.4b deterministic bucket-placement check**
  ([verify.py](src/keynote_recap/stages/verify.py)): hard gate verifying
  the rendered report respected the per-chapter buckets from D1.

### New verify gates

| Gate | Failure handling |
|---|---|
| 5.5.4b bucket placement | hard error → stage 5 retry |
| 5.5.6 image source mix  | hard error → stage 3 retry |
| 5.5.7 topic coverage    | hard error → stage 3 retry |

### Tests

74 tests passing (was 58 pre-M6). 16 new tests cover D1/D2/D3/D4
individually plus an end-to-end regression test for the user-reported
"8 frames all marketing renders" failure that motivated this release.

### Migration notes

- `state.json` schema added 4 fields (`is_live` and `what_can_be_read` on
  `SelectedFrame`; `bucket_placement_passed`, `image_mix_passed`,
  `topic_coverage_passed`, `extract_retry_count` on `State`). Pydantic
  defaults make old state files load without modification.
- No CLI flag changes. The new gates run by default in strict tier.

## [0.2.0] — M5 hard quality gate + M4 small-model support (2026-05-22)

Major release combining two work streams:

1. **M5 (this commit)**: methodology rules become code-enforced contract,
   not LLM suggestion. Default tier `standard` → `strict`; pipeline retries
   draft once on any rule violation; report carries a yellow warning banner
   when quality gate fails after retry.
2. **M4 (previous batch)**: small-model support — vision capability probe,
   `doctor` subcommand, `--llm-all` flag, draft prompt tiers, vendor presets.

### Added — M5 (hard quality gate)

Rationale: 3 real user-feedback docx files revealed the LLM ignoring
prompt-level rules — invented placeholder filenames (`frame_gt_01.jpg`),
missing `**核心判断**：`, forbidden phrases (`总而言之`, `显著`,
`不仅仅`). Prompt-only constraints rely on LLM self-discipline; this
release makes them code-enforced contracts.

#### Default tier flipped to `strict`

- `config.py`: `DraftConfig.tier` default `standard` → `strict`. Methodology
  rules are now hard contract: ban-word list active, ≥ 8 citations,
  ≥ 8 table rows, every chapter must have `**核心判断**：`, callout block
  required, `## 信源说明` + `## 一点观察` mandatory.
- Users on weaker LLMs should pass `--tier easy` or `--tier standard`
  rather than seeing low-quality output silently published.
- `--tier` CLI help text and `cli.py` `recap` command updated.

#### 4 hard-fail flags + retry-once mechanism

- `state.py`: 5 new persisted fields:
  - `placeholder_detected: bool` (5.5.0 hard gate)
  - `lint_hard_failed: bool` (5.5.3 L1 hard gate)
  - `structure_check_passed: bool` (5.5.5 hard gate)
  - `draft_retry_count: int`
  - `final_quality_warnings: list[str]`, `quality_passed: bool`
- `stages/verify.py`:
  - 5.5.0 missing filename now sets `state.placeholder_detected`.
  - 5.5.3 L1 lint errors now set `state.lint_hard_failed`.
  - L1 errors print line/rule/found context to console for debug.
- `pipeline.py`:
  - New `_collect_quality_failures()` helper inspects 4 flags and
    returns a human-readable issue list.
  - After stage 5.5: if any hard gate fails AND `draft_retry_count == 0`,
    rewind `last_completed_stage` to 4.0 and re-run draft + verify once.
  - If retry still fails, set `quality_passed=False` and stash the
    issue list in `final_quality_warnings`. Pipeline continues to
    stage 6 render rather than crashing.

#### Yellow warning banner on quality fail

- `stages/render.py`: emits a `<div class="quality-banner">` above the
  body when `quality_passed=False`, listing each failed gate and
  suggesting a stronger model or `--tier easy`. Light + dark CSS theme.
- New `_escape()` helper for safe HTML in banner text.

#### Draft prompt: placeholder counter-examples + self-check

- `stages/draft.py`:
  - **Bug fix (root cause of `test-opencode.docx` failure)**:
    `_build_user_for_body` was reconstructing `frame_NNN.jpg` from
    `f.filename.split("_")[1]`, which dropped the `.jpg` suffix and
    confused the LLM into inventing semantic names like `frame_gt_01.jpg`.
    Filenames are now passed verbatim from `f.filename`.
  - User prompt now includes 3 explicit `❌` counter-examples
    (`frame_gt_01.jpg`, `01-spark-intro.jpg`, `frame_intro.jpg`) and a
    `✅` example using the first real filename from `selected_frames`.
  - Added `⚠️ 输出前自检` step instructing the model to scan its own
    `![](frames/XXX)` references for fabricated names before submitting.

#### Tests

- 52 → 58 (6 new):
  - State has 4 hard-gate flags + retry counter (defaults sane).
  - `_collect_quality_failures()` returns empty when all pass.
  - `_collect_quality_failures()` produces 4 distinct lines per flag.
  - Render emits banner div + warning text when quality_passed=False.
  - Render emits no banner div when quality_passed=True.
  - Draft user prompt contains all 3 forbidden placeholder examples,
    the real filename verbatim, and the self-check instruction.

### Added — M4 (small-model support)

Optimization pass aimed at users on cheaper / medium-capability LLM
gateways (gemini-2.5-flash, qwen-vl-max, llama-3.1-vision, GPT-4o-mini,
single-vendor proxies). Goal: meaningful runs on models below
claude-opus-4 quality, plus fail-fast on models that won't work at all.

#### Vision capability probe (P1)

- `prompts/03-extract-vision-filter.md` and `prompts/05-5-caption-verify.md`
  now lead with a "Capability self-check" section. Models without vision
  must reply with the exact prefix `ERROR_NO_VISION_CAPABILITY` and stop,
  instead of fabricating captions from the subtitle text.
- `src/keynote_recap/util.py`: `VisionCapabilityError` exception +
  `detect_vision_capability_error()` helper. The detector tolerates code
  fences and avoids false-positives on legitimate JSON output.
- `stages/extract.py`: stage 3 now hard-fails with a clear remediation
  message ("set KEYNOTE_RECAP_MODEL=gemini-2.5-pro / claude-sonnet-4 /
  gpt-4o") when the probe fires.
- `stages/verify.py`: stage 5.5.2 now (a) loads its system prompt from
  the prompt file (previously hard-coded — a latent bug) and (b) marks
  the sub-check as skipped with `skip_reason: no_vision_capability` on
  probe failure rather than crashing 5.5.

#### CLI preflight + `doctor` subcommand

- `src/keynote_recap/preflight.py`: regex-based model classifier with
  three tiers: verified_multimodal / known_text_only / unknown.
  Whitelist: claude-{opus,sonnet}-{4,3.5,3.7}, gemini-{1.5,2.0,2.5}-pro,
  gpt-4o, gpt-4-turbo. Blacklist: mimo-*, gpt-4o-mini, gpt-3.5-*,
  deepseek-{v3,r1}, qwen-{max,plus,turbo,3.x}, llama-3.x. Tolerant of
  provider prefixes (`openai/gpt-4o`).
- `keynote-recap recap`: new preflight check before stage 1; aborts with
  exit 2 if a vision stage uses a known text-only model. Override with
  `--force` (which still warns the prompt-level probe will trip).
- `keynote-recap doctor`: new subcommand for standalone preflight without
  running the pipeline. Prints resolved per-stage models + capability
  verdict + reference list.
- `--llm-all` flag (and `KEYNOTE_RECAP_MODEL_ALL` env var): override ALL
  4 LLM stages with one model. Existing `--llm` only sets draft, which
  is the wrong default for users on single-model gateways.

#### Difficulty tiers for the draft prompt (P2)

- `prompts/05-draft-write-easy.md` (2745 chars, -37% vs standard):
  - 5 forbidden phrases (down from 21)
  - 15-40 images (down from 25-40 floor)
  - ≥ 5 citations (down from ≥ 10)
  - 400-900 lines (down from 600-900)
  - External methodology links inlined (medium models don't fetch)
- `prompts/05-draft-write.md`: unchanged; remains the standard tier.
- `prompts/05-draft-write-strict.md`: incremental constraints on top of
  standard (≤ 25 char sentences, ≥ 2 citations per section, ≥ 5 tables,
  9 additional forbidden phrases, "opposing view" paragraph required in
  every '一点观察' bullet). Recommended for claude-opus-4.
- `config.py`: `DraftConfig.tier` field (default `standard`).
- `stages/draft.py`: `_pick_draft_prompt()` resolves tier → file path,
  falls back to standard on unknown values.
- `cli.py`: `--tier {easy,standard,strict}` flag; the resolved tier is
  printed in the recap startup banner.

#### Forward-fill outline checklist (P3)

- `prompts/05-draft-outline.md`: replaced the after-the-fact "self-check
  for over-merging" instructions (which medium models consistently
  ignored — they treat output completion as `done` and never loop back)
  with a forward fill-in table covering 10 commonly-merged product
  categories (UCP, Neural Expressive, Pics/Stitch/Flow, glasses, Fitbit,
  Omni, Search, science, TPU, pricing). Models must answer yes/no for
  each row before writing the outline, then map yes-rows 1:1 to ##
  sections. Forward checklists are a much stronger signal for medium
  models than reverse self-checks.

#### Single-gateway config presets

- `docs/examples/config.preset-gemini-only.yaml` — all stages on Gemini
  2.5 Pro/Flash; ~\$0.40/keynote (M2 baseline reference stack).
- `docs/examples/config.preset-claude-only.yaml` — all stages on Claude
  family; sonnet for vision, opus + tier=`strict` for draft; ~\$2.50.
- `docs/examples/config.preset-openai-only.yaml` — gpt-4o for vision/draft,
  gpt-4o-mini for research only; ~\$1.20.
- `docs/examples/config.preset-mixed-cheap.yaml` — multi-vendor proxy
  (e.g. OpenRouter); gemini for vision, sonnet-4 for draft, gpt-4o-mini
  for research; ~\$0.60.
- `docs/examples/README.md`: preset selection table + "doctor before
  recap" workflow.

#### Documentation

- `README.md`: new "Model Selection" section before the quickstart, with
  verified vs known-bad model tables. Hot-fixed to main as commit
  `26ccea9` for users hitting the live link before the rest of v0.2 ships.
- `USAGE.md`: matching § 1.1.5 with the same tables, plus three usage
  patterns (`--llm-all`, config-file mixing, CLI override) and the
  `keynote-recap doctor` workflow.

### Tests

- 28 → 52 (24 new):
  - 8 for vision capability probe (detector cases, prompt file presence,
    error subclass, prompt file loading)
  - 5 for preflight model classifier (verified / text-only / unknown
    cases across 21 model names) and `--llm-all` scope correctness
  - 8 for draft tier system (default tier, per-tier file resolution,
    case-insensitivity, unknown fallback, quantitative size check)
  - 3 for config presets (existence, schema validation, gemini-only
    routes vision to Gemini)

### Added — M3
- `src/keynote_recap/official_channels.py`: registry of 7 publishers (Google,
  OpenAI, Anthropic, Apple, Meta, Microsoft, NVIDIA) with allow-listed
  domains, seed URLs, and product-slug URL templates.
- `stages/research.py`: official-channel-first verification pass before
  falling back to web search; new `_detect_product_names()` heuristic
  extracts capitalized product phrases from the transcript with frequency ≥ 2.
- `_summarize_page()` and `_try_official_url()` helpers for reuse across
  the official-first and search fallback passes.
- 7 new smoke tests covering the official-channels registry, publisher
  detection, URL template generation, and product-name extraction.
- `USAGE.md`: end-to-end reuse guide for new keynote URLs (one-shot recipe,
  acceptance checklist, troubleshooting matrix).
- `.github/workflows/ci.yml`: CI matrix for Python 3.10–3.13 (smoke tests +
  ruff lint).

### Changed
- Search fallback in `_verify_facts()` now biases queries toward the detected
  publisher's domains (`site:` operator).
- `confidence` is auto-assigned `high` whenever the source URL matches an
  official domain in the registry, regardless of which pass produced it.

### Fixed
- Removed dead `in_callout` tracking in `stages/verify.py` lint scan
  (resolved last lingering `F841`).

## [0.1.0a0] — M2 quality baseline (2026-05-21)

First end-to-end run that meets the M2 acceptance gates.

### Achievements vs. golden standard (Google I/O '26 keynote)

| Metric | Golden (manual) | M2 v10 (CLI) | Ratio |
|---|---|---|---|
| Lines | 783 | 486 | 62% |
| Sections | 14 | 11 | 79% |
| Images | 35 | 19 | 54% |
| Citations | — | 11 | ✓ (≥ 8) |
| L1 lint errors | 0 | 0 | ✓ |
| L2 lint warnings | 0 | 0 | ✓ |
| Wrong captions | 0 | 0 | ✓ |
| Wrong filenames | 0 | 0 | ✓ |
| Cost | ~$6 (manual time) | $0.20–0.50 (LLM) | — |
| Duration | ~6 hours | 15–25 minutes | — |

### Added — M2
- 7-stage pipeline (download → segment → extract → research → draft →
  verify → render) plus stage 5.5 (3-step quality gate).
- Stage 5.5.0: image filename existence check (whitelist guard).
- Stage 5.5.1 auto-fix: insert unused selected frames into uncovered
  sections.
- `_detect_product_names()` in stage 5.1 outline pass, fed into the prompt
  as a "must consider" list to prevent over-merging.
- Numbered filename whitelist in draft prompt to stop LLM hallucination of
  image paths.
- Anti-AI lint rules (zero-tolerance forbidden words: 巨大 / 显著 / 革命性
  / 让我们 / 不仅仅是 / etc.).
- HTML self-contained renderer (base64-inlined images) for Feishu paste.

### Added — M1
- 18 source files (~3,548 lines of Python) covering CLI, config (5 layers),
  state with checkpointing, OpenAI-compatible LLM client, search abstraction,
  cost tracking, and all 7 stage modules.
- 21 unit tests covering imports, pure-function helpers, state save/load.

### Added — M0
- 25 documents: `docs/requirements.md` (single source of truth, 38 user
  messages traced), 5 methodology docs, 9 stage prompts, and 2 worked
  examples (golden standard + research notes).

### Fixed
- Subtitle truncation at 40 K chars → full transcript fed to outline LLM
  (Gemini 1M-context).
- Callout block wrapped in ```markdown fence → strip + prompt hard-ban.
- Section over-merging (7 → 11) via product-name detection + anti-merge
  self-check in outline prompt.
- Caption language drift to English → forced Chinese + visual verification
  pass.
- Citation count short (3 → 11) via stronger draft-prompt requirements
  (≥ 10 total, ≥ 1 per section).
- Research JSON truncation at 4 K tokens → `max_tokens=16K` + recovery
  for unclosed arrays.
