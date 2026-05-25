"""Unified LLM client over OpenAI-compatible endpoints.

Supports text, vision (images), and JSON-mode. Uses tenacity for retries.
Returns (text, input_tokens, output_tokens) so cost_tracker can record.

v0.2.3: adds ``chat_batch`` for project-controlled parallel calls. The
concurrency level is set by ``methodology.parallel_for_stage`` based on
the stage's model tier — users do not get to override it.
"""
from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, TypeVar

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import LLMConfig

T = TypeVar("T")
R = TypeVar("R")


class LLMClient:
    """OpenAI-compatible chat client with retry."""

    def __init__(self, cfg: LLMConfig) -> None:
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Environment variable {cfg.api_key_env} not set. "
                f"Export it or change `llm.api_key_env` in config."
            )
        self.cfg = cfg
        self.client = OpenAI(
            api_key=api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
        )

    # ──────────────────────────────────────────────────────────────────
    # Text chat
    # ──────────────────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def chat(
        self,
        *,
        model: str,
        system: str = "",
        user: str = "",
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.5,
        max_tokens: int = 8000,
        json_mode: bool = False,
    ) -> tuple[str, int, int]:
        """Send chat request. Returns (text, input_tokens, output_tokens)."""
        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": user})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return text, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)

    # ──────────────────────────────────────────────────────────────────
    # Vision chat (with image inputs)
    # ──────────────────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def chat_with_images(
        self,
        *,
        model: str,
        system: str = "",
        user_text: str = "",
        image_paths: list[Path],
        temperature: float = 0.2,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> tuple[str, int, int]:
        """Send chat request with image inputs."""
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

        for p in image_paths:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{data}"},
            })

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return text, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def parse_json(text: str) -> Any:
        """Robust JSON parsing — strips markdown fences if present."""
        t = text.strip()
        if t.startswith("```"):
            # Remove first and last code fence lines
            lines = t.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines)
        return json.loads(t)


def run_parallel(
    items: list[T],
    work: Callable[[T], R],
    *,
    parallel: int,
) -> list[R]:
    """Run ``work(item)`` for each item with bounded concurrency.

    Order of returned results matches order of ``items``. Concurrency is
    project-controlled (see ``methodology.parallel_for_stage``); users
    cannot override it.

    A ``parallel=1`` value forces sequential execution (no thread pool
    overhead, identical semantics to a plain for-loop) — this is the
    default for unverified models so behavior matches v0.2.2.

    Exceptions in ``work`` propagate to the caller; partial results are
    NOT silently dropped (caller decides whether to retry vs. abort).
    """
    if parallel <= 1 or len(items) <= 1:
        return [work(it) for it in items]

    results: list[R] = [None] * len(items)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(work, it): i for i, it in enumerate(items)}
        for fut in futures:
            idx = futures[fut]
            results[idx] = fut.result()
    return results
