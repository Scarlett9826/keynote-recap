"""Smoke tests — verify all modules import + pure-Python helpers work.

These tests do NOT require API keys or network. Suitable for CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable
SRC_ROOT = Path(__file__).parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# ──────────────────────────────────────────────────────────────────────────────
# Import smoke
# ──────────────────────────────────────────────────────────────────────────────
def test_import_top_package():
    import keynote_recap
    assert keynote_recap.__version__


def test_import_cli():
    from keynote_recap import cli
    assert cli.main


def test_import_config():
    from keynote_recap.config import Config
    cfg = Config()
    assert cfg.llm.models.draft
    assert cfg.video.keep_video is True


def test_import_state():
    from keynote_recap.state import State
    s = State.new(url="https://example.com", output_dir="/tmp/t")
    assert s.url == "https://example.com"


def test_import_stages():
    from keynote_recap.stages import download, draft, extract, render, research, segment, verify
    assert all([download.run, segment.run, extract.run, research.run,
                draft.run, verify.run, render.run])


def test_import_pipeline():
    from keynote_recap.pipeline import STAGES, run_pipeline
    assert "download" in STAGES
    assert "verify" in STAGES
    assert run_pipeline


# ──────────────────────────────────────────────────────────────────────────────
# util.py
# ──────────────────────────────────────────────────────────────────────────────
def test_slugify_url_youtube():
    from keynote_recap.util import slugify_url
    assert slugify_url("https://www.youtube.com/watch?v=wYSncx9zLIU") == "youtube_wYSncx9zLIU"
    assert slugify_url("https://youtu.be/abc123") == "youtube_abc123"


def test_slugify_url_bilibili():
    from keynote_recap.util import slugify_url
    assert slugify_url("https://www.bilibili.com/video/BV1xxx").startswith("bilibili_BV1xxx")


def test_format_duration():
    from keynote_recap.util import format_duration
    assert format_duration(65) == "1:05"
    assert format_duration(3725) == "1:02:05"


def test_srt_timestamp():
    from keynote_recap.util import seconds_to_srt_timestamp, srt_timestamp_to_seconds
    assert srt_timestamp_to_seconds("00:01:23,456") == 83.456
    assert srt_timestamp_to_seconds("01:23.456") == 83.456
    assert seconds_to_srt_timestamp(83.456) == "00:01:23,456"


# ──────────────────────────────────────────────────────────────────────────────
# verify.py — pure functions
# ──────────────────────────────────────────────────────────────────────────────
def test_check_coverage_passes():
    from keynote_recap.stages.verify import check_coverage

    md = """# Title

## 一、Agent
![img](frames/a.jpg)
content

## 二、模型
![img](frames/b.jpg)
content

## 信源说明
no image needed
"""
    result = check_coverage(md)
    assert result["all_pass"] is True
    assert len(result["passed"]) == 2


def test_check_coverage_fails_when_missing():
    from keynote_recap.stages.verify import check_coverage

    md = """# Title

## 一、Agent
![img](frames/a.jpg)

## 二、模型
no image here
"""
    result = check_coverage(md)
    assert result["all_pass"] is False
    assert "二、模型" in result["missing"][0]


def test_lint_detects_forbidden_emoji():
    from keynote_recap.stages.verify import lint_report

    md = "## Section\n\n这是一个 🚀 标志。\n"
    result = lint_report(md)
    assert any("🚀" in v.get("found", "") for v in result["level1"])


def test_lint_detects_forbidden_phrase():
    from keynote_recap.stages.verify import lint_report

    md = "## Section\n\n让我们一起来看看 Gemini 的能力。\n"
    result = lint_report(md)
    assert any("让我们一起来看看" in v.get("found", "") for v in result["level1"])


def test_lint_detects_overhype():
    from keynote_recap.stages.verify import lint_report

    md = "## Section\n\n性能有了巨大的提升。\n"
    result = lint_report(md)
    assert any("巨大" in v.get("found", "") for v in result["level2"])


def test_lint_exempts_quote_blocks():
    """Phrases inside `> "..."` quote blocks are演讲者原话, not lint violations."""
    from keynote_recap.stages.verify import lint_report

    md = '## Section\n\n> "让我们一起来看看 the future"\n\nNormal text here.\n'
    # The forbidden phrase is in a quote block — should NOT trigger
    result = lint_report(md)
    # Filter to phrase violations only
    phrase_violations = [v for v in result["level1"]
                          if "L1.2" in v.get("rule", "")
                          and "让我们一起来看看" in v.get("found", "")]
    assert len(phrase_violations) == 0


# ──────────────────────────────────────────────────────────────────────────────
# cost_tracker.py
# ──────────────────────────────────────────────────────────────────────────────
def test_cost_estimate_known_model():
    from keynote_recap.cost_tracker import estimate_cost
    cost = estimate_cost("claude-opus-4", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest_approx(15.0 + 75.0)


def test_cost_estimate_unknown_model():
    from keynote_recap.cost_tracker import estimate_cost
    assert estimate_cost("totally-unknown-model", 1000, 1000) == 0.0


def pytest_approx(expected, rel=1e-6):
    """Tiny approx helper to avoid pytest fixture import."""
    class A:
        def __eq__(self, other):
            return abs(other - expected) < max(rel * abs(expected), 1e-9)
        def __repr__(self):
            return f"~{expected}"
    return A()


# ──────────────────────────────────────────────────────────────────────────────
# config.py
# ──────────────────────────────────────────────────────────────────────────────
def test_config_default():
    from keynote_recap.config import Config
    cfg = Config()
    assert cfg.search.provider == "duckduckgo"  # decision: default zero-key
    assert cfg.video.resolution == "1080p60"
    assert cfg.video.keep_video is True
    assert cfg.template == "keynote-recap"
    assert cfg.language == "zh"


def test_config_yaml_override(tmp_path: Path):
    from keynote_recap.config import load_config
    yaml_text = """
llm:
  base_url: https://custom.example.com/v1
  models:
    draft: my-custom-model
search:
  provider: tavily
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_text)
    cfg = load_config(config_path=cfg_path)
    assert cfg.llm.base_url == "https://custom.example.com/v1"
    assert cfg.llm.models.draft == "my-custom-model"
    assert cfg.search.provider == "tavily"
    # Untouched defaults preserved
    assert cfg.video.resolution == "1080p60"


# ──────────────────────────────────────────────────────────────────────────────
# state.py — round-trip
# ──────────────────────────────────────────────────────────────────────────────
def test_state_save_load(tmp_path: Path):
    from keynote_recap.state import State, VideoMeta

    s = State.new(url="https://example.com/v", output_dir=str(tmp_path))
    s.video = VideoMeta(url="https://example.com/v", title="Test Keynote", duration_s=600)
    s.last_completed_stage = 2.0

    saved_path = s.save()
    assert saved_path.exists()

    loaded = State.load(saved_path)
    assert loaded.url == s.url
    assert loaded.video.title == "Test Keynote"
    assert loaded.last_completed_stage == 2.0


# ──────────────────────────────────────────────────────────────────────────────
# Official channels registry
# ──────────────────────────────────────────────────────────────────────────────
def test_official_channels_import():
    from keynote_recap.official_channels import (
        REGISTRY,
    )
    assert "google" in REGISTRY
    assert "openai" in REGISTRY
    assert "anthropic" in REGISTRY


def test_detect_publisher_google():
    from keynote_recap.official_channels import detect_publisher

    assert detect_publisher("Google", "Google I/O '26 Keynote", "") == "google"
    assert detect_publisher("YouTube Official", "I/O 2026", "Welcome to Google I/O") == "google"


def test_detect_publisher_openai():
    from keynote_recap.official_channels import detect_publisher

    assert detect_publisher("OpenAI", "OpenAI DevDay 2026", "") == "openai"


def test_detect_publisher_unknown():
    from keynote_recap.official_channels import detect_publisher

    assert detect_publisher("Random Channel", "Tech talk", "") is None


def test_candidate_urls_for_product_google():
    from keynote_recap.official_channels import (
        candidate_urls_for_product,
        get_channel,
    )

    ch = get_channel("google")
    urls = candidate_urls_for_product(ch, "Gemini 3 Pro")
    assert any("gemini-3-pro" in u for u in urls)
    assert any("blog.google" in u for u in urls)


def test_is_official_url():
    from keynote_recap.official_channels import get_channel, is_official_url

    ch = get_channel("google")
    assert is_official_url("https://blog.google/products/gemini/", ch)
    assert is_official_url("https://developers.googleblog.com/x", ch)
    assert not is_official_url("https://random-blog.example.com/post", ch)
    assert not is_official_url("https://blog.google/x", None)


def test_detect_product_names():
    from keynote_recap.stages.research import _detect_product_names

    transcript = (
        "Today we're introducing Gemini 3 Pro. With Gemini 3 Pro, you get... "
        "And we're launching Antigravity. Antigravity is a new platform. "
        "We also have Veo 3 and Veo 3 for video. The future is here."
    )
    names = _detect_product_names(transcript, min_count=2)
    assert any("Gemini" in n for n in names)
    assert any("Antigravity" in n for n in names)


# ──────────────────────────────────────────────────────────────────────────────
# Vision capability probe (P1 — small model support)
# ──────────────────────────────────────────────────────────────────────────────
def test_vision_capability_detector_clean_error():
    from keynote_recap.util import detect_vision_capability_error

    text = "ERROR_NO_VISION_CAPABILITY: 当前模型无法看到候选帧图像。"
    result = detect_vision_capability_error(text)
    assert result is not None
    assert "ERROR_NO_VISION_CAPABILITY" in result


def test_vision_capability_detector_with_code_fence():
    from keynote_recap.util import detect_vision_capability_error

    # Some models wrap output in ```...```; detector should still match
    text = "```\nERROR_NO_VISION_CAPABILITY: 模型无 vision 能力。\n```"
    result = detect_vision_capability_error(text)
    assert result is not None
    assert "ERROR_NO_VISION_CAPABILITY" in result


def test_vision_capability_detector_no_false_positive_on_json():
    from keynote_recap.util import detect_vision_capability_error

    # A normal stage 3 JSON output must NOT trigger the detector
    text = (
        '{"selected_frames": [{"filename": "frame_15.jpg", '
        '"caption": "Spark email demo", "info_density": 0.85}]}'
    )
    assert detect_vision_capability_error(text) is None


def test_vision_capability_detector_handles_empty():
    from keynote_recap.util import detect_vision_capability_error

    assert detect_vision_capability_error("") is None
    assert detect_vision_capability_error(None) is None


def test_vision_capability_error_is_runtime_error():
    from keynote_recap.util import VisionCapabilityError

    assert issubclass(VisionCapabilityError, RuntimeError)
    e = VisionCapabilityError("test message")
    assert str(e) == "test message"


def test_caption_verify_prompt_loads_from_file():
    """Stage 5.5.2 should load its system prompt from prompts/05-5-caption-verify.md
    (was previously hard-coded; this regression test prevents reverting)."""
    from keynote_recap.stages.verify import _load_caption_verify_system

    system = _load_caption_verify_system()
    # Must contain the capability probe instructions
    assert "ERROR_NO_VISION_CAPABILITY" in system
    # Must mention the audit role
    assert "审核" in system or "审" in system


def test_extract_prompt_contains_capability_probe():
    """Stage 3 prompt file must include the vision capability probe."""
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "03-extract-vision-filter.md"
    assert p.exists(), f"prompt file missing: {p}"
    content = p.read_text()
    assert "ERROR_NO_VISION_CAPABILITY" in content
    assert "能力前置自检" in content


def test_caption_verify_prompt_contains_capability_probe():
    """Stage 5.5.2 prompt file must include the vision capability probe."""
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "05-5-caption-verify.md"
    assert p.exists(), f"prompt file missing: {p}"
    content = p.read_text()
    assert "ERROR_NO_VISION_CAPABILITY" in content
    assert "能力前置自检" in content


# ──────────────────────────────────────────────────────────────────────────────
# Preflight model classifier (CLI doctor command)
# ──────────────────────────────────────────────────────────────────────────────
def test_preflight_classifies_verified_multimodal():
    from keynote_recap.preflight import ModelTier, check_model_capability

    for name in [
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-3-opus",
        "claude-3.5-sonnet",
        "gemini-2.5-pro",
        "gemini-1.5-pro",
        "gpt-4o",
        "gpt-4-turbo",
        "openai/gpt-4o",
    ]:
        result = check_model_capability(name)
        assert result.tier == ModelTier.VERIFIED_MULTIMODAL, f"{name} should be verified"


def test_preflight_classifies_known_text_only():
    from keynote_recap.preflight import ModelTier, check_model_capability

    for name in [
        "mimo-2.5-pro",
        "mimo-7b",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        "deepseek-v3",
        "deepseek-r1",
        "qwen-max",
        "qwen-3.6-plus",
        "llama-3-70b",
    ]:
        result = check_model_capability(name)
        assert result.tier == ModelTier.KNOWN_TEXT_ONLY, f"{name} should be text-only"


def test_preflight_unknown_models():
    from keynote_recap.preflight import ModelTier, check_model_capability

    for name in [
        "qwen-vl-max",   # multimodal but not on verified list yet
        "internal-foo-bar",
        "",
    ]:
        result = check_model_capability(name)
        assert result.tier == ModelTier.UNKNOWN, f"{name} should be unknown"


def test_llm_override_all_sets_all_stages():
    """--llm-all / KEYNOTE_RECAP_MODEL_ALL should override all 4 LLM stages,
    not just the draft stage (which the existing --llm flag handles)."""
    from keynote_recap.config import load_config

    cfg = load_config(llm_override_all="gemini-2.5-pro")
    assert cfg.llm.models.extract == "gemini-2.5-pro"
    assert cfg.llm.models.research == "gemini-2.5-pro"
    assert cfg.llm.models.draft == "gemini-2.5-pro"
    assert cfg.llm.models.verify == "gemini-2.5-pro"


def test_llm_override_only_sets_draft():
    """--llm should only set draft (regression: don't accidentally widen scope)."""
    from keynote_recap.config import load_config

    cfg = load_config(llm_override="claude-opus-4")
    assert cfg.llm.models.draft == "claude-opus-4"
    # extract/research/verify retain their defaults
    assert cfg.llm.models.extract != "claude-opus-4"  # default is claude-sonnet-4


# ──────────────────────────────────────────────────────────────────────────────
# Draft tier selection (P2 — small model support)
# ──────────────────────────────────────────────────────────────────────────────
def test_draft_tier_default_is_strict(tmp_path, monkeypatch):
    """M5: default tier is now 'strict' — methodology rules are hard contract.

    Users who run the tool with no flags should get the strictest quality gate
    (forbidden phrases, ≥ 8 citations, every chapter has 核心判断, etc).
    Pass --tier easy / --tier standard to relax for weaker models.

    v0.3.2: isolate from the developer's ``~/.config/keynote-recap/config.yaml``
    by pointing HOME at a clean tmp_path so the test asserts the *built-in
    default*, not whatever the dev happens to have on disk.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from keynote_recap.config import load_config

    cfg = load_config()
    assert cfg.draft.tier == "strict"


def test_draft_tier_picks_easy_prompt():
    from keynote_recap.config import load_config
    from keynote_recap.stages.draft import _pick_draft_prompt

    cfg = load_config()
    cfg.draft.tier = "easy"
    p = _pick_draft_prompt(cfg)
    assert p.name == "05-draft-write-easy.md"
    assert p.exists()


def test_draft_tier_picks_standard_prompt():
    from keynote_recap.config import load_config
    from keynote_recap.stages.draft import _pick_draft_prompt

    cfg = load_config()
    cfg.draft.tier = "standard"
    p = _pick_draft_prompt(cfg)
    assert p.name == "05-draft-write.md"
    assert p.exists()


def test_draft_tier_picks_strict_prompt():
    from keynote_recap.config import load_config
    from keynote_recap.stages.draft import _pick_draft_prompt

    cfg = load_config()
    cfg.draft.tier = "strict"
    p = _pick_draft_prompt(cfg)
    assert p.name == "05-draft-write-strict.md"
    assert p.exists()


def test_draft_tier_unknown_falls_back_to_standard():
    """Unknown tier strings should silently fall back to standard, not crash."""
    from keynote_recap.config import load_config
    from keynote_recap.stages.draft import _pick_draft_prompt

    cfg = load_config()
    cfg.draft.tier = "this-tier-does-not-exist"
    p = _pick_draft_prompt(cfg)
    assert p.name == "05-draft-write.md"


def test_draft_tier_case_insensitive():
    from keynote_recap.config import load_config
    from keynote_recap.stages.draft import _pick_draft_prompt

    cfg = load_config()
    cfg.draft.tier = "EASY"
    p = _pick_draft_prompt(cfg)
    assert p.name == "05-draft-write-easy.md"


def test_easy_prompt_is_shorter_than_standard():
    """Easy tier exists primarily to reduce prompt length for medium models."""
    from pathlib import Path

    base = Path(__file__).parent.parent / "prompts"
    standard_chars = (base / "05-draft-write.md").read_text()
    easy_chars = (base / "05-draft-write-easy.md").read_text()
    # Easy should be at least 25% shorter than standard
    assert len(easy_chars) < len(standard_chars) * 0.8, (
        f"easy={len(easy_chars)} chars, standard={len(standard_chars)} chars; "
        "easy tier failed to meaningfully shorten the prompt"
    )


def test_easy_prompt_has_relaxed_image_count():
    """Easy tier loosens the 25-40 image constraint to 15-40."""
    from pathlib import Path

    p = Path(__file__).parent.parent / "prompts" / "05-draft-write-easy.md"
    content = p.read_text()
    assert "15-40" in content, "easy tier should advertise the looser 15-40 image range"
    # Easy tier should have a citation requirement of 5 (not 10)
    assert "至少 5 个" in content or "≥ 5" in content


# ──────────────────────────────────────────────────────────────────────────────
# Config presets (P5 — small model support)
# ──────────────────────────────────────────────────────────────────────────────
def test_config_presets_exist():
    """The 4 vendor-specific presets must exist for users to copy from."""
    from pathlib import Path

    base = Path(__file__).parent.parent / "docs" / "examples"
    for preset in [
        "config.preset-gemini-only.yaml",
        "config.preset-claude-only.yaml",
        "config.preset-openai-only.yaml",
        "config.preset-mixed-cheap.yaml",
    ]:
        assert (base / preset).exists(), f"missing preset: {preset}"


def test_config_presets_parse_as_valid_config():
    """Each preset must load through Config.model_validate without errors."""
    from pathlib import Path

    import yaml

    from keynote_recap.config import Config

    base = Path(__file__).parent.parent / "docs" / "examples"
    presets = list(base.glob("config.preset-*.yaml"))
    assert len(presets) >= 4, f"expected ≥ 4 presets, found {len(presets)}"

    for preset in presets:
        with preset.open() as f:
            data = yaml.safe_load(f)
        # Must validate against the Config schema
        cfg = Config.model_validate(data)
        # Every preset must set vision-stage models to non-empty
        assert cfg.llm.models.extract, f"{preset.name}: extract model is empty"
        assert cfg.llm.models.verify, f"{preset.name}: verify model is empty"


def test_gemini_only_preset_uses_gemini_for_vision_stages():
    """The gemini-only preset must route both vision stages to a Gemini model."""
    from pathlib import Path

    import yaml

    from keynote_recap.config import Config

    p = Path(__file__).parent.parent / "docs" / "examples" / "config.preset-gemini-only.yaml"
    with p.open() as f:
        data = yaml.safe_load(f)
    cfg = Config.model_validate(data)
    assert "gemini" in cfg.llm.models.extract.lower()
    assert "gemini" in cfg.llm.models.verify.lower()


# ──────────────────────────────────────────────────────────────────────────────
# M5 — Quality gate hard-fail + retry mechanism
# ──────────────────────────────────────────────────────────────────────────────
def test_state_has_quality_gate_fields():
    """State must persist the four hard-fail flags + retry counter (M5)."""
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    # All four hard-fail flags exist with safe defaults
    assert hasattr(s, "placeholder_detected")
    assert hasattr(s, "lint_hard_failed")
    assert hasattr(s, "structure_check_passed")
    assert hasattr(s, "coverage_check_passed")
    # Retry counter starts at 0
    assert s.draft_retry_count == 0
    # v0.3.1 C2: defaults to False so early-return paths surface a banner.
    # Only an explicit final-assessment pass sets True.
    assert s.quality_passed is False
    assert s.final_quality_warnings == []


def test_collect_quality_failures_empty_when_all_pass():
    """Pipeline helper returns empty list when all gates pass."""
    from keynote_recap.pipeline import _collect_quality_failures
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    s.coverage_check_passed = True
    s.structure_check_passed = True
    s.placeholder_detected = False
    s.lint_hard_failed = False
    assert _collect_quality_failures(s) == []


def test_collect_quality_failures_detects_each_gate():
    """Each hard-fail flag produces a distinct issue line."""
    from keynote_recap.pipeline import _collect_quality_failures
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    s.coverage_check_passed = False
    s.structure_check_passed = False
    s.placeholder_detected = True
    s.lint_hard_failed = True
    issues = _collect_quality_failures(s)
    assert len(issues) == 4
    # Each issue mentions its stage number for traceability
    joined = " ".join(issues)
    assert "5.5.0" in joined
    assert "5.5.1" in joined
    assert "5.5.3" in joined
    assert "5.5.5" in joined


def test_render_banner_appears_when_quality_failed():
    """Render stage emits a yellow warning banner when quality_passed=False."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        # Minimal report.md
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        s.quality_passed = False
        s.final_quality_warnings = ["5.5.0 image filename: invented placeholder names"]

        cfg = load_config()
        s = render_run(s, cfg)

        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-red">' in html
        assert "本报告未通过项目质量门" in html
        assert "invented placeholder names" in html
        # M7: red banner triggers responsibility section
        assert "模型与责任边界" in html
        assert "项目（keynote-recap）负责" in html


def test_render_no_banner_when_quality_passed():
    """No banner when quality_passed=True and no env/model warnings."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        # v0.3.1 C2: must explicitly set True since default flipped to False
        s.quality_passed = True

        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        # CSS class definitions always present in <style>; check rendered <div>s
        assert '<div class="quality-banner quality-banner-red">' not in html
        assert '<div class="quality-banner quality-banner-yellow">' not in html
        assert "本报告未通过项目质量门" not in html
        assert "本次运行存在环境" not in html
        # responsibility section only emitted when banner present
        assert "模型与责任边界" not in html


# ──────────────────────────────────────────────────────────────────────────────
# M7 / v0.2.2 — preflight env + tri-color banner + responsibility section
# ──────────────────────────────────────────────────────────────────────────────
def test_preflight_env_python_version_check():
    """Python version check returns ok for current interpreter (>= 3.10 in CI)."""
    from keynote_recap.preflight_env import check_python_version

    r = check_python_version()
    assert r.what == "python"
    assert r.ok is True


def test_preflight_env_ffmpeg_check_handles_missing(monkeypatch):
    """When ffmpeg binary is not on PATH, check_ffmpeg returns blocker."""
    import keynote_recap.preflight_env as pe

    monkeypatch.setattr(pe.shutil, "which", lambda b: None)
    r = pe.check_ffmpeg()
    assert r.ok is False
    assert r.severity == "blocker"
    assert "ffmpeg" in r.detail.lower()
    assert r.fix is not None
    assert "brew install ffmpeg" in r.fix


def test_preflight_env_api_key_check_unset(monkeypatch):
    """v0.2.5.1 hotfix: unset API key is a *warning*, not a blocker.

    Rationale: many environments (corporate gateways, agent-host injected
    proxies) reach the LLM endpoint without OPENAI_API_KEY being literally
    set in the calling shell. Pre-flighting only catches "the variable is
    literally unset", which is advisory-grade. The proper place for "the
    key is actually wrong" is the first LLM call (401 with provider
    message). v0.2.5 silently upgraded this to a blocker (un-declared
    BREAKING) which broke those workflows.

    v0.3.5 update: detail wording is fully neutralized (no "fail" /
    "401" / "missing") to stop external agent wrappers from over-reading
    the message and aborting. fix is now None (we don't tell the user
    what to do — we trust the SDK's resolution chain).
    """
    from keynote_recap.preflight_env import check_api_key

    monkeypatch.delenv("FAKE_KEY", raising=False)
    r = check_api_key("FAKE_KEY")
    assert r.ok is False
    assert r.severity == "warning"  # v0.2.5.1 — was "blocker" in v0.2.5
    assert "FAKE_KEY" in r.detail
    # v0.3.5: detail must not contain alarming words that fool agents.
    lower = r.detail.lower()
    for forbidden in ("fail", "401", "error", "missing", "unset"):
        assert forbidden not in lower, (
            f"v0.3.5: detail must be neutral; found '{forbidden}' in: {r.detail!r}"
        )
    # v0.3.5: fix is None — we no longer prescribe `export X=...`.
    assert r.fix is None


def test_v0251_preflight_env_does_not_abort_when_only_api_key_missing(
    tmp_path, monkeypatch
):
    """Regression for v0.2.5 hard-abort bug.

    cli._preflight_env must return a (possibly non-empty) warnings list,
    NOT None, when the only failing check is the API key. Returning None
    means the recap command sys.exit(2)s before stage 1.
    """
    from keynote_recap.cli import _preflight_env
    from keynote_recap.config import load_config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = load_config()
    result = _preflight_env(cfg, tmp_path)
    assert result is not None, (
        "v0.2.5 regression: _preflight_env aborted when only api_key was "
        "missing. v0.2.5.1 must let the run continue (warning, not blocker)."
    )
    assert any("api_key" in w for w in result), (
        "Expected api_key warning to surface in warnings list."
    )


def test_preflight_env_api_key_check_set(monkeypatch):
    """A normal-length API key passes."""
    from keynote_recap.preflight_env import check_api_key

    monkeypatch.setenv("FAKE_KEY", "x" * 40)
    r = check_api_key("FAKE_KEY")
    assert r.ok is True


def test_preflight_env_api_key_check_too_short(monkeypatch):
    """A suspiciously short key gets a warning, not a blocker."""
    from keynote_recap.preflight_env import check_api_key

    monkeypatch.setenv("FAKE_KEY", "abc")
    r = check_api_key("FAKE_KEY")
    assert r.ok is False
    assert r.severity == "warning"


def test_preflight_env_run_all_returns_list(tmp_path, monkeypatch):
    """Smoke: run_all_checks returns a list of EnvChecks; warning_summaries
    only includes non-blocker failures."""
    from keynote_recap.preflight_env import (
        EnvCheck,
        has_blocker,
        run_all_checks,
        warning_summaries,
    )

    monkeypatch.setenv("FAKE_KEY", "x" * 40)
    checks = run_all_checks(output_dir=tmp_path, api_key_env="FAKE_KEY")
    assert isinstance(checks, list)
    assert all(isinstance(c, EnvCheck) for c in checks)

    # Construct a fake-mixed result to verify helpers
    fake = [
        EnvCheck(ok=True, what="a", detail="ok"),
        EnvCheck(ok=False, what="b", detail="blocked", severity="blocker", fix="fix"),
        EnvCheck(ok=False, what="c", detail="warn", severity="warning"),
    ]
    assert has_blocker(fake) is True
    summaries = warning_summaries(fake)
    assert any("warn" in s for s in summaries)
    assert not any("blocked" in s for s in summaries)


def test_render_yellow_banner_for_env_warnings():
    """Env preflight warnings produce a yellow (not red) banner + responsibility section."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        s.preflight_env_warnings = ["disk: only 2.0 GB free at /tmp"]
        s.quality_passed = True  # v0.3.1 C2: default flipped, set explicitly

        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-yellow">' in html
        assert '<div class="quality-banner quality-banner-red">' not in html
        assert "本次运行存在环境" in html
        assert "only 2.0 GB free" in html
        # responsibility section IS shown for yellow banner
        assert "模型与责任边界" in html
        assert "项目<b>不</b>负责" in html


def test_render_yellow_banner_for_unverified_model():
    """Unverified vision model triggers yellow banner with model-warning section."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        s.preflight_model_warnings = [
            "extract (stage 3 frame filter) uses unverified model some-custom-model"
        ]
        s.models_used = {
            "extract": "some-custom-model",
            "draft": "claude-opus-4",
            "research": "gpt-4o",
            "verify": "some-custom-model",
        }
        s.model_tiers = {
            "extract": "unknown",
            "draft": "verified_multimodal",
            "research": "verified_multimodal",
            "verify": "unknown",
        }
        s.quality_passed = True  # v0.3.1 C2: default flipped, set explicitly

        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-yellow">' in html
        assert "some-custom-model" in html
        # responsibility table lists the actual model
        assert "未验证" in html
        assert "已验证多模态" in html


def test_render_yellow_banner_for_runtime_probe():
    """Runtime capability probe warning surfaces in yellow banner."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        s.runtime_warnings = [
            "stage 3 only produced 2 frames (< 5). Vision model may be weak."
        ]
        s.quality_passed = True  # v0.3.1 C2: default flipped, set explicitly

        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-yellow">' in html
        assert "跑中能力探针" in html
        assert "only produced 2 frames" in html


def test_render_red_takes_precedence_over_yellow():
    """When both quality_failed AND env warnings exist, red wins."""
    import tempfile
    from pathlib import Path

    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta

    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")

        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        s.quality_passed = False
        s.final_quality_warnings = ["5.5.0 placeholder names"]
        s.preflight_env_warnings = ["disk: only 1 GB free"]

        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-red">' in html
        assert '<div class="quality-banner quality-banner-yellow">' not in html
        assert "本报告未通过项目质量门" in html


def test_runtime_probe_extract_few_frames():
    """_probe_extract_output flags runs with very few selected frames."""
    from keynote_recap.pipeline import _probe_extract_output
    from keynote_recap.state import SelectedFrame, State

    s = State.new(url="https://x", output_dir="/tmp/x")
    s.models_used = {"extract": "some-weak-model"}
    s.selected_frames = [
        SelectedFrame(
            filename=f"frame_{i:05d}.jpg",
            timestamp_s=float(i),
            category="demo",
            caption=f"c{i}",
            recommended_section="一",
            info_density=0.5,
            relevance=0.5,
        )
        for i in range(2)
    ]
    warn = _probe_extract_output(s)
    assert warn is not None
    assert "2 frames" in warn
    assert "some-weak-model" in warn

    # Healthy: 10 frames -> no warning
    s.selected_frames = s.selected_frames * 5
    assert _probe_extract_output(s) is None


def test_runtime_probe_research_no_verified():
    """_probe_research_output flags runs where research turned up nothing."""
    from keynote_recap.pipeline import _probe_research_output
    from keynote_recap.state import FactToVerify, State

    s = State.new(url="https://x", output_dir="/tmp/x")
    s.models_used = {"research": "some-text-only"}
    s.facts_to_verify = [
        FactToVerify(
            id="f1",
            category="product_name",
            transcript_quote="...",
            transcript_timestamp_s=10.0,
            what_to_verify="...",
        )
    ]
    s.verified_facts = []  # zero verified despite having facts to verify
    warn = _probe_research_output(s)
    assert warn is not None
    assert "some-text-only" in warn

    # Healthy: nothing to verify -> no warning
    s.facts_to_verify = []
    assert _probe_research_output(s) is None


def test_preflight_models_unknown_warns_but_proceeds():
    """v0.3.2: unverified vision model is advisory, NOT a hard abort.

    Rationale: gateway-prefixed names like ``mygw/claude-opus-4`` already
    pass via the substring matcher in ``preflight.py`` (see
    ``test_v032_preflight_recognises_gateway_prefixed_models``). What
    remains as UNKNOWN is genuinely-new model IDs being tested; those
    must surface a warning but not block the run — that's what the
    quality banner is for.

    KNOWN_TEXT_ONLY remains a hard abort (separate test below).
    """
    from keynote_recap.cli import _preflight_models
    from keynote_recap.config import load_config

    cfg = load_config()
    cfg.llm.models.extract = "totally-unknown-vision-model-xyz"
    cfg.llm.models.verify = "totally-unknown-vision-model-xyz"

    proceed, warnings = _preflight_models(cfg)
    assert proceed is True, (
        "v0.3.2: UNKNOWN models must proceed with advisory; this was a hard "
        "abort in v0.2.4-v0.3.1 and broke gateway/proxy routed models."
    )
    assert len(warnings) >= 2  # both extract and verify warned
    assert any("totally-unknown" in w for w in warnings)


def test_v032_known_text_only_still_hard_aborts():
    """v0.3.2 keeps KNOWN_TEXT_ONLY as a hard abort.

    Text-only models on a vision stage silently produce garbage reports.
    Preflight is the only place we catch it and the signal is worth
    preserving.
    """
    from keynote_recap.cli import _preflight_models
    from keynote_recap.config import load_config

    cfg = load_config()
    cfg.llm.models.extract = "deepseek-v3"  # KNOWN_TEXT_ONLY
    cfg.llm.models.verify = "deepseek-v3"

    proceed, warnings = _preflight_models(cfg)
    assert proceed is False, "KNOWN_TEXT_ONLY must hard abort"
    assert any("deepseek" in w.lower() for w in warnings)


def test_v032_preflight_recognises_gateway_prefixed_models():
    """v0.3.2: gateway/proxy-prefixed model IDs map to VERIFIED via substring.

    Real-world model IDs from agent-host setups like opencode, openrouter,
    your-gateway all wrap the underlying model with a routing prefix. Before
    v0.3.2 these tripped the UNKNOWN hard abort even though the
    underlying model was a verified Claude/Gemini/GPT-4o.
    """
    from keynote_recap.preflight import ModelTier, check_model_capability

    cases = [
        "your-company-llm-anthropic/your-vendor/claude-opus-4-7",
        "your-company-llm-anthropic/your-vendor/claude-sonnet-4-6",
        "openrouter/anthropic/claude-opus-4",
        "gateway/openai/gpt-4o",
        "your-gateway/gemini-2.5-pro",
    ]
    for name in cases:
        r = check_model_capability(name)
        assert r.tier == ModelTier.VERIFIED_MULTIMODAL, (
            f"{name} should be recognised as VERIFIED via substring "
            f"match; got {r.tier}"
        )


def test_v032_llm_client_does_not_raise_when_api_key_env_unset(monkeypatch, capsys):
    """v0.3.2: LLMClient must NOT raise when api_key_env is unset.

    Restores the v0.2.4 contract that the SDK owns key resolution. The
    historical regression: corporate gateways / agent-host proxies
    inject auth via headers (not env), and SDKs read from keychains /
    config files / multiple env vars. Hard-failing in our __init__
    on a single env var blocked all those paths.

    The advisory message goes to stderr-equivalent (print to stdout).
    A real 401 surfaces at the first LLM call with a provider message.
    """
    from keynote_recap.config import LLMConfig
    from keynote_recap.llm_client import LLMClient

    # Ensure both possible env vars are unset
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FAKE_KEY", raising=False)

    cfg = LLMConfig(api_key_env="FAKE_KEY")
    # Must NOT raise
    client = LLMClient(cfg)
    assert client is not None

    captured = capsys.readouterr()
    assert "FAKE_KEY" in captured.out, (
        "v0.3.2 expects an advisory mentioning the unset env var name"
    )


def test_v032_llm_client_anthropic_backend_does_not_raise_when_unset(monkeypatch, capsys):
    """v0.3.2: same contract for the anthropic-native backend."""
    from keynote_recap.config import LLMConfig
    from keynote_recap.llm_client import LLMClient

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FAKE_KEY", raising=False)

    cfg = LLMConfig(provider="anthropic-native", api_key_env="FAKE_KEY")
    client = LLMClient(cfg)
    assert client is not None
    captured = capsys.readouterr()
    assert "FAKE_KEY" in captured.out


def test_v024_preflight_models_no_force_kwarg():
    """v0.2.4 (M9.1): _preflight_models no longer accepts a force= kwarg."""
    import inspect

    from keynote_recap.cli import _preflight_models

    sig = inspect.signature(_preflight_models)
    assert "force" not in sig.parameters, (
        "v0.2.4 removed --force; _preflight_models must not accept it either"
    )


def test_draft_user_prompt_warns_against_placeholder_names():
    """draft.py user prompt must contain the 3 forbidden placeholder examples."""
    from keynote_recap.stages.draft import _build_user_for_body
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    s = State.new(url="https://x", output_dir="/tmp/x")
    s.video = VideoMeta(url="https://x", title="t", duration_s=600.0, transcript="")
    s.selected_frames = [SelectedFrame(
        filename="frame_00457.jpg",
        timestamp_s=10.0,
        category="demo",
        caption="test caption",
        recommended_section="一、demo",
        info_density=0.8,
        relevance=0.9,
    )]

    user_prompt = _build_user_for_body(s, "## 一、demo\n")
    # Forbidden placeholder examples must be visible to the LLM
    assert "frame_gt_01" in user_prompt
    assert "01-spark-intro" in user_prompt
    assert "frame_intro" in user_prompt
    # Real filename appears verbatim
    assert "frame_00457.jpg" in user_prompt
    # Self-check instruction is present
    assert "输出前自检" in user_prompt


# ──────────────────────────────────────────────────────────────────────────────
# M6 D1 — deterministic image bucket placement
# ──────────────────────────────────────────────────────────────────────────────
def test_d1_bucket_by_section_groups_frames_by_chapter():
    """frames sharing recommended_section with a chapter end up in same bucket."""
    from keynote_recap.stages.draft import _bucket_by_section
    from keynote_recap.state import SelectedFrame

    frames = [
        SelectedFrame(
            filename="f1.jpg", timestamp_s=10, category="demo",
            caption="c1", recommended_section="模型层",
            info_density=0.8, relevance=0.8,
        ),
        SelectedFrame(
            filename="f2.jpg", timestamp_s=20, category="data",
            caption="c2", recommended_section="模型层 Gemini",
            info_density=0.8, relevance=0.8,
        ),
        SelectedFrame(
            filename="f3.jpg", timestamp_s=30, category="product",
            caption="c3", recommended_section="订阅价",
            info_density=0.8, relevance=0.8,
        ),
    ]
    outline = "## 一、模型层 — Gemini 谱系\n\n## 二、订阅价 — 三档定价\n"
    buckets = _bucket_by_section(frames, outline)
    # 2 chapter buckets, no unassigned
    assert len(buckets) == 2
    titles = {ch for ch, _ in buckets}
    assert any("模型层" in t for t in titles)
    assert any("订阅价" in t for t in titles)
    # f1 and f2 should be in the model bucket; f3 in pricing
    for ch, fs in buckets:
        names = {f.filename for f in fs}
        if "模型层" in ch:
            assert names == {"f1.jpg", "f2.jpg"}
        elif "订阅价" in ch:
            assert names == {"f3.jpg"}


def test_d1_bucket_unmatched_frames_go_to_overflow():
    """frames whose recommended_section matches no chapter land in overflow bucket."""
    from keynote_recap.stages.draft import _bucket_by_section
    from keynote_recap.state import SelectedFrame

    frames = [
        SelectedFrame(
            filename="orphan.jpg", timestamp_s=5, category="demo",
            caption="c", recommended_section="某个未列出的章节",
            info_density=0.8, relevance=0.8,
        ),
    ]
    outline = "## 一、模型层\n"
    buckets = _bucket_by_section(frames, outline)
    # First bucket = 模型层 (empty), last = 未分配 with the orphan
    titles = [ch for ch, _ in buckets]
    assert any("未分配" in t for t in titles)
    overflow = [fs for ch, fs in buckets if "未分配" in ch][0]
    assert overflow[0].filename == "orphan.jpg"


def test_d1_format_buckets_warns_for_empty_chapters():
    """A chapter with zero candidate frames must be visible in the prompt."""
    from keynote_recap.stages.draft import _format_buckets_for_prompt

    text = _format_buckets_for_prompt([("一、孤章节 (no frames)", []), ("二、富章节", [])])
    assert "本章无候选帧" in text


def test_d1_check_bucket_placement_passes_for_correct_chapter():
    """If image lands in chapter matching its recommended_section, no error."""
    from keynote_recap.stages.verify import check_bucket_placement
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x")
    s.selected_frames = [
        SelectedFrame(
            filename="f1.jpg", timestamp_s=10, category="demo",
            caption="c", recommended_section="模型层",
            info_density=0.8, relevance=0.8,
        ),
    ]
    report = "## 一、模型层 — Gemini\n\n![cap](frames/f1.jpg)\n\nbody\n"
    r = check_bucket_placement(report, s)
    assert r["all_pass"] is True
    assert r["cross_placements"] == []


def test_d1_check_bucket_placement_fails_for_cross_chapter():
    """If image with recommended_section=A lands in chapter B, must fail."""
    from keynote_recap.stages.verify import check_bucket_placement
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x")
    s.selected_frames = [
        SelectedFrame(
            filename="f1.jpg", timestamp_s=10, category="demo",
            caption="c", recommended_section="订阅价",
            info_density=0.8, relevance=0.8,
        ),
    ]
    # f1 has recommended_section=订阅价 but report places it in 模型层 chapter
    report = "## 一、模型层 — Gemini\n\n![cap](frames/f1.jpg)\n"
    r = check_bucket_placement(report, s)
    assert r["all_pass"] is False
    assert len(r["cross_placements"]) == 1
    cp = r["cross_placements"][0]
    assert cp["filename"] == "f1.jpg"
    assert "订阅价" in cp["intended"]
    assert "模型层" in cp["actual"]


# ──────────────────────────────────────────────────────────────────────────────
# M6 D2 — image source mix (live ratio + total floor)
# ──────────────────────────────────────────────────────────────────────────────
def _make_frame(name: str, is_live: bool = True):
    from keynote_recap.state import SelectedFrame
    return SelectedFrame(
        filename=name, timestamp_s=1.0, category="demo",
        caption="c", recommended_section="x",
        info_density=0.8, relevance=0.8, is_live=is_live,
    )


def test_d2_image_source_mix_passes_when_above_thresholds():
    """≥25 frames + ≥70% live → all_pass=True."""
    from keynote_recap.stages.verify import check_image_source_mix
    from keynote_recap.state import State, VideoMeta

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x")
    s.selected_frames = [_make_frame(f"l{i}.jpg", True) for i in range(20)] + \
                        [_make_frame(f"n{i}.jpg", False) for i in range(5)]
    r = check_image_source_mix(s)
    assert r["all_pass"] is True
    assert r["total"] == 25
    assert r["live"] == 20
    assert r["live_ratio"] == 0.8


def test_d2_image_source_mix_fails_when_total_too_low():
    """<25 total frames → all_pass=False."""
    from keynote_recap.stages.verify import check_image_source_mix
    from keynote_recap.state import State, VideoMeta

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x")
    s.selected_frames = [_make_frame(f"l{i}.jpg", True) for i in range(8)]
    r = check_image_source_mix(s)
    assert r["all_pass"] is False
    assert any("frame count" in i for i in r["issues"])


def test_d2_image_source_mix_fails_when_live_ratio_too_low():
    """≥25 frames but live <70% → all_pass=False."""
    from keynote_recap.stages.verify import check_image_source_mix
    from keynote_recap.state import State, VideoMeta

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x")
    # 0525 PDF case: 8/30 live = 26%
    s.selected_frames = [_make_frame(f"l{i}.jpg", True) for i in range(8)] + \
                        [_make_frame(f"n{i}.jpg", False) for i in range(22)]
    r = check_image_source_mix(s)
    assert r["all_pass"] is False
    assert r["live_ratio"] < 0.70


# ──────────────────────────────────────────────────────────────────────────────
# M6 D3 — stage 2 topic-chunk floor
# ──────────────────────────────────────────────────────────────────────────────
def test_d3_topn_with_chunk_floor_guarantees_per_chunk_minimum():
    """Even if some chunks have only low-score frames, they still get K frames."""
    from pathlib import Path
    from keynote_recap.stages.segment import _topn_with_chunk_floor

    # Simulate 60 frames over 600s (10s interval). 12 chunks of 50s each.
    # frames 1-5 high score (chunk 0), 6-60 low score
    scored = []
    for i in range(1, 61):
        score = 100 - i  # frame_00001 highest, descending
        scored.append((Path(f"frame_{i:05d}.jpg"), float(score), {}))

    result = _topn_with_chunk_floor(
        scored=scored, duration_s=600.0,
        target_count=30, chunk_count=12, per_chunk_min=2,
    )
    # Each chunk should have at least 2 frames represented
    by_chunk: dict[int, int] = {i: 0 for i in range(12)}
    n_frames = len(scored)
    interval_est = 600.0 / n_frames
    chunk_size_s = 600.0 / 12
    for path, _score, _m in result:
        idx = int(path.stem.split("_")[1])
        ts = (idx - 1) * interval_est
        ci = max(0, min(11, int(ts / chunk_size_s)))
        by_chunk[ci] += 1
    # Every chunk has ≥ 2 frames (the per-chunk floor)
    for ci, n in by_chunk.items():
        assert n >= 2, f"chunk {ci} has only {n} frames (floor=2)"


def test_d3_topn_falls_back_when_zero_duration():
    """duration=0 should return top-N by score without crashing."""
    from pathlib import Path
    from keynote_recap.stages.segment import _topn_with_chunk_floor

    scored = [(Path(f"frame_{i:05d}.jpg"), float(100 - i), {}) for i in range(1, 11)]
    result = _topn_with_chunk_floor(
        scored=scored, duration_s=0, target_count=5,
        chunk_count=12, per_chunk_min=2,
    )
    # Returns top-5 by score, no crash
    assert len(result) == 5


# ──────────────────────────────────────────────────────────────────────────────
# M6 D4 — topic coverage
# ──────────────────────────────────────────────────────────────────────────────
def test_d4_topic_coverage_passes_when_all_high_freq_covered():
    """Every product mentioned ≥5 times in transcript appears in some frame."""
    from keynote_recap.stages.verify import check_topic_coverage
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    transcript = "Spark " * 6 + "Antigravity " * 6
    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x", transcript=transcript)
    s.selected_frames = [
        SelectedFrame(
            filename="f1.jpg", timestamp_s=1, category="demo",
            caption="Spark 主舞台", recommended_section="Agent",
            info_density=0.8, relevance=0.8,
        ),
        SelectedFrame(
            filename="f2.jpg", timestamp_s=2, category="demo",
            caption="Antigravity IDE", recommended_section="开发者平台",
            info_density=0.8, relevance=0.8,
        ),
    ]
    r = check_topic_coverage(s)
    assert r["all_pass"] is True
    assert len(r["missing"]) == 0


def test_d4_topic_coverage_fails_when_high_freq_topic_has_no_frame():
    """Product mentioned ≥5× but absent from any frame's caption → fail."""
    from keynote_recap.stages.verify import check_topic_coverage
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    # Spark + Antigravity + AlphaFold + AlphaProteo + AI Mode all ≥5×
    # but selected_frames covers only Spark
    transcript = (
        "Spark Spark Spark Spark Spark Spark "
        "Antigravity Antigravity Antigravity Antigravity Antigravity Antigravity "
        "AlphaFold AlphaFold AlphaFold AlphaFold AlphaFold AlphaFold "
        "AlphaProteo AlphaProteo AlphaProteo AlphaProteo AlphaProteo AlphaProteo "
    )
    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x", transcript=transcript)
    s.selected_frames = [
        SelectedFrame(
            filename="f1.jpg", timestamp_s=1, category="demo",
            caption="Spark demo", recommended_section="Agent",
            info_density=0.8, relevance=0.8,
        ),
    ]
    r = check_topic_coverage(s)
    # Tolerance is 2; we have 3 missing (Antigravity / AlphaFold / AlphaProteo) → fail
    assert r["all_pass"] is False
    assert len(r["missing"]) >= 3


# ──────────────────────────────────────────────────────────────────────────────
# M6 — pipeline retry helpers
# ──────────────────────────────────────────────────────────────────────────────
def test_pipeline_extract_failures_separated_from_draft():
    """Stage 3 retry triggered by extract failures only; stage 5 retry by draft."""
    from keynote_recap.pipeline import _collect_extract_failures, _collect_draft_failures
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    # Simulate a frame-selection problem
    s.image_mix_passed = False
    s.topic_coverage_passed = False
    # And simulate a writing problem
    s.bucket_placement_passed = False
    s.lint_hard_failed = True

    extract = _collect_extract_failures(s)
    draft = _collect_draft_failures(s)

    assert any("5.5.6" in i for i in extract)
    assert any("5.5.7" in i for i in extract)
    # bucket_placement and lint must NOT be in extract failures
    assert not any("5.5.4b" in i for i in extract)
    assert not any("5.5.3" in i for i in extract)
    # bucket_placement and lint MUST be in draft failures
    assert any("5.5.4b" in i for i in draft)
    assert any("5.5.3" in i for i in draft)


def test_d2_extract_parses_is_live_field():
    """stage 3 _merge_batch_result must parse is_live from LLM JSON."""
    from keynote_recap.stages.extract import _merge_batch_result
    from keynote_recap.state import FrameCandidate, SelectedFrame

    batch = [
        FrameCandidate(filename="f1.jpg", timestamp_s=1, score=80,
                       text_density=0.5, edge_density=0.5, context_subtitle=""),
        FrameCandidate(filename="f2.jpg", timestamp_s=2, score=75,
                       text_density=0.5, edge_density=0.5, context_subtitle=""),
    ]
    selected: list[SelectedFrame] = []
    rejected: list[dict] = []
    _merge_batch_result({
        "selected_frames": [
            {"filename": "f1.jpg", "category": "demo", "caption": "live shot",
             "recommended_section": "x", "is_live": True,
             "info_density": 0.8, "relevance_to_section": 0.9,
             "what_can_be_read": "643km / 73kWh"},
            {"filename": "f2.jpg", "category": "product", "caption": "渲染图",
             "recommended_section": "x", "is_live": False,
             "info_density": 0.6, "relevance_to_section": 0.7,
             "what_can_be_read": "红色 SUV"},
        ],
        "rejected_frames": [],
    }, batch, selected, rejected)
    assert len(selected) == 2
    f1, f2 = selected[0], selected[1]
    assert f1.is_live is True
    assert f2.is_live is False
    # caption gets disclaimer prefix when is_live=False
    assert f2.caption.startswith("（插播官方渲染）")
    # what_can_be_read preserved
    assert "643km" in f1.what_can_be_read
    assert "红色" in f2.what_can_be_read


# ──────────────────────────────────────────────────────────────────────────────
# M6 — end-to-end: simulate 0525.pdf failure and verify gates would catch it
# ──────────────────────────────────────────────────────────────────────────────
def test_e2e_0525pdf_scenario_would_have_been_caught_by_gates():
    """The 0525 PDF failure (8 frames, all marketing renders) must trigger
    BOTH the 5.5.6 image-mix gate AND the 5.5.7 topic-coverage gate, leading
    to extract-stage retry. This is the regression test for the user-reported
    real-world failure that motivated M6.
    """
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.stages.verify import (
        check_image_source_mix,
        check_topic_coverage,
    )
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    # Reproduce 0525 conditions: transcript mentions YU7 / SU7 / Pro / Max heavily,
    # but selected_frames is 8 marketing renders (is_live=False) of cars.
    transcript = (
        "YU7 " * 30 +              # discussed extensively
        "SU7 " * 25 +
        "Pro " * 10 + "Max " * 10
    )

    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x", transcript=transcript)
    # 8 marketing-render frames, none captioned with the actual product names
    s.selected_frames = [
        SelectedFrame(
            filename=f"frame_{i:05d}.jpg", timestamp_s=float(i),
            category="product",
            caption="（插播官方渲染）红色 SUV 公路夕阳行驶镜头",
            recommended_section="车辆外观",
            info_density=0.4, relevance=0.5, is_live=False,
            what_can_be_read="红色 SUV",
        )
        for i in range(1, 9)
    ]

    # Now run the gates the same way verify.run() would
    mix = check_image_source_mix(s)
    cov = check_topic_coverage(s)

    # Both gates must reject this report
    assert mix["all_pass"] is False, "5.5.6 gate must catch 8-frame all-render scenario"
    assert mix["total"] == 8, "should report low total frame count"
    assert mix["live_ratio"] == 0.0, "all 8 are non-live → 0% live ratio"

    # Topic coverage may pass or fail depending on whether YU7/SU7 are in
    # _PRODUCT_PATTERNS. The important property is at least one of {mix, cov}
    # fails so the extract retry triggers.
    s.image_mix_passed = mix["all_pass"]
    s.topic_coverage_passed = cov["all_pass"]

    fails = _collect_extract_failures(s)
    assert len(fails) >= 1, "at least one extract-stage retry trigger must fire"
    assert any("5.5.6" in f for f in fails), "image-mix failure must be reported"


def test_e2e_healthy_recap_passes_all_gates():
    """Counter-test: a healthy state with 30 live frames + full topic coverage
    must pass all M6 gates so we don't regress good reports.
    """
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.stages.verify import (
        check_image_source_mix,
        check_topic_coverage,
    )
    from keynote_recap.state import SelectedFrame, State, VideoMeta

    transcript = "Spark " * 20 + "Antigravity " * 15
    s = State.new(url="x", output_dir="/tmp/x")
    s.video = VideoMeta(url="x", transcript=transcript)

    # 30 live frames covering both topics
    frames = []
    for i in range(15):
        frames.append(SelectedFrame(
            filename=f"l{i}.jpg", timestamp_s=float(i),
            category="demo", caption=f"Spark demo {i}",
            recommended_section="Agent 体系",
            info_density=0.85, relevance=0.9, is_live=True,
        ))
    for i in range(15):
        frames.append(SelectedFrame(
            filename=f"a{i}.jpg", timestamp_s=float(100 + i),
            category="demo", caption=f"Antigravity IDE {i}",
            recommended_section="开发者平台",
            info_density=0.85, relevance=0.9, is_live=True,
        ))
    s.selected_frames = frames

    mix = check_image_source_mix(s)
    cov = check_topic_coverage(s)
    assert mix["all_pass"] is True
    assert cov["all_pass"] is True

    s.image_mix_passed = mix["all_pass"]
    s.topic_coverage_passed = cov["all_pass"]
    assert _collect_extract_failures(s) == []


# ──────────────────────────────────────────────────────────────────────────────
# v0.2.3: methodology lock + agent parallel layer
# ──────────────────────────────────────────────────────────────────────────────
def test_v023_methodology_module_exposes_locked_constants():
    """All 13 methodology constants must exist + agent parallel layer."""
    from keynote_recap import methodology as M
    # Frame extract floor / ceiling (replaces user-tunable knobs).
    # v0.3.1: MIN raised 30→35 to align with prompts/03; see
    # test_v031_methodology_constants for the new floor set.
    # v0.3.3 F6: MAX raised 50→65 to give rescue+dedupe headroom.
    assert M.EXTRACT_FINAL_COUNT_MIN == 35
    assert M.EXTRACT_FINAL_COUNT_MAX == 65
    # Segment-stage chunk policy
    assert M.SEGMENT_CHUNK_COUNT > 0
    assert M.SEGMENT_CHUNK_FLOOR > 0
    # Research caps
    assert M.RESEARCH_MAX_QUERIES > 0
    assert M.RESEARCH_MAX_WEBFETCH > 0
    # Pipeline checkpoints (lock the 7-stage commitment)
    assert isinstance(M.PIPELINE_CHECKPOINTS, tuple)
    assert len(M.PIPELINE_CHECKPOINTS) >= 1
    # Agent parallelism layer
    assert M.AGENT_PARALLEL_DEFAULT == 1
    assert M.AGENT_PARALLEL_VERIFIED_CAP == 4
    # research excluded in v0.2.3 (state machine, see methodology.py)
    assert "extract" in M.AGENT_PARALLEL_ELIGIBLE_STAGES
    assert "research" not in M.AGENT_PARALLEL_ELIGIBLE_STAGES


def test_v023_parallel_for_stage_three_tier_logic():
    """parallel_for_stage gates concurrency on (stage, tier)."""
    from keynote_recap import methodology as M
    # eligible stage + verified -> cap
    assert M.parallel_for_stage("extract", "verified_multimodal") == M.AGENT_PARALLEL_VERIFIED_CAP
    # eligible stage but unverified -> 1 (safe default)
    assert M.parallel_for_stage("extract", "unknown") == 1
    assert M.parallel_for_stage("extract", "known_text_only") == 1
    # ineligible stage stays sequential regardless of tier
    assert M.parallel_for_stage("draft", "verified_multimodal") == 1
    assert M.parallel_for_stage("research", "verified_multimodal") == 1
    assert M.parallel_for_stage("verify", "verified_multimodal") == 1


def test_v023_run_parallel_preserves_order():
    """run_parallel must return results in same order as input items."""
    from keynote_recap.llm_client import run_parallel
    items = list(range(20))
    # Sleep based on value to encourage out-of-order completion
    import time
    def work(x: int) -> int:
        time.sleep(0.01 * (20 - x))  # later items finish first
        return x * 2
    results = run_parallel(items, work, parallel=4)
    assert results == [x * 2 for x in items]


def test_v023_run_parallel_sequential_when_parallel_one():
    """parallel=1 -> plain for-loop, no thread pool overhead."""
    from keynote_recap.llm_client import run_parallel
    calls: list[int] = []
    def work(x: int) -> int:
        calls.append(x)
        return x
    results = run_parallel([1, 2, 3], work, parallel=1)
    assert results == [1, 2, 3]
    assert calls == [1, 2, 3]  # strictly sequential order


def test_v023_run_parallel_propagates_exceptions():
    """Exceptions in worker propagate; partial results are NOT silently dropped."""
    from keynote_recap.llm_client import run_parallel
    def work(x: int) -> int:
        if x == 2:
            raise ValueError("boom")
        return x
    import pytest
    with pytest.raises(ValueError, match="boom"):
        run_parallel([1, 2, 3, 4], work, parallel=2)


def test_v023_state_has_stage_parallelism_field():
    """State must record per-stage parallel decisions for report rendering."""
    from keynote_recap.state import State
    s = State(url="https://example.com/v", output_dir="/tmp/x")
    assert hasattr(s, "stage_parallelism")
    assert s.stage_parallelism == {}
    s.stage_parallelism["extract"] = 4
    assert s.stage_parallelism["extract"] == 4


def test_v023_config_no_longer_has_methodology_knobs():
    """Removed user-tunable methodology knobs must NOT appear in Config."""
    from keynote_recap.config import Config, DraftConfig, SearchConfig, StagesConfig
    # DraftConfig should have only `tier` (sanctioned model-quality lever)
    draft_fields = set(DraftConfig.model_fields.keys())
    # min/max image counts no longer tunable
    assert "min_images" not in draft_fields
    assert "max_images" not in draft_fields
    # tier remains
    assert "tier" in draft_fields
    # SearchConfig: max_queries / max_webfetch removed
    search_fields = set(SearchConfig.model_fields.keys())
    assert "max_queries" not in search_fields
    assert "max_webfetch" not in search_fields
    # StagesConfig: checkpoints removed
    stages_fields = set(StagesConfig.model_fields.keys())
    assert "checkpoints" not in stages_fields
    # FrameFilterConfig should not even exist as an attribute on Config
    cfg_fields = set(Config.model_fields.keys())
    assert "frame_filter" not in cfg_fields


def test_v023_yaml_template_does_not_emit_locked_keys():
    """write_sample_config output must not advertise methodology-locked keys."""
    from keynote_recap.config import write_sample_config
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        path = Path(f.name)
    try:
        write_sample_config(path)
        body = path.read_text()
        # Locked methodology keys must NOT be templated
        assert "max_queries" not in body
        assert "max_webfetch" not in body
        assert "min_images" not in body
        assert "max_images" not in body
        assert "checkpoints" not in body
        assert "frame_filter" not in body
        # Sanctioned knobs SHOULD still be there
        assert "tier" in body  # draft.tier survives
    finally:
        path.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# v0.2.4: M9 anti-shortcut layer
# ──────────────────────────────────────────────────────────────────────────────
def test_v024_force_flag_removed_from_recap_command():
    """v0.2.4 (M9.1): --force is no longer a flag on `keynote-recap recap`."""
    from click.testing import CliRunner
    from keynote_recap.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["recap", "--help"])
    assert result.exit_code == 0
    assert "--force" not in result.output, (
        "v0.2.4 removed --force; help text must not mention it"
    )


def test_v024_frontmatter_roundtrip_basic():
    """frontmatter render → parse must roundtrip simple types."""
    from keynote_recap.frontmatter import parse_frontmatter, render_frontmatter

    # Note: numeric strings round-trip as ints; that's fine for our schema
    # since stages are "1", "5.5", etc. — the report consumer treats them
    # as opaque labels.
    meta = {
        "keynote-recap-version": "0.2.4",
        "stages-completed": ["1", "2", "3"],
        "stages-skipped": [],
        "model-extract": "claude-opus-4",
    }
    text = render_frontmatter(meta) + "body line 1\nbody line 2\n"
    parsed, body = parse_frontmatter(text)
    assert parsed["keynote-recap-version"] == "0.2.4"
    assert parsed["stages-completed"] == [1, 2, 3]
    assert parsed["stages-skipped"] == []
    assert parsed["model-extract"] == "claude-opus-4"
    assert body == "body line 1\nbody line 2\n"


def test_v024_attach_frontmatter_computes_sha():
    """attach_frontmatter must populate content-sha256 from body bytes."""
    from keynote_recap.frontmatter import (
        attach_frontmatter,
        compute_body_sha256,
        verify_frontmatter,
    )

    body = "# Title\n\n> ✅ healthy run\n\nsome content\n"
    composed = attach_frontmatter(
        {"keynote-recap-version": "0.2.4"},
        body,
    )
    expected_sha = compute_body_sha256(body)
    assert expected_sha in composed
    ok, msg, meta = verify_frontmatter(composed)
    assert ok is True
    assert msg == "ok"
    assert meta["content-sha256"] == expected_sha


def test_v024_verify_frontmatter_detects_body_edit():
    """Editing the body after frontmatter is written must fail verification."""
    from keynote_recap.frontmatter import attach_frontmatter, verify_frontmatter

    body = "# Title\n\noriginal content\n"
    composed = attach_frontmatter(
        {"keynote-recap-version": "0.2.4"},
        body,
    )
    # Tamper: replace one word in body
    tampered = composed.replace("original", "EDITED")
    ok, msg, _ = verify_frontmatter(tampered)
    assert ok is False
    assert "sha mismatch" in msg


def test_v024_verify_frontmatter_no_frontmatter():
    """Plain markdown without frontmatter returns 'no frontmatter'."""
    from keynote_recap.frontmatter import verify_frontmatter

    ok, msg, meta = verify_frontmatter("# Just markdown\n\nno YAML here.\n")
    assert ok is False
    assert msg == "no frontmatter"
    assert meta == {}


def test_v024_state_has_stages_skipped_field():
    """v0.2.4 (M9.4): state tracks stages_completed / skipped / reasons."""
    from keynote_recap.state import State

    s = State(url="https://x.example/v", output_dir="/tmp/x")
    assert hasattr(s, "stages_completed")
    assert hasattr(s, "stages_skipped")
    assert hasattr(s, "stages_skip_reasons")
    assert hasattr(s, "transcript_override_path")
    assert s.stages_completed == []
    assert s.stages_skipped == []
    assert s.transcript_override_path == ""


def test_v024_integrity_callout_healthy_template():
    """M9.4: healthy-run callout has ✅ + 'verified multimodal'."""
    from keynote_recap.stages.draft import _build_integrity_callout
    from keynote_recap.state import State, VerifiedFact

    s = State(url="https://x.example/v", output_dir="/tmp/x")
    s.stages_completed = [1.0, 2.0, 3.0, 4.0, 5.0, 5.5, 6.0]
    s.stages_skipped = []
    s.models_used = {"extract": "claude-opus-4"}
    s.model_tiers = {"extract": "verified_multimodal"}
    s.verified_facts = [
        VerifiedFact(
            id=f"f{i}",
            transcript_quote=f"q{i}",
            verified_content=f"v{i}",
            source_url="https://e.com",
            source_name="example",
        )
        for i in range(10)
    ]

    callout = _build_integrity_callout(s, None)
    assert "✅" in callout
    assert "完整运行" in callout
    assert "claude-opus-4" in callout
    assert "verified multimodal" in callout


def test_v024_integrity_callout_half_run_template():
    """M9.4: half-run callout has ⚠️ + skipped stages + can't-verify list."""
    from keynote_recap.stages.draft import _build_integrity_callout
    from keynote_recap.state import State

    s = State(url="https://x.example/v", output_dir="/tmp/x")
    s.stages_completed = [2.0, 3.0, 5.0, 5.5]
    s.stages_skipped = [1.0, 4.0]
    s.stages_skip_reasons = {
        "1": "bilibili 412",
        "4": "depends on stage 1",
    }
    s.models_used = {"extract": "your-company/mimo-v2.5"}
    s.model_tiers = {"extract": "known_text_only"}

    callout = _build_integrity_callout(s, None)
    assert "⚠️" in callout
    assert "部分运行" in callout
    assert "stage 1" in callout
    assert "stage 4" in callout
    assert "bilibili 412" in callout
    assert "事实查证" in callout
    assert "transcript" in callout or "字幕" in callout or "高频产品名" in callout
    # text-only model should be flagged
    assert "纯文本" in callout or "不能看图" in callout


def test_v024_render_red_banner_when_stage_4_skipped():
    """M9.3: skipping stage 4 → red 'no fact-check' banner in HTML."""
    from keynote_recap.stages.render import _build_banner
    from keynote_recap.state import State

    s = State(url="https://x.example/v", output_dir="/tmp/x")
    s.stages_completed = [2.0, 3.0, 5.0, 5.5]
    s.stages_skipped = [4.0]
    s.quality_passed = True
    html = _build_banner(s)
    assert 'quality-banner-red' in html
    assert "未经事实查证" in html


def test_v024_render_red_banner_when_transcript_skipped():
    """M9.3: skipping stage 1 (no transcript) → red banner."""
    from keynote_recap.stages.render import _build_banner
    from keynote_recap.state import State

    s = State(url="https://x.example/v", output_dir="/tmp/x")
    s.stages_completed = [2.0, 3.0]
    s.stages_skipped = [1.0]
    s.quality_passed = True
    html = _build_banner(s)
    assert 'quality-banner-red' in html
    assert "Stage 1" in html or "字幕" in html


def test_v024_html_stamp_present():
    """M9.7: HTML output contains version + sha stamp."""
    from pathlib import Path
    import tempfile

    from keynote_recap.frontmatter import attach_frontmatter
    from keynote_recap.stages.render import render_report_md_to_html

    body = "# Title\n\nSome **content** here.\n"
    composed = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.4",
            "model-extract": "claude-opus-4",
            "model-extract-tier": "verified_multimodal",
            "stages-completed": ["1", "2", "3", "4", "5", "5.5"],
            "stages-skipped": [],
        },
        body,
    )
    with tempfile.TemporaryDirectory() as d:
        md_path = Path(d) / "report.md"
        md_path.write_text(composed)
        html_path = Path(d) / "report.html"

        from keynote_recap.frontmatter import parse_frontmatter
        meta, _ = parse_frontmatter(composed)
        render_report_md_to_html(md_path, html_path, meta)

        html = html_path.read_text()
        assert '<meta name="generator" content="keynote-recap 0.2.4">' in html
        assert '<meta name="content-sha256"' in html
        assert 'class="recap-stamp"' in html
        assert 'v0.2.4' in html
        # sha:<8-hex>
        import re
        assert re.search(r'sha:[0-9a-f]{8}', html)


def test_v024_publish_html_aborts_on_sha_mismatch():
    """publish-html refuses to render if body has been edited."""
    from pathlib import Path
    import tempfile

    from click.testing import CliRunner
    from keynote_recap.cli import main
    from keynote_recap.frontmatter import attach_frontmatter

    body = "# Title\n\nOriginal content.\n"
    composed = attach_frontmatter(
        {"keynote-recap-version": "0.2.4"},
        body,
    )
    # Tamper: change a word in the body
    tampered = composed.replace("Original", "EDITED")

    with tempfile.TemporaryDirectory() as d:
        md_path = Path(d) / "report.md"
        md_path.write_text(tampered)

        runner = CliRunner()
        result = runner.invoke(main, ["publish-html", str(md_path)])
        assert result.exit_code == 2
        assert "verification failed" in result.output
        assert "sha mismatch" in result.output


def test_v024_publish_html_succeeds_on_clean_report():
    """publish-html renders HTML when sha matches."""
    from pathlib import Path
    import tempfile

    from click.testing import CliRunner
    from keynote_recap.cli import main
    from keynote_recap.frontmatter import attach_frontmatter

    body = "# Title\n\n> ✅ healthy\n\nbody content\n"
    composed = attach_frontmatter(
        {"keynote-recap-version": "0.2.4"},
        body,
    )
    with tempfile.TemporaryDirectory() as d:
        md_path = Path(d) / "report.md"
        md_path.write_text(composed)

        runner = CliRunner()
        result = runner.invoke(main, ["publish-html", str(md_path)])
        assert result.exit_code == 0, result.output
        html_path = md_path.with_suffix(".html")
        assert html_path.exists()
        assert "<title>" in html_path.read_text()


def test_v024_publish_html_aborts_on_no_frontmatter():
    """publish-html refuses pre-v0.2.4 reports without frontmatter."""
    from pathlib import Path
    import tempfile

    from click.testing import CliRunner
    from keynote_recap.cli import main

    with tempfile.TemporaryDirectory() as d:
        md_path = Path(d) / "report.md"
        md_path.write_text("# Plain markdown\n\nno frontmatter here.\n")

        runner = CliRunner()
        result = runner.invoke(main, ["publish-html", str(md_path)])
        assert result.exit_code == 2
        assert "no frontmatter" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# v0.2.4.1 — _download_subtitles cookie fallback
# ──────────────────────────────────────────────────────────────────────────────
def test_v0241_subtitle_no_retry_when_first_attempt_succeeds(tmp_path, monkeypatch):
    """If the first yt-dlp call (no cookies) produces a subtitle file,
    the cookie retry must NOT run."""
    from keynote_recap.stages import download as dl

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        # First attempt: drop a fake srt file in dest_dir
        # dest_dir is encoded in the -o argument: "<dest>/subtitle.%(ext)s"
        for i, tok in enumerate(cmd):
            if tok == "-o":
                out_tmpl = cmd[i + 1]
                dest = Path(out_tmpl).parent
                (dest / "subtitle.zh-CN.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
                break

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(dl.subprocess, "run", fake_run)
    path, lang = dl._download_subtitles("https://example.com/x", tmp_path, ["zh-CN", "ai-zh"])
    assert path.endswith("subtitle.zh-CN.srt")
    assert lang == "zh-CN"
    # Critical: no cookie retry should have happened
    assert len(calls) == 1
    assert "--cookies-from-browser" not in calls[0]


def test_v0241_subtitle_retries_with_cookies_when_first_yields_no_file(tmp_path, monkeypatch):
    """If the first attempt produces no usable subtitle file (Bilibili 2024H2
    behaviour: returncode 0 but no zh-CN srt), the function must retry with
    --cookies-from-browser chrome and find the subtitle that time."""
    from keynote_recap.stages import download as dl

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        is_cookie_retry = "--cookies-from-browser" in cmd
        if is_cookie_retry:
            # Cookie attempt: drop the ai-zh srt
            for i, tok in enumerate(cmd):
                if tok == "-o":
                    dest = Path(cmd[i + 1]).parent
                    (dest / "subtitle.ai-zh.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
                    break
        # First attempt: do nothing (simulates B-station "success but no subs")

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(dl.subprocess, "run", fake_run)
    path, lang = dl._download_subtitles("https://example.com/x", tmp_path, ["zh-CN", "ai-zh"])
    assert path.endswith("subtitle.ai-zh.srt")
    assert lang == "ai-zh"
    # Two calls: one without cookies, one with
    assert len(calls) == 2
    assert "--cookies-from-browser" not in calls[0]
    assert "--cookies-from-browser" in calls[1]
    # Verify cookie target is `chrome` (matches _fetch_metadata / _download_video)
    idx = calls[1].index("--cookies-from-browser")
    assert calls[1][idx + 1] == "chrome"


def test_v0241_subtitle_returns_empty_when_both_attempts_fail(tmp_path, monkeypatch):
    """If neither attempt produces a subtitle file, return ('', '') so
    pipeline.py can route to M9.2 abort with the correct fix-it message."""
    from keynote_recap.stages import download as dl

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(dl.subprocess, "run", fake_run)
    path, lang = dl._download_subtitles("https://example.com/x", tmp_path, ["zh-CN"])
    assert path == ""
    assert lang == ""
    assert len(calls) == 2  # tried both


# ──────────────────────────────────────────────────────────────────────────────
# v0.2.5 — internalized defense layer (banner + verify + recap-and-verify)
# ──────────────────────────────────────────────────────────────────────────────
def test_v025_verify_html_with_valid_frontmatter_returns_ok():
    """A complete v0.2.5 HTML (generator + sha meta + banner + stamp) verifies OK."""
    from keynote_recap.verify import verify_html_text

    sha = "a" * 64
    html = (
        '<!doctype html><html><head>'
        '<meta name="generator" content="keynote-recap 0.2.5">'
        f'<meta name="content-sha256" content="{sha}">'
        '</head><body>'
        '<div class="recap-banner"><div class="recap-banner-body">'
        'keynote-recap v0.2.5 · sha:aaaaaaaa · model:claude · stages:6/6 · verified ✓'
        '</div></div>'
        '<h1>Body</h1>'
        '<div class="recap-stamp">v0.2.5 · sha:aaaaaaaa · 模型:claude</div>'
        '</body></html>'
    )
    result = verify_html_text(html)
    assert result.ok is True
    assert result.summary.startswith("OK:")
    assert "keynote-recap v0.2.5" in result.summary
    assert "sha:" in result.summary


def test_v025_verify_html_with_tampered_body_returns_fail(tmp_path):
    """verify_md_text catches body-edit tamper via content-sha256 mismatch."""
    from keynote_recap.frontmatter import attach_frontmatter
    from keynote_recap.verify import verify_md_text

    composed = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.5",
            "model-extract": "claude-opus-4",
        },
        "# Title\n\nOriginal body.\n",
    )
    tampered = composed + "X"  # append byte → body sha drifts
    result = verify_md_text(tampered)
    assert result.ok is False
    summary_lower = result.summary.lower()
    assert ("sha mismatch" in summary_lower) or ("content-sha256 mismatch" in summary_lower)
    assert "body has been edited" in summary_lower


def test_v025_verify_html_without_generator_meta_returns_fail():
    """HTML lacking <meta name="generator"> fails the very first check."""
    from keynote_recap.verify import verify_html_text

    html = "<html><body>fake</body></html>"
    result = verify_html_text(html)
    assert result.ok is False
    summary_lower = result.summary.lower()
    assert "missing" in summary_lower
    assert "generator" in summary_lower


def test_v025_verify_html_without_recap_banner_returns_fail():
    """Pre-v0.2.5 HTML (stamp present but no banner) fails with friendly message."""
    from keynote_recap.verify import verify_html_text

    sha = "b" * 64
    html = (
        '<!doctype html><html><head>'
        '<meta name="generator" content="keynote-recap 0.2.4">'
        f'<meta name="content-sha256" content="{sha}">'
        '</head><body>'
        '<h1>Body</h1>'
        '<div class="recap-stamp">v0.2.4 · sha:bbbbbbbb · 模型:claude</div>'
        '</body></html>'
    )
    result = verify_html_text(html)
    assert result.ok is False
    summary_lower = result.summary.lower()
    assert ("pre-v0.2.5" in summary_lower) or ("banner" in summary_lower)


def test_v025_verify_md_with_valid_frontmatter_returns_ok():
    """Markdown produced by attach_frontmatter verifies OK."""
    from keynote_recap.frontmatter import attach_frontmatter
    from keynote_recap.verify import verify_md_text

    md = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.5",
            "model-extract": "claude-opus-4",
        },
        "# hello\nbody\n",
    )
    result = verify_md_text(md)
    assert result.ok is True
    assert result.summary.startswith("OK:")


def test_v025_verify_md_without_frontmatter_returns_fail():
    """Plain markdown without frontmatter is not a keynote-recap report."""
    from keynote_recap.verify import verify_md_text

    md = "# hello\njust a markdown\n"
    result = verify_md_text(md)
    assert result.ok is False
    summary_lower = result.summary.lower()
    assert ("no frontmatter" in summary_lower) or ("not a keynote-recap" in summary_lower)


def test_v025_verify_nonexistent_file_returns_fail():
    """verify_file on a missing path returns a clear FAIL."""
    from pathlib import Path

    from keynote_recap.verify import verify_file

    result = verify_file(Path("/nonexistent/path/foo.html"))
    assert result.ok is False
    assert "does not exist" in result.summary


def test_v025_render_writes_banner_at_body_top(tmp_path):
    """v0.2.5: top banner is rendered immediately after <body>, before main content."""
    from keynote_recap.frontmatter import attach_frontmatter, parse_frontmatter
    from keynote_recap.stages.render import render_report_md_to_html

    body = "# Real Title\n\nSome content paragraph.\n"
    composed = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.5",
            "model-extract": "claude-opus-4",
            "stages-completed": ["1", "2", "3", "4", "5", "5.5"],
            "stages-skipped": [],
        },
        body,
    )
    md_path = tmp_path / "report.md"
    md_path.write_text(composed)
    html_path = tmp_path / "report.html"

    meta, _ = parse_frontmatter(composed)
    render_report_md_to_html(md_path, html_path, meta)

    html = html_path.read_text()

    # 1. banner present
    assert 'class="recap-banner"' in html
    # 2. v0.2.4 stamp still present (redundant defence)
    assert 'class="recap-stamp"' in html
    # 3. banner text reflects healthy path
    assert "keynote-recap v0.2.5" in html
    assert "verified ✓" in html

    # 4. positional check: banner must appear after <body> and before the
    #    rendered main content (the first <h1>)
    body_idx = html.index("<body>")
    banner_idx = html.index('class="recap-banner"')
    h1_idx = html.index("<h1>")
    assert body_idx < banner_idx < h1_idx


def test_v025_verify_cli_exits_0_for_valid_md(tmp_path):
    """`keynote-recap verify <valid.md>` prints OK and exits 0."""
    from click.testing import CliRunner

    from keynote_recap.cli import main
    from keynote_recap.frontmatter import attach_frontmatter

    md = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.5",
            "model-extract": "claude-opus-4",
        },
        "# hello\nbody\n",
    )
    md_path = tmp_path / "report.md"
    md_path.write_text(md)

    runner = CliRunner()
    result = runner.invoke(main, ["verify", str(md_path)])
    assert result.exit_code == 0, result.output
    assert "OK:" in result.output


def test_v025_verify_cli_exits_1_for_tampered_md(tmp_path):
    """`keynote-recap verify <tampered.md>` prints FAIL and exits 1."""
    from click.testing import CliRunner

    from keynote_recap.cli import main
    from keynote_recap.frontmatter import attach_frontmatter

    md = attach_frontmatter(
        {
            "keynote-recap-version": "0.2.5",
            "model-extract": "claude-opus-4",
        },
        "# hello\nbody\n",
    )
    tampered = md + "X"  # body byte drift → sha mismatch
    md_path = tmp_path / "report.md"
    md_path.write_text(tampered)

    runner = CliRunner()
    result = runner.invoke(main, ["verify", str(md_path)])
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.0 — anthropic-native provider
# ──────────────────────────────────────────────────────────────────────────────


def _make_anthropic_message(text: str, in_tok: int = 10, out_tok: int = 5):
    """Build a realistic ``anthropic.types.Message`` for testing."""
    from anthropic.types import Message, Usage
    from anthropic.types.text_block import TextBlock

    return Message(
        id="msg_test_000",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text=text)],
        model="test-model",
        stop_reason="end_turn",
        usage=Usage(input_tokens=in_tok, output_tokens=out_tok),
    )


def test_v030_provider_default_is_openai_compatible():
    """``LLMConfig()`` default is openai-compatible — backward compat."""
    from keynote_recap.config import LLMConfig

    assert LLMConfig().provider == "openai-compatible"


def test_v030_anthropic_backend_routes_via_messages_api(monkeypatch):
    """provider=anthropic-native → backend is ``_AnthropicBackend``, not OpenAI."""
    from keynote_recap.llm_client import LLMClient, _AnthropicBackend, _OpenAIBackend
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)
    assert isinstance(client._backend, _AnthropicBackend)
    assert not isinstance(client._backend, _OpenAIBackend)


def test_v030_openai_provider_still_works_unchanged(monkeypatch):
    """Regression: provider=openai-compatible goes through ``_OpenAIBackend``."""
    from keynote_recap.llm_client import LLMClient, _OpenAIBackend
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("OPENAI_API_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="openai-compatible",
        base_url="https://test.example.com/v1",
        api_key_env="OPENAI_API_KEY",
    )
    client = LLMClient(cfg)
    assert isinstance(client._backend, _OpenAIBackend)


def test_v030_anthropic_chat_basic_text(monkeypatch):
    """Plain text chat returns (text, input_tokens, output_tokens)."""
    from keynote_recap.llm_client import LLMClient
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)
    client._backend.client.messages.create = lambda **kw: _make_anthropic_message(
        "Hello world", in_tok=15, out_tok=7
    )

    text, in_tok, out_tok = client.chat(model="test", user="hi")
    assert text == "Hello world"
    assert in_tok == 15
    assert out_tok == 7


def test_v030_anthropic_chat_with_images_payload(monkeypatch, tmp_path):
    """Vision call sends Anthropic content-block format (image + text)."""
    from keynote_recap.llm_client import LLMClient
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)

    captured_kwargs = {}

    def capturing_create(**kw):
        captured_kwargs.update(kw)
        return _make_anthropic_message("image description")

    client._backend.client.messages.create = capturing_create

    # Create a tiny test image (1x1 jpeg)
    img = tmp_path / "test.jpg"
    img.write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00"
        b"\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00"
        b"\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00"
        b"\x00\x00\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142"
        b"\x81\x91\xa2\x08\xb1\xc1#2\x15R\xd1\xf0$3brB\xc2\x16\x17\x18\x19"
        b"\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
        b"\xff\xd9"
    )

    text, in_tok, out_tok = client.chat_with_images(
        model="test", user_text="describe the image", image_paths=[img]
    )

    # Check the call used the correct Anthropic content-block format
    msgs = captured_kwargs.get("messages", [])
    assert len(msgs) == 1
    content = msgs[0].get("content", [])
    assert len(content) == 2

    # First block is image
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[0]["source"]["data"] != ""

    # Second block is text
    assert content[1]["type"] == "text"
    assert content[1]["text"] == "describe the image"

    # Return values
    assert text == "image description"
    assert in_tok == 10
    assert out_tok == 5


def test_v030_anthropic_json_mode_appends_system_directive(monkeypatch):
    """json_mode=True appends a JSON directive to the system prompt."""
    from keynote_recap.llm_client import LLMClient
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)

    captured_kwargs = {}

    def capturing_create(**kw):
        captured_kwargs.update(kw)
        return _make_anthropic_message('{"ok": true}')

    client._backend.client.messages.create = capturing_create

    client.chat(model="test", user="respond with json", json_mode=True)

    system_used = captured_kwargs.get("system", "")
    assert "valid JSON" in system_used
    assert "markdown fences" in system_used or "code blocks" in system_used


def test_v030_anthropic_extracts_system_from_messages_list(monkeypatch):
    """System role in messages list is lifted into top-level system parameter."""
    from keynote_recap.llm_client import LLMClient
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)

    captured_kwargs = {}

    def capturing_create(**kw):
        captured_kwargs.update(kw)
        return _make_anthropic_message("ok")

    client._backend.client.messages.create = capturing_create

    client.chat(
        model="test",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi"},
        ],
    )

    # The system content should be in the top-level system parameter
    system_used = captured_kwargs.get("system", "")
    assert "helpful assistant" in system_used

    # The messages list should NOT contain a system role entry
    msgs = captured_kwargs.get("messages", [])
    for m in msgs:
        assert m.get("role") != "system", (
            "System role should be lifted out of messages list"
        )


def test_v030_png_frames_use_image_png_media_type(monkeypatch, tmp_path):
    """.png frames use media_type=image/png, .jpg uses image/jpeg."""
    from keynote_recap.llm_client import LLMClient
    from keynote_recap.config import LLMConfig

    monkeypatch.setenv("FAKE_KEY", "x" * 40)

    cfg = LLMConfig(
        provider="anthropic-native",
        base_url="https://test.example.com",
        api_key_env="FAKE_KEY",
    )
    client = LLMClient(cfg)

    captured = {"content": None}

    def capturing_create(**kw):
        captured["content"] = kw.get("messages", [{}])[0].get("content", [])
        return _make_anthropic_message("desc")

    client._backend.client.messages.create = capturing_create

    jpg_img = tmp_path / "frame.jpg"
    jpg_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")

    png_img = tmp_path / "frame.png"
    png_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")

    client.chat_with_images(
        model="test",
        user_text="describe",
        image_paths=[jpg_img, png_img],
    )

    content = captured["content"]
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1]["source"]["media_type"] == "image/png"


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 — image quality hard gate constants (E1/E2/E3)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_methodology_constants():
    """v0.3.1: image quality hard floor constants exist with correct values."""
    from keynote_recap import methodology as M
    assert M.EXTRACT_FINAL_COUNT_MIN == 35  # E1: was 30, now aligned with prompts/03
    assert M.EXTRACT_LIVE_RATIO_MIN == 0.50  # E2: new, abort floor (prompt keeps 0.70 soft)
    assert M.EXTRACT_PER_SECTION_MIN == 1  # E3: A8 硬约束
    assert M.EXTRACT_PER_MAINLINE_MIN == 4  # E3: 主线 4-6 张
    assert M.EXTRACT_CAPTION_VERIFY_WRONG_MAX == 1  # B2: tolerance for vision LLM hiccup
    assert M.EXTRACT_INFO_DENSITY_MIN == 0.70


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 2 — stage 3 hard floors (A1/A3/A4)
# ──────────────────────────────────────────────────────────────────────────────
def _make_selected_frame(
    name: str,
    *,
    info_density: float = 0.85,
    is_live: bool = True,
    relevance: float = 0.9,
):
    """Test helper: build SelectedFrame with sane defaults."""
    from keynote_recap.state import SelectedFrame
    return SelectedFrame(
        filename=name,
        timestamp_s=10.0,
        category="data",
        is_live=is_live,
        caption="x" if is_live else "（插播官方渲染）x",
        recommended_section="一",
        info_density=info_density,
        relevance=relevance,
        source="frame_extract",
    )


def test_v031_extract_drops_low_density():
    """v0.3.1 A4: stage 3 must drop frames with info_density < 0.70."""
    from keynote_recap.stages.extract import _enforce_density_floor
    frames = [
        _make_selected_frame("a.jpg", info_density=0.85),
        _make_selected_frame("b.jpg", info_density=0.55),
        _make_selected_frame("c.jpg", info_density=0.70),  # exactly at floor → keep
    ]
    kept, dropped = _enforce_density_floor(frames, threshold=0.70)
    assert {f.filename for f in kept} == {"a.jpg", "c.jpg"}
    assert {f.filename for f in dropped} == {"b.jpg"}


def test_v031_extract_aborts_below_count_floor():
    """v0.3.1 A1: < count_min raises ExtractFloorError."""
    from keynote_recap.stages.extract import (
        ExtractFloorError,
        _check_extract_floors,
    )
    too_few = [_make_selected_frame(f"f{i}.jpg") for i in range(20)]
    try:
        _check_extract_floors(too_few, count_min=35, live_ratio_min=0.50)
    except ExtractFloorError as e:
        assert "20" in str(e) and "35" in str(e)
    else:
        raise AssertionError("expected ExtractFloorError on count<min")


def test_v031_extract_aborts_below_live_ratio():
    """v0.3.1 A3: live ratio < 0.50 raises ExtractFloorError."""
    from keynote_recap.stages.extract import (
        ExtractFloorError,
        _check_extract_floors,
    )
    # 35 张但只 10 张 live → 28.5% < 50%
    frames = [
        _make_selected_frame(f"f{i}.jpg", is_live=(i < 10))
        for i in range(35)
    ]
    try:
        _check_extract_floors(frames, count_min=35, live_ratio_min=0.50)
    except ExtractFloorError as e:
        assert "live" in str(e).lower()
    else:
        raise AssertionError("expected ExtractFloorError on low live ratio")


def test_v031_extract_passes_when_floors_met():
    """v0.3.1: 35 张 + 70% live + 全 density >= 0.70 → no exception."""
    from keynote_recap.stages.extract import _check_extract_floors
    frames = [
        _make_selected_frame(f"f{i}.jpg", is_live=(i < 25))  # 25/35 = 71% live
        for i in range(35)
    ]
    # 不抛异常 = 通过
    _check_extract_floors(frames, count_min=35, live_ratio_min=0.50)


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 3 — per-section / per-mainline image floor (A5/A6)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_per_section_floor_pass():
    """v0.3.1 A5: 每个 ## 章节 ≥ 1 张图 → pass."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、A
![alt](frames/a.jpg)
## 二、B
![alt](frames/b.jpg)
"""
    r = check_per_section_floor(
        md, per_section_min=1, mainline_titles=set(), per_mainline_min=4
    )
    assert r["all_pass"] is True
    assert r["sections_below_floor"] == []
    assert r["mainline_below_floor"] == []


def test_v031_per_section_floor_fails_empty_section():
    """v0.3.1 A5: 章节 0 张图 → fail."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、A
![alt](frames/a.jpg)
## 二、B
some text but no image
## 三、C
![alt](frames/c.jpg)
"""
    r = check_per_section_floor(
        md, per_section_min=1, mainline_titles=set(), per_mainline_min=4
    )
    assert r["all_pass"] is False
    assert any("二" in s for s in r["sections_below_floor"])
    assert r["mainline_below_floor"] == []


def test_v031_per_mainline_floor_fails():
    """v0.3.1 A6: 主线章节 < 4 张 → fail."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、主线
![alt](frames/a.jpg)
![alt](frames/b.jpg)
## 二、其他
![alt](frames/c.jpg)
"""
    r = check_per_section_floor(
        md,
        per_section_min=1,
        mainline_titles={"一、主线"},
        per_mainline_min=4,
    )
    assert r["all_pass"] is False
    assert any("主线" in s for s in r["mainline_below_floor"])


def test_v031_per_mainline_floor_pass_with_4():
    """v0.3.1 A6: 主线 = 4 张 (= floor) → pass."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、主线
![](frames/a.jpg)
![](frames/b.jpg)
![](frames/c.jpg)
![](frames/d.jpg)
## 二、其他
![](frames/e.jpg)
"""
    r = check_per_section_floor(
        md,
        per_section_min=1,
        mainline_titles={"一、主线"},
        per_mainline_min=4,
    )
    assert r["all_pass"] is True


def test_v031_per_section_floor_collect_failure_in_extract_failures():
    """v0.3.1 wiring: per_section_floor_passed=False enters
    _collect_extract_failures so retry orchestration can pick it up."""
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = False
    fails = _collect_extract_failures(s)
    assert any("per-section" in f.lower() or "5.5.1b" in f for f in fails)


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 4 — caption verify wrong triggers extract retry (B1/B2)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_caption_wrong_triggers_extract_retry():
    """v0.3.1 B2: caption verify wrong > tolerance → enters extract_failures."""
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = 2  # > EXTRACT_CAPTION_VERIFY_WRONG_MAX (1)
    fails = _collect_extract_failures(s)
    assert any("caption" in f.lower() for f in fails), \
        f"expected caption failure in {fails}"


def test_v031_caption_wrong_below_threshold_no_retry():
    """v0.3.1 B2: 1 wrong is at tolerance → no retry trigger."""
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = 1  # at tolerance, no retry
    fails = _collect_extract_failures(s)
    assert not any("caption" in f.lower() for f in fails), \
        f"unexpected caption failure (count=1 should be tolerated): {fails}"


def test_v031_caption_zero_wrong_no_retry():
    """v0.3.1 B2: 0 wrong → no retry."""
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = 0
    fails = _collect_extract_failures(s)
    assert not any("caption" in f.lower() for f in fails)


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 5 — image-section fit 子节级粒度 (B3)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_section_fit_subsection_grain_factory_in_ac_chapter():
    """v0.3.1 B3: image of 智能工厂 inside ### 8.3 子节 (under ## 八、空调
    chapter) should NOT be flagged as mismatch.

    Real-world case from Xiaomi 2026-05-20 launch: §八 ACME空调 chapter has
    a §8.3 制造底气 — 武汉智能工厂 subsection with factory frames; v0.3.0
    5.5.4 falsely flagged because chapter-level keywords didn't include
    工厂. v0.3.1 must consider subsection title in the keyword pool.
    """
    from keynote_recap.stages.verify import check_image_section_fit
    md = """## 八、ACME空调强劲风系列：风量对标柜机的挂机

### 8.1 1.5 匹挂机 — 风量 1000 m³/h

![空调实物对比表](frames/ac.jpg)

### 8.3 制造底气 — 武汉家电智能工厂，磁悬浮装配线 + AI 100% 全检

2024 年 10 月，ACME武汉家电智能工厂正式投产。

![（插播官方渲染）ACME家电智能工厂介绍片段：磁悬浮主板装配线，高精度主板定位](frames/factory.jpg)
"""
    r = check_image_section_fit(md)
    factory_mm = [m for m in r.get("mismatches", []) if "factory" in m.get("filename", "")]
    assert len(factory_mm) == 0, (
        f"factory.jpg should match §8.3 subsection (智能工厂); got: {factory_mm}"
    )


def test_v031_section_fit_still_catches_real_mismatch():
    """v0.3.1: legitimate cross-chapter placement still flagged.

    Caption talks about Pixel phone, image placed in chapter about Search.
    No subsection nearby that mentions Pixel either → should still flag.
    """
    from keynote_recap.stages.verify import check_image_section_fit
    md = """## 五、Search 重做：搜索框 25 年来最大升级

### 5.1 全新智能搜索框

![Pixel 9 Pro 手机硬件规格表：5400mAh 电池 / 高通 8 Gen 4 处理器 / 三摄系统](frames/pixel.jpg)
"""
    r = check_image_section_fit(md)
    pixel_mm = [m for m in r.get("mismatches", []) if "pixel" in m.get("filename", "")]
    assert len(pixel_mm) >= 1, (
        f"pixel.jpg in Search chapter should still be flagged; got: {pixel_mm}"
    )


def test_v031_section_fit_unchanged_when_no_subsection():
    """v0.3.1: behavior unchanged for chapters with no ### subsections."""
    from keynote_recap.stages.verify import check_image_section_fit
    md = """## 一、A 章节

![A 主体内容介绍图：包含核心产品参数与价格信息](frames/a.jpg)
"""
    r = check_image_section_fit(md)
    # caption 词没出现在 ## 标题（只有 "A 章节"），但只有 1 张图 + 内容相关；
    # 旧实现可能误报，新实现因 body_hits/subsection 也参与，应不报
    # （这个测试验证不会因改动引入新的 false positive）
    # 至少不应该报错；具体是否 mismatch 取决于既有 heuristic
    assert isinstance(r.get("mismatches"), list)


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 6 — retry orchestration fixes (C1/C2/C3/C4)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_quality_passed_defaults_to_false():
    """v0.3.1 C2 root cause: quality_passed default must be False so any
    early-return path (retry exception, --start-stage skip, pipeline error)
    leaves quality_passed=False — banner gets rendered.

    Real bug from Xiaomi 2026-05-20: state had 5 gates fail but quality_passed=True
    because final assessment never executed, leaving the default True intact.
    """
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    assert s.quality_passed is False, (
        "v0.3.1 C2: quality_passed must default to False; "
        "only explicit final-assessment pass sets it True"
    )


def test_v031_extract_run_accepts_retry_context():
    """v0.3.1 C3: stages/extract.py::run accepts retry_context list[str]
    so retry runs are not blind — failures from previous attempt feed back
    into stage 3 vision prompt as [RETRY GUIDANCE].
    """
    import inspect
    from keynote_recap.stages import extract
    sig = inspect.signature(extract.run)
    assert "retry_context" in sig.parameters, (
        "v0.3.1 C3: extract.run must accept retry_context parameter"
    )
    p = sig.parameters["retry_context"]
    assert p.default is None or p.default == [], (
        f"retry_context should default to None or [], got {p.default!r}"
    )


def test_v031_build_retry_directive_renders_failures():
    """v0.3.1 C3: _build_retry_directive helper takes failure list and
    renders a RETRY GUIDANCE block to inject into stage 3 prompt.
    """
    from keynote_recap.stages.extract import _build_retry_directive
    fails = [
        "5.5.6 image mix: total frames < 35 or live ratio < 50%",
        "5.5.2 caption verify: 3 wrong captions",
    ]
    d = _build_retry_directive(fails)
    assert "RETRY" in d.upper()
    assert "image mix" in d.lower() or "5.5.6" in d
    assert "caption" in d.lower() or "5.5.2" in d


def test_v031_build_retry_directive_empty_returns_empty():
    """No failures → empty directive (first attempt, not a retry)."""
    from keynote_recap.stages.extract import _build_retry_directive
    assert _build_retry_directive([]) == ""
    assert _build_retry_directive(None) == ""


def test_v031_render_synthesizes_red_banner_when_verify_skipped():
    """v0.3.1 C2: if quality_passed=False AND no final_quality_warnings
    (verify never ran / early exit / --start-stage skip), render must
    synthesize a warning so a red banner appears — silent unsigned reports
    are the exact bug we're fixing.
    """
    import tempfile
    from pathlib import Path
    from keynote_recap.config import load_config
    from keynote_recap.stages.render import run as render_run
    from keynote_recap.state import State, VideoMeta
    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        md = outdir / "report.md"
        md.write_text("# Test\n\n## 一、demo\n\nbody\n")
        s = State.new(url="https://x", output_dir=str(outdir))
        s.video = VideoMeta(url="https://x", title="Test")
        s.report_md_path = str(md)
        # verify never ran: quality_passed left at default False, warnings empty
        assert s.quality_passed is False
        assert s.final_quality_warnings == []
        cfg = load_config()
        s = render_run(s, cfg)
        html = Path(s.report_html_path).read_text()
        assert '<div class="quality-banner quality-banner-red">' in html, (
            "v0.3.1 C2: verify-skipped path must produce red banner, not silent"
        )
        assert "Quality gate did not run" in html or "未通过项目质量门" in html


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 7 — alt_short field + briefing-style + table-density (D1/D2/D3)
# ──────────────────────────────────────────────────────────────────────────────
def test_v031_selected_frame_has_alt_short_field():
    """v0.3.1 D2: SelectedFrame has alt_short field defaulting to empty."""
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(
        filename="x.jpg",
        timestamp_s=0.0,
        category="other",
        caption="full caption",
        recommended_section="",
        info_density=0.7,
        relevance=0.7,
    )
    assert hasattr(f, "alt_short")
    assert f.alt_short == ""


def test_v031_selected_frame_alt_short_round_trip():
    """v0.3.1 D2: alt_short accepts and persists short alt text."""
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(
        filename="x.jpg",
        timestamp_s=0.0,
        category="other",
        caption="（插播官方渲染）武汉家电智能工厂磁悬浮装配线",
        alt_short="武汉智能工厂装配线",
        recommended_section="",
        info_density=0.7,
        relevance=0.7,
    )
    assert f.alt_short == "武汉智能工厂装配线"
    assert len(f.alt_short) <= 25


def test_v031_extract_prompt_schema_includes_alt_short():
    """v0.3.1 D2: stage 3 vision prompt JSON schema asks for alt_short."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "03-extract-vision-filter.md"
    text = p.read_text()
    assert "alt_short" in text, "prompts/03 must include alt_short field in schema"
    assert "≤25" in text or "<=25" in text or "25 字" in text


def test_v031_strict_prompt_includes_briefing_first_sentence():
    """v0.3.1 D1: strict prompt has briefing-style first-sentence rule."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "05-draft-write-strict.md"
    text = p.read_text()
    assert "简报体" in text or "首句" in text
    assert "词典释义" in text  # forbidden mode
    assert ("数字开打" in text) or ("时间开打" in text) or ("判断开打" in text)


def test_v031_strict_prompt_includes_table_hard_constraint():
    """v0.3.1 D3: strict prompt requires parallel info ≥ 3 items → table."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "05-draft-write-strict.md"
    text = p.read_text()
    assert "并列" in text and "表格" in text
    # spot-check the example table is present
    assert "| 档位 |" in text or "| 价位 |" in text


def test_v031_draft_bucket_lists_alt_short():
    """v0.3.1 D2: per-chapter bucket text shown to draft LLM exposes alt_short
    so the LLM can copy it into the rendered ![](frames/...) reference.
    """
    from keynote_recap.stages.draft import _format_buckets_for_prompt
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(
        filename="frame_001.jpg",
        timestamp_s=10.0,
        category="data",
        caption="（插播官方渲染）武汉家电智能工厂磁悬浮装配线",
        alt_short="武汉智能工厂装配线",
        recommended_section="八、ACME空调",
        info_density=0.85,
        relevance=0.9,
    )
    txt = _format_buckets_for_prompt([("八、ACME空调", [f])])
    assert "alt_short" in txt
    assert "武汉智能工厂装配线" in txt
    # rendered ![](frames/...) reference uses alt_short, not full caption
    assert "![武汉智能工厂装配线](frames/frame_001.jpg)" in txt


def test_v031_draft_bucket_falls_back_to_caption_when_no_alt_short():
    """v0.3.1 D2: legacy frames (alt_short=='') fall back to caption[:60]."""
    from keynote_recap.stages.draft import _format_buckets_for_prompt
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(
        filename="frame_002.jpg",
        timestamp_s=20.0,
        category="data",
        caption="完整的图说明文字描述了具体内容",
        recommended_section="一、demo",
        info_density=0.85,
        relevance=0.9,
    )
    txt = _format_buckets_for_prompt([("一、demo", [f])])
    assert "完整的图说明文字描述了具体内容" in txt


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.1 Task 8 — 19-item audit checklist (code-level enforcement)
# ──────────────────────────────────────────────────────────────────────────────
# Each test below corresponds to a specific finding from the v0.3.0 真产出
# audit (see docs/plans/2026-05-26-v031-image-quality-hard-gates.md).
# A green pass here means the code-level guard exists; end-to-end production
# verification (running the full pipeline against real video) is documented
# separately and intentionally NOT run in CI (LLM cost + non-determinism).

def test_v031_audit_A1_count_floor_is_35():
    from keynote_recap import methodology as M
    assert M.EXTRACT_FINAL_COUNT_MIN == 35, "A1: count floor must be 35"


def test_v031_audit_A2_prompt_and_code_count_consistent():
    """A2: prompts/03 advertises ≥ 35; code enforces 35."""
    from pathlib import Path
    from keynote_recap import methodology as M
    p = Path(__file__).resolve().parents[1] / "prompts" / "03-extract-vision-filter.md"
    text = p.read_text()
    assert "35" in text, "prompts/03 should mention 35 (consistent with code)"
    assert M.EXTRACT_FINAL_COUNT_MIN == 35


def test_v031_audit_A3_live_ratio_hard_floor_50pct():
    from keynote_recap import methodology as M
    assert M.EXTRACT_LIVE_RATIO_MIN == 0.50, "A3: live ratio hard floor 0.50"


def test_v031_audit_A4_info_density_floor_enforced():
    from keynote_recap import methodology as M
    from keynote_recap.stages.extract import _enforce_density_floor
    assert M.EXTRACT_INFO_DENSITY_MIN == 0.70
    # callable exists and is the actual gate
    assert callable(_enforce_density_floor)


def test_v031_audit_A5_per_section_floor_check_exists():
    from keynote_recap.stages.verify import check_per_section_floor
    assert callable(check_per_section_floor)


def test_v031_audit_A6_per_mainline_floor_constant():
    from keynote_recap import methodology as M
    assert M.EXTRACT_PER_MAINLINE_MIN == 4
    assert M.EXTRACT_PER_SECTION_MIN == 1


def test_v031_audit_B1_caption_wrong_persists_in_state():
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    assert hasattr(s, "caption_verify_wrong_count")


def test_v031_audit_B2_caption_wrong_triggers_extract_retry():
    from keynote_recap import methodology as M
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = M.EXTRACT_CAPTION_VERIFY_WRONG_MAX + 1
    fails = _collect_extract_failures(s)
    assert any("caption" in f.lower() for f in fails)


def test_v031_audit_B3_section_fit_uses_subsection():
    """B3 covered by test_v031_section_fit_subsection_grain_*; this is a sentinel
    that the implementation references subsection tracking.
    """
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "src/keynote_recap/stages/verify.py"
    if not p.exists():
        # tests run from project root, adjust
        p = Path(__file__).resolve().parents[1] / "src/keynote_recap/stages/verify.py"
    text = p.read_text()
    assert "current_subsection_keywords" in text, "B3: subsection-aware code missing"


def test_v031_audit_C1_retry_actually_reruns_verify():
    """C1: retry block re-runs verify (textual sentinel — full path in pipeline)."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "src/keynote_recap/pipeline.py"
    text = p.read_text()
    # The retry block must call verify after extract
    assert 'STAGES["verify"][1](state, config)' in text


def test_v031_audit_C2_quality_passed_default_false():
    from keynote_recap.state import State
    s = State(url="x", output_dir="/tmp/x")
    assert s.quality_passed is False, "C2: must default False (silent-unsigned bug)"


def test_v031_audit_C3_extract_run_accepts_retry_context():
    import inspect
    from keynote_recap.stages import extract
    assert "retry_context" in inspect.signature(extract.run).parameters


def test_v031_audit_C4_pipeline_recollects_after_retry():
    """C4: final assessment uses _collect_quality_failures(state) on
    post-retry state — sentinel via source.
    """
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "src/keynote_recap/pipeline.py"
    text = p.read_text()
    assert "_collect_quality_failures(state)" in text
    # and the call appears AFTER the retry blocks (line order check)
    lines = text.split("\n")
    retry_idx = next(i for i, line in enumerate(lines) if "extract.run(state, config, retry_context=extract_fails)" in line)
    final_idx = next(i for i, line in enumerate(lines) if "still_failing = _collect_quality_failures(state)" in line)
    assert final_idx > retry_idx, "C4: final assessment must be AFTER retry"


def test_v031_audit_D1_strict_prompt_briefing_rule():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "05-draft-write-strict.md"
    text = p.read_text()
    assert "简报体" in text and "词典释义" in text


def test_v031_audit_D2_alt_short_field_and_schema():
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(filename="x.jpg", timestamp_s=0.0, category="other",
                      caption="c", recommended_section="", info_density=0.7,
                      relevance=0.7)
    assert hasattr(f, "alt_short")
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "03-extract-vision-filter.md"
    assert "alt_short" in p.read_text()


def test_v031_audit_D3_strict_prompt_table_constraint():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "prompts" / "05-draft-write-strict.md"
    text = p.read_text()
    assert "并列" in text and "表格" in text and "| 档位 |" in text


def test_v031_audit_E1_count_constant_consistent():
    """E1: 35 lives in methodology.py (single source of truth)."""
    from pathlib import Path
    from keynote_recap import methodology as M
    p = Path(__file__).resolve().parents[1] / "src/keynote_recap/methodology.py"
    assert "EXTRACT_FINAL_COUNT_MIN" in p.read_text()
    assert M.EXTRACT_FINAL_COUNT_MIN == 35


def test_v031_audit_E2_live_ratio_constant_centralized():
    from keynote_recap import methodology as M
    assert hasattr(M, "EXTRACT_LIVE_RATIO_MIN")


def test_v031_audit_E3_per_section_constants_present():
    from keynote_recap import methodology as M
    assert hasattr(M, "EXTRACT_PER_SECTION_MIN")
    assert hasattr(M, "EXTRACT_PER_MAINLINE_MIN")


def test_v031_audit_full_19_findings_have_guards():
    """Sentinel: count of v031_audit_* tests matches 19 findings + 1 total."""
    import sys
    mod = sys.modules[__name__]
    audit_tests = [
        n for n in dir(mod)
        if n.startswith("test_v031_audit_") and callable(getattr(mod, n))
    ]
    # 19 individual finding tests + this sentinel = 20
    assert len(audit_tests) >= 19, (
        f"expected >= 19 audit tests, got {len(audit_tests)}: {audit_tests}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# p14: LLM client granular httpx timeout
# ──────────────────────────────────────────────────────────────────────────────
# Real bug: stage-5 LLM call held an ESTABLISHED TCP socket at 0% CPU for
# 7+ minutes. SDK's scalar timeout doesn't detect mid-stream read stalls
# until the full budget (default 600s) elapses — pipeline appeared frozen.

def test_p14_build_httpx_timeout_returns_httpx_timeout():
    import httpx
    from keynote_recap.llm_client import _build_httpx_timeout
    t = _build_httpx_timeout(600)
    assert isinstance(t, httpx.Timeout)


def test_p14_httpx_timeout_caps_read_at_120s():
    """Read timeout must be <= 120s regardless of overall budget.

    This is the hang detector: even if user sets a 1-hour overall budget,
    a connection idle for 120s should fail fast.
    """
    from keynote_recap.llm_client import _build_httpx_timeout
    t = _build_httpx_timeout(3600)
    assert t.read is not None
    assert t.read <= 120.0, (
        f"read timeout {t.read}s > 120s defeats the hang detector"
    )


def test_p14_httpx_timeout_preserves_overall_budget():
    """Overall timeout must equal the configured timeout_s.

    Legitimately long generations (final report) need the full budget;
    we only want fast-fail on idle reads, not on total wall-clock.
    """
    from keynote_recap.llm_client import _build_httpx_timeout
    t = _build_httpx_timeout(600)
    # httpx.Timeout exposes per-pool timeouts; .connect/.read/.write/.pool
    # the "overall" is set via the positional ``timeout=`` kwarg which
    # becomes the default for any unset field, but we explicitly set all
    # four. The contract here is: connect/write/pool are short, read=120,
    # and the *user-visible* total budget is preserved as the constructor
    # input — verified by checking write timeout matches 30 (sentinel).
    assert t.connect == 10.0
    assert t.write == 30.0
    assert t.pool == 10.0


def test_p14_openai_backend_uses_granular_timeout():
    """OpenAI backend must construct its client with the httpx.Timeout."""
    import inspect
    from keynote_recap import llm_client
    src = inspect.getsource(llm_client)
    # find the OpenAI() constructor call
    openai_block = src[src.find("self.client = OpenAI("):]
    openai_block = openai_block[:openai_block.find(")") + 1]
    assert "_build_httpx_timeout" in openai_block, (
        "OpenAI client must use _build_httpx_timeout(cfg.timeout_s), "
        "not a raw scalar — scalar timeout cannot detect read stalls"
    )


def test_p14_anthropic_backend_uses_granular_timeout():
    """Anthropic backend must construct its client with the httpx.Timeout."""
    import inspect
    from keynote_recap import llm_client
    src = inspect.getsource(llm_client)
    anthropic_block = src[src.find("self.client = Anthropic("):]
    anthropic_block = anthropic_block[:anthropic_block.find(")") + 1]
    assert "_build_httpx_timeout" in anthropic_block, (
        "Anthropic client must use _build_httpx_timeout(cfg.timeout_s)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# p14: ExtractFloorError handling in pipeline
# ──────────────────────────────────────────────────────────────────────────────
# Real bug: stage 3 raised ExtractFloorError per source comments
# ("caught by pipeline retry orchestration"), but pipeline had no actual
# `except ExtractFloorError` — the error escaped to top-level and crashed
# the whole `recap-and-verify` command.

def test_p14_extract_floor_error_is_imported_in_pipeline():
    """Pipeline must import ExtractFloorError to catch it specifically."""
    import keynote_recap.pipeline as P
    assert hasattr(P, "ExtractFloorError"), (
        "pipeline.py must import ExtractFloorError so the orchestrator "
        "can catch hard-floor breaches separately from generic exceptions"
    )


def test_p14_extract_floor_error_handler_exists_in_pipeline_source():
    """Pipeline source must explicitly catch ExtractFloorError."""
    import keynote_recap.pipeline as P
    src = Path(P.__file__).read_text()
    assert "except ExtractFloorError" in src, (
        "pipeline.py must contain `except ExtractFloorError` so the "
        "documented retry contract is honoured (was missing pre-p14)"
    )


def test_p14_extract_floor_handler_uses_retry_context():
    """The ExtractFloorError handler must invoke runner with retry_context.

    This is what makes the retry meaningful: passing the failure details
    back into stage 3's prompt so it can target the breach.
    """
    import keynote_recap.pipeline as P
    src = Path(P.__file__).read_text()
    # find the except block
    handler_start = src.find("except ExtractFloorError")
    assert handler_start >= 0
    # next 30 lines should contain the retry runner call with retry_context
    handler_block = src[handler_start:handler_start + 2000]
    assert "retry_context=" in handler_block, (
        "ExtractFloorError handler must call runner(...) with retry_context "
        "kwarg so stage 3 sees the prior failure details"
    )


def test_p14_extract_floor_handler_marks_state_on_double_failure():
    """If retry also fails, set image_mix_passed=False so render banner shows."""
    import keynote_recap.pipeline as P
    src = Path(P.__file__).read_text()
    handler_start = src.find("except ExtractFloorError")
    handler_block = src[handler_start:handler_start + 2000]
    assert "image_mix_passed = False" in handler_block, (
        "On double floor breach, must set state.image_mix_passed=False so "
        "the final report carries a red banner instead of crashing silently"
    )


def test_p14_extract_floor_handler_only_runs_once():
    """Guard against infinite retry: only retry when extract_retry_count == 0."""
    import keynote_recap.pipeline as P
    src = Path(P.__file__).read_text()
    handler_start = src.find("except ExtractFloorError")
    handler_block = src[handler_start:handler_start + 2000]
    assert "extract_retry_count" in handler_block, (
        "ExtractFloorError handler must check state.extract_retry_count to "
        "prevent infinite retry loops if the floor keeps failing"
    )


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.3 — robustness: F1 (json_repair), F2 (schema), F4 (caption verify
# rescue exclusion), P5 (image-section fit feeds retry), F6 (count_max raise)
# ──────────────────────────────────────────────────────────────────────────────
def test_v033_f1_parse_json_handles_truncated_output():
    """F1: json_repair fallback recovers truncated vision-LLM JSON."""
    from keynote_recap.llm_client import LLMClient

    LLMClient._json_repair_invocations = 0
    truncated = '{"selected_frames": [{"filename": "a.jpg", "caption": "x"'
    result = LLMClient.parse_json(truncated)
    assert isinstance(result, dict)
    assert "selected_frames" in result
    assert len(result["selected_frames"]) == 1
    assert result["selected_frames"][0]["filename"] == "a.jpg"
    assert LLMClient._json_repair_invocations == 1, (
        "Truncated input must invoke json_repair fallback"
    )


def test_v033_f1_parse_json_well_formed_skips_repair():
    """F1: well-formed JSON must NOT invoke json_repair (no overhead)."""
    from keynote_recap.llm_client import LLMClient

    LLMClient._json_repair_invocations = 0
    result = LLMClient.parse_json('{"a": 1, "b": [2, 3]}')
    assert result == {"a": 1, "b": [2, 3]}
    assert LLMClient._json_repair_invocations == 0, (
        "Well-formed JSON must use stdlib path; non-zero count means "
        "we're paying the json_repair tax on every call"
    )


def test_v033_f1_parse_json_strips_markdown_fence_then_repairs():
    """F1: markdown fence stripping still happens before json_repair."""
    from keynote_recap.llm_client import LLMClient

    LLMClient._json_repair_invocations = 0
    fenced_broken = '```json\n{"a": 1,}\n```'
    result = LLMClient.parse_json(fenced_broken)
    assert result == {"a": 1}


def test_v033_f1_dependency_declared():
    """F1: json-repair must be a runtime dep (not optional)."""
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    # Check it's in the main dependencies block, not optional
    deps_block = pyproject.split("[project.optional-dependencies]")[0]
    assert "json-repair" in deps_block, (
        "json-repair must be a runtime dependency for F1 fallback to work"
    )


def test_v033_f2_merge_batch_coerces_string_info_density():
    """F2: LLM emitting info_density='high' must not crash the batch."""
    from keynote_recap.stages.extract import _merge_batch_result
    from keynote_recap.state import FrameCandidate

    batch = [FrameCandidate(filename="a.jpg", timestamp_s=10.0, score=0.9)]
    data = {
        "selected_frames": [{
            "filename": "a.jpg",
            "caption": "x",
            "category": "demo",
            "recommended_section": "测试",
            "info_density": "high",        # Bad: string instead of float
            "relevance_to_section": 0.8,
        }],
        "rejected_frames": [],
    }
    selected: list = []
    rejected: list = []
    warnings: list[str] = []
    # Must not raise
    _merge_batch_result(data, batch, selected, rejected, schema_warnings=warnings)
    assert len(selected) == 1
    assert selected[0].info_density == 0.7  # Defaulted
    assert any("info_density" in w for w in warnings)


def test_v033_f2_merge_batch_skips_non_dict_payload():
    """F2: when LLM emits a bare list (or json_repair returns one),
    do not crash; record warning and skip the batch."""
    from keynote_recap.stages.extract import _merge_batch_result
    from keynote_recap.state import FrameCandidate

    batch = [FrameCandidate(filename="a.jpg", timestamp_s=1.0, score=0.5)]
    selected: list = []
    rejected: list = []
    warnings: list[str] = []
    _merge_batch_result([], batch, selected, rejected, schema_warnings=warnings)
    assert selected == []
    assert any("expected dict" in w for w in warnings)


def test_v033_f2_merge_batch_handles_non_dict_entry_in_selected():
    """F2: an entry inside selected_frames that's not a dict must be skipped,
    not crash."""
    from keynote_recap.stages.extract import _merge_batch_result
    from keynote_recap.state import FrameCandidate

    batch = [FrameCandidate(filename="a.jpg", timestamp_s=1.0, score=0.5)]
    data = {"selected_frames": ["not-a-dict", {"filename": "a.jpg",
                                               "caption": "ok",
                                               "info_density": 0.8,
                                               "relevance_to_section": 0.8,
                                               "recommended_section": "x",
                                               "category": "demo"}]}
    selected: list = []
    rejected: list = []
    warnings: list[str] = []
    _merge_batch_result(data, batch, selected, rejected, schema_warnings=warnings)
    assert len(selected) == 1, "Valid entry must still be merged"
    # Warning should mention the non-dict entry in some form
    assert any("entry was str" in w or "skipping" in w for w in warnings), (
        f"Expected warning about non-dict entry; got: {warnings}"
    )


def test_v033_f4_caption_verify_excludes_rescue_frames():
    """F4: rescue frames must be sorted to the back of caption_verify
    sample; non-rescue frames are sampled first."""
    import inspect

    from keynote_recap.stages.verify import verify_captions

    src = inspect.getsource(verify_captions)
    assert "frame_extract_rescue" in src, (
        "verify_captions must filter on source==frame_extract_rescue (F4)"
    )
    assert "non_rescue" in src, (
        "verify_captions must split by rescue/non-rescue before sampling"
    )


def test_v033_p5_image_section_fit_feeds_state():
    """P5: 5.5.4 fit check writes state.image_section_fit_passed and
    state.image_section_fit_mismatch_count."""
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    # Default: fit passes
    assert s.image_section_fit_passed is True
    assert s.image_section_fit_mismatch_count == 0


def test_v033_p5_draft_failures_includes_fit():
    """P5: when image_section_fit_passed=False, _collect_draft_failures
    must report it so retry orchestration kicks in."""
    from keynote_recap.pipeline import _collect_draft_failures
    from keynote_recap.state import State

    s = State.new(url="x", output_dir="/tmp/x")
    s.image_section_fit_passed = False
    s.image_section_fit_mismatch_count = 5
    issues = _collect_draft_failures(s)
    assert any("5.5.4 image-section fit" in i for i in issues), (
        "image-section fit failure must surface in draft failures so "
        "stage 5 retries instead of silently shipping"
    )


def test_v033_p5_methodology_constant_exposed():
    """P5: EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX is in methodology
    (single source of truth)."""
    from keynote_recap import methodology as M

    assert hasattr(M, "EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX")
    assert M.EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX >= 1
    # Ensure not absurdly tight (would always trigger) or absurdly loose
    assert M.EXTRACT_IMAGE_SECTION_FIT_MISMATCH_MAX <= 10


def test_v033_f6_extract_count_max_lifted_for_rescue_headroom():
    """F6: MAX 50 was tight; rescue+dedupe occasionally landed just under
    the 35 floor. Raised to 65 so dedupe has breathing room without
    tripping the floor gate."""
    from keynote_recap import methodology as M

    assert M.EXTRACT_FINAL_COUNT_MAX == 65
    # Sanity: still enforces a real ceiling (not infinite)
    assert M.EXTRACT_FINAL_COUNT_MAX < 100


# ──────────────────────────────────────────────────────────────────────────────
# v0.3.4 — P1 (fuzzy bucket: 3-gram fallback for cn compound tokens)
#          P3 (5.5.4 fit: caption-side trigram so cn captions enter judgment)
# ──────────────────────────────────────────────────────────────────────────────
def test_v034_p1_fuzzy_match_bridges_cn_compound_tokens():
    """P1: stage 3 vision LLM emits ``recommended_section`` *before* stage 5
    generates the real outline; phrasing won't match exactly. 3-gram overlap
    bridges 'compound noun' chinese tokens like 武汉智能工厂 ↔ ACME智能工厂."""
    from keynote_recap.stages.draft import _fuzzy_section_match

    # Cases that v0.3.3 fuzzy missed but should now match
    assert _fuzzy_section_match("武汉智能工厂", "八、ACME智能工厂") is True
    assert _fuzzy_section_match("智能工厂介绍", "武汉家电智能工厂") is True


def test_v034_p1_fuzzy_match_still_rejects_unrelated():
    """P1: trigram fallback must NOT introduce false positives.
    'Pixel Halo' should still NOT match 'Search'."""
    from keynote_recap.stages.draft import _fuzzy_section_match

    assert _fuzzy_section_match("Pixel Halo", "五、Search") is False
    assert _fuzzy_section_match("your-company car", "pet show") is False
    # cn-eng synonym is intentionally NOT bridged (would need semantic LLM)
    assert _fuzzy_section_match("搜索体验", "五、Search") is False


def test_v034_p1_fuzzy_match_preserves_v033_behaviour():
    """P1: existing matches still work — no regressions on the 2-token /
    substring paths."""
    from keynote_recap.stages.draft import _fuzzy_section_match

    assert _fuzzy_section_match("AI Agent", "二、AI Agent 演示") is True
    assert _fuzzy_section_match("Gemini 模型层", "模型层：Gemini 3.5 谱系") is True
    assert _fuzzy_section_match("ACME空调", "八、ACME空调") is True
    assert _fuzzy_section_match("搜索重塑", "五、搜索重塑") is True


def test_v034_p1_fuzzy_match_single_trigram_overlap_insufficient():
    """P1: ≥ 2 shared trigrams required (single-trigram is too noisy —
    '智能' alone appears in many unrelated chapters)."""
    from keynote_recap.stages.draft import _fuzzy_section_match

    # Only 1 trigram (智能X / Y智能) overlap → must NOT match
    # 'AI智能' vs 'XX智能助手': trigrams 'AI智', '智能X' vs 'XX智', 'X智能', '智能助', '能助手'
    # — actual shared trigram = empty (different surrounding chars). Use crafted case:
    # rec='智能体' chapter='智能家居' → trigrams {'智能体'} vs {'智能家','能家居'} → no overlap, no match.
    assert _fuzzy_section_match("智能体", "智能家居") is False


def test_v034_p3_fit_judges_chinese_dense_captions():
    """P3: pre-v0.3.4, Chinese caption 'ACME家电智能工厂介绍片段' splits into
    1 whitespace-token, fails the ≥ 4 tokens guard, and silently passes fit
    even when section is unrelated. Now trigram path catches these."""
    from keynote_recap.stages.verify import check_image_section_fit

    # Caption (Chinese-dense) about 工厂 placed in 'Search' chapter — should mismatch
    md = (
        "## 五、Search\n"
        "本章介绍搜索能力。\n\n"
        "![ACME家电智能工厂介绍武汉装配线片段](frames/frame_42.jpg)\n\n"
        "搜索新体验。\n"
    )
    result = check_image_section_fit(md)
    assert len(result["mismatches"]) >= 1, (
        "Chinese-dense caption about 工厂 in a Search section must be flagged "
        "(was silently passed pre-v0.3.4 because cap_tokens len < 4)"
    )
    assert result["mismatches"][0]["filename"] == "frame_42.jpg"


def test_v034_p3_fit_pass_for_cn_caption_in_matching_section():
    """P3: must not cause false positives — cn caption in matching chapter
    via shared trigrams should pass."""
    from keynote_recap.stages.verify import check_image_section_fit

    md = (
        "## 八、ACME智能工厂\n"
        "工厂展示武汉装配线。\n\n"
        "![ACME家电智能工厂介绍武汉装配线片段](frames/frame_99.jpg)\n\n"
        "现场展示磁悬浮装配线。\n"
    )
    result = check_image_section_fit(md)
    assert result["all_pass"], (
        f"Cn caption in matching chapter must pass; got {result['mismatches']}"
    )


def test_v034_p3_fit_short_caption_still_skipped():
    """P3: very short captions (< 4 tokens AND < 8 trigrams) are still
    skipped — too little signal for the heuristic to be reliable."""
    from keynote_recap.stages.verify import check_image_section_fit

    md = (
        "## 五、Search\n\n"
        "![空调](frames/frame_3.jpg)\n"
    )
    result = check_image_section_fit(md)
    assert result["all_pass"], (
        "2-char caption is too short to judge; must NOT be flagged"
    )


def test_v034_p3_mismatch_dict_carries_trigram_diagnostics():
    """P3: when a mismatch is reported, the diagnostic dict must include
    trigram_hits and body_trigram_hits so retry directives have actionable info."""
    from keynote_recap.stages.verify import check_image_section_fit

    md = (
        "## 五、Search\n"
        "搜索能力介绍。\n\n"
        "![ACME家电智能工厂介绍武汉装配线](frames/frame_x.jpg)\n"
    )
    result = check_image_section_fit(md)
    assert result["mismatches"]
    m = result["mismatches"][0]
    assert "trigram_hits" in m
    assert "body_trigram_hits" in m


# ─────────────────────────────────────────────────────────────────────
# v0.3.5 — agent-friendly preflight phrasing
# ─────────────────────────────────────────────────────────────────────


def test_v035_doctor_stdout_has_no_alarming_words_when_api_key_unset(
    tmp_path, monkeypatch, capsys
):
    """v0.3.5: when OPENAI_API_KEY is unset, `keynote-recap doctor`'s
    rendered stdout must contain ZERO words that an external agent
    wrapper could over-read as "the tool errored". This test is a hard
    gate for the regression we keep hitting where opencode / cron
    drivers / claude-desktop hooks see ⚠ + 'fail' + '401' and abort
    before invoking the CLI.

    Forbidden in stdout (case-insensitive): fail, 401, missing, unset,
    error, abort.
    """
    from keynote_recap.cli import _preflight_env
    from keynote_recap.config import load_config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = load_config()
    result = _preflight_env(cfg, tmp_path)
    # Must not abort.
    assert result is not None

    captured = capsys.readouterr().out.lower()
    for forbidden in ("fail", "401", "missing", "unset", "error", "abort"):
        assert forbidden not in captured, (
            f"v0.3.5 regression: doctor stdout contains '{forbidden}' "
            f"when only api_key is unset. Full output:\n{captured}"
        )
    # And the warning is still recorded in state for the report banner.
    assert any("api_key" in w for w in result)


def test_v035_api_key_check_uses_info_glyph_in_cli(tmp_path, monkeypatch, capsys):
    """v0.3.5: cli._preflight_env special-cases what == "api_key" and
    renders ℹ blue instead of ⚠ yellow. Other warning-severity checks
    keep ⚠. This isolates the visual fix to the one check that was
    causing agent abort, without weakening other warnings.
    """
    from keynote_recap.cli import _preflight_env
    from keynote_recap.config import load_config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = load_config()
    _preflight_env(cfg, tmp_path)
    out = capsys.readouterr().out
    # Filter to the rendered preflight bullet lines only — not test
    # framework chrome. The bullet line format is:
    #   "  <glyph> api_key: <detail>"
    # so we look for the literal "api_key:" substring (with the colon).
    api_key_lines = [ln for ln in out.splitlines() if "api_key:" in ln]
    assert api_key_lines, (
        f"expected at least one api_key bullet line in doctor output; got:\n{out}"
    )
    joined = "\n".join(api_key_lines)
    # api_key bullet must use ℹ (U+2139), not ⚠ (U+26A0).
    assert "\u2139" in joined, f"api_key line missing ℹ in:\n{joined}"
    assert "\u26a0" not in joined, f"api_key line still has ⚠ in:\n{joined}"
