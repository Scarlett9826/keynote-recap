"""LLM cost tracking.

Pricing data is approximate (2026-05). Updated separately from code.
For unknown models, returns 0.0 with a debug warning.
"""
from __future__ import annotations

from datetime import datetime

from .state import CostEntry, State


# Pricing in USD per 1M tokens (input / output). Approximate as of 2026-05.
PRICING_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-4":           (15.0, 75.0),
    "claude-sonnet-4":         ( 3.0, 15.0),
    "claude-haiku-4":          ( 0.8,  4.0),
    "claude-3-5-sonnet":       ( 3.0, 15.0),
    "claude-3-5-haiku":        ( 1.0,  5.0),

    # OpenAI
    "gpt-4o":                  ( 2.5, 10.0),
    "gpt-4o-mini":             ( 0.15, 0.6),
    "o1":                      (15.0, 60.0),
    "o3-mini":                 ( 1.1,  4.4),

    # Google
    "gemini-2.5-pro":          ( 1.25, 5.0),
    "gemini-2.5-flash":        ( 0.075, 0.3),

    # Local / unknown (free)
    "local":                   ( 0.0,  0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost. Falls back to 0.0 with warning for unknown models."""
    # Strip vendor prefix (e.g., "anthropic/claude-opus-4" → "claude-opus-4")
    key = model.split("/")[-1]

    if key not in PRICING_PER_M_TOKENS:
        # Try fuzzy match
        for k in PRICING_PER_M_TOKENS:
            if k in key or key in k:
                key = k
                break
        else:
            return 0.0

    in_rate, out_rate = PRICING_PER_M_TOKENS[key]
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


def track(
    state: State,
    *,
    stage: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> CostEntry:
    """Append a cost entry to state and return it."""
    entry = CostEntry(
        timestamp=datetime.now().isoformat(),
        stage=stage,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(model, input_tokens, output_tokens),
    )
    state.cost_entries.append(entry)
    return entry


def format_summary(state: State) -> str:
    """Pretty cost summary string."""
    if not state.cost_entries:
        return "No LLM calls recorded."

    lines = ["═══ Cost Summary ═══"]
    by_stage: dict[str, list[CostEntry]] = {}
    for e in state.cost_entries:
        by_stage.setdefault(e.stage, []).append(e)

    for stage, entries in by_stage.items():
        total = sum(e.cost_usd for e in entries)
        in_t = sum(e.input_tokens for e in entries)
        out_t = sum(e.output_tokens for e in entries)
        lines.append(
            f"  {stage:12s} | {len(entries):3d} calls | "
            f"in {in_t/1000:7.1f}K | out {out_t/1000:7.1f}K | ${total:6.3f}"
        )

    total = state.total_cost_usd()
    lines.append(f"  {'─' * 60}")
    lines.append(f"  {'TOTAL':12s} | ${total:.3f}")
    return "\n".join(lines)
