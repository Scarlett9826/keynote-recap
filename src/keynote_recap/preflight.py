"""Preflight model-capability check.

Some pipeline stages (3 frame filter, 5.5.2 caption verify) require the LLM
to *actually look at images*. If a user picks a pure-text model the prompt's
capability probe will trip and the stage will hard-fail. Better: warn the
user before any work starts.

This module classifies a model name into one of three tiers:

  - ``verified_multimodal``: known to work end-to-end on the project's
    quality bar (Claude Opus 4 / Sonnet 4, Gemini 2.5 Pro, GPT-4o, etc.)
  - ``known_text_only``: explicitly text-only models the project has seen
    silent-fail (mimo, gpt-4o-mini text variant, deepseek-v3 text, etc.)
  - ``unknown``: anything not on either list — print a soft warning but
    let the user proceed.

Matching is case-insensitive, prefix-or-substring based, since users
often prefix the model name with a provider id (``openai/gpt-4o``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ModelTier(Enum):
    VERIFIED_MULTIMODAL = "verified_multimodal"
    KNOWN_TEXT_ONLY = "known_text_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelCheck:
    """Result of preflight check for a single model name."""

    name: str
    tier: ModelTier
    matched_pattern: str | None
    note: str


# Patterns are matched against the lowercased model name with re.search.
# Order matters: more specific patterns first.
_VERIFIED_MULTIMODAL_PATTERNS: tuple[tuple[str, str], ...] = (
    # Anthropic Claude (multimodal since Claude 3)
    (r"claude[-_ ]?(opus|sonnet)[-_ ]?(4|3\.7|3\.5)", "Claude Opus/Sonnet 4 (multimodal, 200K)"),
    (r"claude[-_ ]?3(\.5|\.7)?[-_ ]?(opus|sonnet|haiku)", "Claude 3 family (multimodal)"),
    # Google Gemini (multimodal since 1.5)
    (r"gemini[-_ ]?2\.5[-_ ]?pro", "Gemini 2.5 Pro (multimodal, 1M context)"),
    (r"gemini[-_ ]?(2\.0|1\.5)[-_ ]?(pro|flash)", "Gemini 1.5/2.0 family (multimodal)"),
    # OpenAI GPT-4 with vision
    (r"gpt[-_ ]?4o(?!-mini)", "GPT-4o (multimodal, 128K)"),
    (r"gpt[-_ ]?4[-_ ]?turbo", "GPT-4 Turbo (multimodal)"),
    (r"gpt[-_ ]?4[-_ ]?vision", "GPT-4 Vision"),
)


_KNOWN_TEXT_ONLY_PATTERNS: tuple[tuple[str, str], ...] = (
    # Xiaomi MiMo (text-only)
    (r"mimo", "MiMo is text-only; stage 3 / 5.5.2 will fail the capability probe"),
    # OpenAI mini / text variants
    (r"gpt[-_ ]?4o[-_ ]?mini", "GPT-4o-mini text variant lacks reliable vision for this workload"),
    (r"gpt[-_ ]?3\.5", "GPT-3.5 has no vision"),
    # DeepSeek
    (r"deepseek[-_ ]?(v3|chat|coder|r1)", "DeepSeek V3/R1 are text-only"),
    # Qwen text variants (qwen-vl is multimodal, qwen-max/plus default text)
    (r"qwen[-_ ]?(max|plus|turbo)(?![-_ ]?vl)", "Qwen Max/Plus/Turbo (non-VL) are text-only"),
    (r"qwen[-_ ]?3", "Qwen-3 default is text-only (use qwen-vl for vision)"),
    # Generic small/text-only
    (r"llama[-_ ]?(3|3\.1)[-_ ]?(?!.*vision)", "Llama 3/3.1 default is text-only"),
    (r"yi[-_ ]?(34b|6b|9b)(?!.*vl)", "Yi text variants are text-only"),
)


def check_model_capability(model_name: str) -> ModelCheck:
    """Classify a model name into one of three capability tiers.

    Args:
        model_name: The model identifier as configured (may include provider
            prefix, e.g. ``"openai/gpt-4o"`` or ``"claude-opus-4"``).

    Returns:
        A ``ModelCheck`` with the tier, the regex that matched (if any), and
        a human-readable note suitable for CLI display.
    """
    if not model_name:
        return ModelCheck(
            name=model_name,
            tier=ModelTier.UNKNOWN,
            matched_pattern=None,
            note="No model name configured.",
        )

    lowered = model_name.lower()

    # Check known-bad first so we surface the strongest warning
    for pattern, note in _KNOWN_TEXT_ONLY_PATTERNS:
        if re.search(pattern, lowered):
            return ModelCheck(
                name=model_name,
                tier=ModelTier.KNOWN_TEXT_ONLY,
                matched_pattern=pattern,
                note=note,
            )

    for pattern, note in _VERIFIED_MULTIMODAL_PATTERNS:
        if re.search(pattern, lowered):
            return ModelCheck(
                name=model_name,
                tier=ModelTier.VERIFIED_MULTIMODAL,
                matched_pattern=pattern,
                note=note,
            )

    return ModelCheck(
        name=model_name,
        tier=ModelTier.UNKNOWN,
        matched_pattern=None,
        note="Not on the verified-multimodal list. Continue only if you know "
             "this model supports image input.",
    )


VERIFIED_MODELS_DOC = """\
Verified multimodal models (any of these will work):

  - claude-opus-4 / claude-sonnet-4         (Anthropic, 200K context)
  - gemini-2.5-pro                          (Google, 1M context — best price/perf)
  - gpt-4o / gpt-4-turbo                    (OpenAI, 128K context)

Known to NOT work (will silent-fail on stage 3 / 5.5.2):

  - mimo-2.5-pro, mimo-*                    (Xiaomi MiMo, text-only)
  - gpt-4o-mini, gpt-3.5-*                  (OpenAI text variants)
  - deepseek-v3, deepseek-r1                (text-only)
  - qwen-max, qwen-plus, qwen-turbo         (use qwen-vl for vision)
  - llama-3, llama-3.1                      (text-only by default)

Set the model via ``KEYNOTE_RECAP_MODEL`` env var, ``--llm`` CLI flag, or
``llm.models.*`` in config.yaml. See README → 'Model Selection' for details."""
