"""Project methodology constants — the harness that defines "project quality".

These values encode the project's editorial methodology. Modifying them is
equivalent to running a different project: weaker filters, fewer images,
shorter reports, no human checkpoints, etc. — and the resulting output will
NOT meet the quality bar the project advertises.

Historically (v0.2.0 — v0.2.2) every value here was exposed in
``config.yaml`` and could be silently lowered by users / forks, producing
sub-spec reports that users then attributed to "the project". v0.2.3 moves
them out of YAML into module-level constants:

  - **The values are NOT user-tunable.** Any change is a code change with a
    PR/commit attached, surfacing the methodology drift explicitly.
  - **CLI tier flag (``--tier strict|standard|easy``) is the only sanctioned
    way to dial difficulty**, and even ``easy`` only relaxes the *prompt*'s
    forbidden phrase list and the lint thresholds — it does not loosen the
    image / chunk / verify floors below.
  - **Every constant has a one-line "why this number" comment.** When you
    consider changing one, that comment is the contract you're breaking.

If a parameter genuinely belongs to user environment / identity (network
timeout, language, model name, output dir, …) it stays in ``config.yaml``.
This module is exclusively for *editorial* / *methodology* parameters.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — segment (PIL frame_scorer)
# ──────────────────────────────────────────────────────────────────────────────
# Sample interval. Trades coverage vs. ffmpeg I/O. A 90-min keynote at 5s
# gives ~1080 raw frames; the chunk-floor sampler downsamples to ~80 final
# candidates. Lower than 4s explodes I/O without quality gain; higher than
# 8s starts losing 3-5s scene transitions.
SEGMENT_SAMPLE_INTERVAL_S: float = 5.0

# Frame_scorer output cap (PIL initial filter). Must be >= 36 because the
# 12-chunk floor (3 per chunk) downstream demands at least that many.
SEGMENT_CANDIDATE_COUNT: int = 80

# Minimum text/edge density for a frame to be considered. Frames below this
# are pure-shot speaker headshots / blank backgrounds.
SEGMENT_MIN_TEXT_DENSITY: float = 0.05

# Number of equal-width time chunks for the per-chunk sampling floor.
# 12 = roughly 1 chunk per 5 minutes of a 60-min keynote. Smaller -> some
# chapters get zero frames; larger -> redundancy.
SEGMENT_CHUNK_COUNT: int = 12

# Minimum frames preserved per chunk by the floor sampler. Below 3 is too
# fragile (one bad-score frame leaves a chunk with 1-2 candidates and
# stage 3 may reject all of them).
SEGMENT_CHUNK_FLOOR: int = 3


# ──────────────────────────────────────────────────────────────────────────────
# Stage 3 — extract (vision LLM filter)
# ──────────────────────────────────────────────────────────────────────────────
# Stage 3 internal target band. v0.3.1: MIN raised 30→35 to align with
# prompts/03-extract-vision-filter.md (which has always asked for 35-50).
# Empirically, < 35 frames on a 60-90min keynote leaves 6+ subsections
# with 0 images (verified Xiaomi 2026-05-20 launch produced only 27 frames
# with 6 chapters uncovered → triggered v0.3.1 hard-gate work).
EXTRACT_FINAL_COUNT_MIN: int = 35
# v0.3.3 F6: was 50; raised to 65 to give rescue + phash-dedupe headroom.
# Math: 14 chapters × per_section_min(1) + 2 mainline × extra per_mainline(3)
# = 20 absolute lower bound, but real keynote chapters often want 5-8 frames.
# 50 cap was tight enough that rescue+dedupe occasionally landed at 33-34
# (below the 35 floor) and tripped ExtractFloorError → unnecessary retry.
EXTRACT_FINAL_COUNT_MAX: int = 65

# Three-principle thresholds. info_density / relevance below 0.7 produces
# pretty-but-empty frames or off-topic frames. v0.3.1 wires this into a
# code-side hard filter (was prompt-only soft target before).
EXTRACT_INFO_DENSITY_MIN: float = 0.70
EXTRACT_RELEVANCE_MIN: float = 0.70

# v0.3.1 — live-ratio abort floor. Two-tier with prompt:
#   - prompt 03 still asks for 0.70 (soft target; vision LLM aims for it)
#   - this 0.50 is the abort floor (raise ExtractFloorError below it)
# Why not also 0.70 as abort: retry rarely flips a 35%→70% live ratio in
# one pass; 0.50 says "现场图至少占多数" — a clear-signal floor that
# distinguishes a real keynote recap from a marketing-render slideshow.
EXTRACT_LIVE_RATIO_MIN: float = 0.50

# v0.3.1 — A8 硬约束代码兑现：每板块至少 1 张图。
# methodology/filter-three-principles.md 写过"绝不接受这个章节没合适的图"，
# 但 v0.3.0 之前没有代码兜底；verify 5.5.1 只报警不 abort。
EXTRACT_PER_SECTION_MIN: int = 1

# v0.3.1 — 主线章节图量下限。方法论文档"主线 4-6 张/章"。
# 主线判定 = transcript 提及次数 top-2 的 ## 章节（detect_mainline_titles）。
EXTRACT_PER_MAINLINE_MIN: int = 4

# v0.3.1 — caption verify sample 10 张里 wrong 超过此数 → 触发 stage 3 retry。
# 1 张容错（vision LLM 偶发幻觉），≥ 2 张说明系统性看错图，必须重跑。
EXTRACT_CAPTION_VERIFY_WRONG_MAX: int = 1

# v0.3.3 P5 — 5.5.4 image-section fit 启发式不匹配上限。
# check_image_section_fit 此前只在控制台打印警告，不进入 retry 决策；
# 已观察到的真 bug：image of "Pixel Halo" 落入 "## 五、Search" 章节，
# 整个 run 走完仍 quality_passed=True。3 张容差对应 35 张里 ≈ 8.5%
# 误差，覆盖中文章节标题分词的合理漏判；> 3 视为 LLM 系统性配错章节，
# 走 stage 5 retry（draft 重写，不重跑 stage 3 — fit 是 draft 阶段决定的）。
# 注意：此启发式对中文 token 切分本身有漏报倾向（cap_tokens 切中文偏粗），
# 因此阈值偏宽容；P3 重新校准 token 切分留 v0.3.4。
EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX: int = 3


# ──────────────────────────────────────────────────────────────────────────────
# Stage 4 — research (fact verification)
# ──────────────────────────────────────────────────────────────────────────────
# Per-run upper bounds. 30 queries / 50 webfetches is the empirical ceiling
# beyond which marginal verified-fact gain falls below ~5 facts per 10
# additional fetches. Lowering these starves the report; raising them
# wastes API quota.
RESEARCH_MAX_QUERIES: int = 30
RESEARCH_MAX_WEBFETCH: int = 50


# ──────────────────────────────────────────────────────────────────────────────
# Stage 5 — draft (writing)
# ──────────────────────────────────────────────────────────────────────────────
# Target body length for a 60-90min keynote recap. Below 600 lines forces
# omission; above 900 lines triggers padding.
DRAFT_TARGET_LINES_MIN: int = 600
DRAFT_TARGET_LINES_MAX: int = 900

# Top-level section count. Below 8 -> oversized chapters; above 14 ->
# fragmented narrative.
DRAFT_SECTION_COUNT_MIN: int = 8
DRAFT_SECTION_COUNT_MAX: int = 14

# Integrated-summary callout block count.
DRAFT_CALLOUT_BLOCK_MIN: int = 8
DRAFT_CALLOUT_BLOCK_MAX: int = 12

# Minimum supplementary-source citations per report. Below 8 -> the
# "外部信源覆盖" verify gate fails.
DRAFT_CITATION_MIN: int = 8


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline — checkpoints
# ──────────────────────────────────────────────────────────────────────────────
# Default human-review pause points. After stage 3 (frame selection),
# stage 4 (research), and stage 5.5 (verify gate). These pauses are part
# of the project's design contract — the user must inspect candidate
# frames and verified facts before the final draft.
PIPELINE_CHECKPOINTS: tuple[float, ...] = (3.0, 4.0, 5.5)


# ──────────────────────────────────────────────────────────────────────────────
# Agent parallelism (v0.2.3)
# ──────────────────────────────────────────────────────────────────────────────
# Some stages issue many independent LLM calls (stage 3 batches frames,
# stage 4 verifies many facts). On strong models with healthy RPM limits,
# running these calls concurrently yields 3-5x speed-up at zero quality
# cost. On weak / unverified / proxied models, concurrency can blow past
# rate limits or expose race conditions in the user's gateway.
#
# The project's policy is: parallelism is a project-side optimization
# decision, NOT a user knob. We auto-enable it when the model tier is
# verified_multimodal, and fall back to sequential otherwise. The chosen
# value is logged in the stage banner and surfaced in the report's
# responsibility section so users can see what the project did.
#
# Why no CLI / yaml override:
#   - High concurrency mis-set burns API quota and can corrupt the
#     ordering assumptions of the dedup / chunk-floor logic.
#   - Low concurrency mis-set silently slows the pipeline; users may
#     blame the project rather than recognize they capped it.
#   - The "right" number depends on (model_tier × endpoint_rpm), which
#     the project can infer; the user usually cannot.

# Default (used when the model is not on the verified-multimodal list).
# 1 = strict sequential — same behavior as v0.2.2.
AGENT_PARALLEL_DEFAULT: int = 1

# Maximum concurrency when the stage's model is verified_multimodal.
# 4 was tuned against claude-opus-4 / sonnet-4 / gemini-2.5-pro / gpt-4o:
# all four sustain 4 concurrent vision calls at default-tier RPM without
# 429s. Going to 8 trips Anthropic's per-minute limit on free-tier keys.
AGENT_PARALLEL_VERIFIED_CAP: int = 4

# Stages that may run their LLM calls in parallel.
#
# - ``extract`` (stage 3): batches of 8 frames per LLM call, each batch
#   independent. Trivially parallel; safe.
#
# - ``draft`` is excluded: produces a single coherent document, nothing
#   to parallelize.
#
# - ``verify`` is excluded: outputs feed retry decisions and ordering
#   matters.
#
# - ``research`` is intentionally NOT yet eligible (v0.2.3): it shares
#   ``fetch_count`` and ``page_cache`` across iterations, and the
#   citation-balance heuristic depends on per-fact sequencing. Safe
#   parallelization needs a small refactor; planned for v0.2.4.
AGENT_PARALLEL_ELIGIBLE_STAGES: tuple[str, ...] = ("extract",)


def parallel_for_stage(stage: str, model_tier: str) -> int:
    """Return the project-mandated concurrency for a stage.

    Args:
        stage: Stage name as keyed in ``AGENT_PARALLEL_ELIGIBLE_STAGES``.
        model_tier: Value of ``preflight.ModelTier.value`` for the stage's
            model — one of ``"verified_multimodal"`` / ``"known_text_only"``
            / ``"unknown"``.

    Returns:
        ``AGENT_PARALLEL_VERIFIED_CAP`` if the stage is eligible AND the
        model is verified; otherwise ``AGENT_PARALLEL_DEFAULT`` (1).
    """
    if stage not in AGENT_PARALLEL_ELIGIBLE_STAGES:
        return AGENT_PARALLEL_DEFAULT
    if model_tier == "verified_multimodal":
        return AGENT_PARALLEL_VERIFIED_CAP
    return AGENT_PARALLEL_DEFAULT
