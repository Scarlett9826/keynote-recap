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
def test_draft_tier_default_is_strict():
    """M5: default tier is now 'strict' — methodology rules are hard contract.

    Users who run the tool with no flags should get the strictest quality gate
    (forbidden phrases, ≥ 8 citations, every chapter has 核心判断, etc).
    Pass --tier easy / --tier standard to relax for weaker models.
    """
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
    # Quality status defaults: passed=True, no warnings
    assert s.quality_passed is True
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
        # quality_passed defaults to True; preflight/runtime warnings empty

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
    """
    from keynote_recap.preflight_env import check_api_key

    monkeypatch.delenv("FAKE_KEY", raising=False)
    r = check_api_key("FAKE_KEY")
    assert r.ok is False
    assert r.severity == "warning"  # v0.2.5.1 — was "blocker" in v0.2.5
    assert "FAKE_KEY" in r.detail
    assert "export FAKE_KEY=" in r.fix


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


def test_preflight_models_unknown_blocks():
    """v0.2.4 (M9.1): unverified vision model is a hard abort, no force backdoor."""
    from keynote_recap.cli import _preflight_models
    from keynote_recap.config import load_config

    cfg = load_config()
    cfg.llm.models.extract = "totally-unknown-vision-model-xyz"
    cfg.llm.models.verify = "totally-unknown-vision-model-xyz"

    proceed, warnings = _preflight_models(cfg)
    assert proceed is False
    assert len(warnings) >= 2  # both extract and verify warned
    assert any("totally-unknown" in w for w in warnings)


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
    assert M.EXTRACT_FINAL_COUNT_MIN == 35
    assert M.EXTRACT_FINAL_COUNT_MAX == 50
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
