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
