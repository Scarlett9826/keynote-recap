"""Unified LLM client dispatching to OpenAI-compatible or Anthropic-native backends.

``LLMClient`` is a thin facade.  At ``__init__`` it chooses
``_OpenAIBackend`` or ``_AnthropicBackend`` based on ``cfg.provider``.
Public API (``chat`` / ``chat_with_images`` / ``parse_json``) is unchanged
from v0.2.x — every ``stages/*`` caller works unmodified.

Supports text, vision (images), and JSON-mode.  Uses tenacity for retries.
Returns ``(text, input_tokens, output_tokens)`` so cost_tracker can record.

v0.2.3: adds ``chat_batch`` for project-controlled parallel calls. The
concurrency level is set by ``methodology.parallel_for_stage`` based on
the stage's model tier — users do not get to override it.

v0.3.0: ``_AnthropicBackend`` — native Anthropic Messages API provider.
"""
from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, TypeVar

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import LLMConfig

T = TypeVar("T")
R = TypeVar("R")


# ──────────────────────────────────────────────────────────────────────────────
# Abstract backend
# ──────────────────────────────────────────────────────────────────────────────


class _Backend(ABC):
    """Internal protocol — every backend implements ``chat`` and
    ``chat_with_images`` with identical signatures so the facade is glue."""

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI-compatible backend (v0.2.x behaviour, byte-identical)
# ──────────────────────────────────────────────────────────────────────────────


class _OpenAIBackend(_Backend):
    """Existing v0.2.x behaviour — byte-identical to the original LLMClient."""

    def __init__(self, cfg: LLMConfig) -> None:
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Environment variable {cfg.api_key_env} not set. "
                f"Export it or change `llm.api_key_env` in config."
            )
        self.client = OpenAI(
            api_key=api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
        )

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


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic-native backend (v0.3.0)
# ──────────────────────────────────────────────────────────────────────────────


class _AnthropicBackend(_Backend):
    """Native Anthropic Messages API backend.

    Used when ``cfg.provider == "anthropic-native"``.  Supports text and
    vision through the ``/messages`` endpoint.  ``json_mode`` is emulated
    via system-prompt directive (Anthropic has no ``response_format``
    parameter).
    """

    def __init__(self, cfg: LLMConfig) -> None:
        from anthropic import Anthropic

        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Environment variable {cfg.api_key_env} not set. "
                f"Export it or change `llm.api_key_env` in config."
            )

        # The Anthropic SDK always prepends /v1 to the resource path
        # (it POSTs to {base_url}/v1/messages).  Strip a user-supplied
        # ``/v1`` suffix so the config URL ``https://gateway/anthropic/v1``
        # results in the correct request
        # ``https://gateway/anthropic/v1/messages`` rather than
        # ``https://gateway/anthropic/v1/v1/messages``.
        base = cfg.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]

        self.client = Anthropic(
            api_key=api_key,
            base_url=base,
            timeout=cfg.timeout_s,
        )

    # ── helpers shared by chat / chat_with_images ──────────────────────

    @staticmethod
    def _assemble_system(system: str, json_mode: bool) -> str:
        """Combine caller system prompt with optional JSON directive."""
        parts = [system] if system else []
        if json_mode:
            parts.append(
                "You must respond with valid JSON only. "
                "Do not include any explanatory text, markdown fences, or code blocks."
            )
        return "\n\n".join(parts)

    @staticmethod
    def _text_from_response(resp) -> str:
        """Concatenate text blocks from an Anthropic messages response.

        ``resp.content`` is a list of ``ContentBlock`` objects.  Vision
        responses always carry at least one ``text`` block.
        """
        return "".join(b.text for b in resp.content if b.type == "text")

    @staticmethod
    def _usage_from_response(resp) -> tuple[int, int]:
        """Extract (input_tokens, output_tokens) from an Anthropic response."""
        return resp.usage.input_tokens, resp.usage.output_tokens

    # ── text chat ──────────────────────────────────────────────────────

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
        system_prompt = self._assemble_system(system, json_mode)

        if messages is not None:
            # Lift any ``role: "system"`` entries into the top-level system
            # parameter (Anthropic Messages API does not support system role
            # inside the messages array).
            system_from_messages = [
                m["content"] for m in messages if m.get("role") == "system"
            ]
            if system_from_messages:
                system_prompt = "\n\n".join(
                    [system_prompt] + system_from_messages
                ).strip() if system_prompt else "\n\n".join(system_from_messages)
            anthr_messages = [
                m for m in messages if m.get("role") != "system"
            ]
        else:
            anthr_messages = [{"role": "user", "content": user}]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": anthr_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        resp = self.client.messages.create(**kwargs)
        text = self._text_from_response(resp)
        in_tok, out_tok = self._usage_from_response(resp)
        return text, in_tok, out_tok

    # ── vision chat ────────────────────────────────────────────────────

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
        system_prompt = self._assemble_system(system, json_mode)

        # Anthropic content-block format: images BEFORE text
        content: list[dict[str, Any]] = []
        for p in image_paths:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": data,
                },
            })
        content.append({"type": "text", "text": user_text})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        resp = self.client.messages.create(**kwargs)
        text = self._text_from_response(resp)
        in_tok, out_tok = self._usage_from_response(resp)
        return text, in_tok, out_tok


# ──────────────────────────────────────────────────────────────────────────────
# Public facade — unchanged public API from v0.2.x
# ──────────────────────────────────────────────────────────────────────────────


class LLMClient:
    """Facade that dispatches to the correct backend based on ``cfg.provider``.

    Public method signatures are identical to v0.2.x — every ``stages/*``
    caller works unmodified.

    Use ``cfg.llm.provider`` (from config.yaml) to choose the backend:
      - ``openai-compatible`` (default) — ``_OpenAIBackend``
      - ``anthropic-native`` (v0.3.0) — ``_AnthropicBackend``
    """

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        if cfg.provider == "anthropic-native":
            self._backend: _Backend = _AnthropicBackend(cfg)
        else:
            self._backend = _OpenAIBackend(cfg)

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
        return self._backend.chat(
            model=model,
            system=system,
            user=user,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

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
        return self._backend.chat_with_images(
            model=model,
            system=system,
            user_text=user_text,
            image_paths=image_paths,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    @staticmethod
    def parse_json(text: str) -> Any:
        """Robust JSON parsing — strips markdown fences if present, with json_repair fallback."""
        t = text.strip()
        if t.startswith("```"):
            lines = t.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines)
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            try:
                from json_repair import repair_json
                repaired = repair_json(t)
                return json.loads(repaired)
            except Exception:
                raise


# ──────────────────────────────────────────────────────────────────────────────
# Helper — module-level (unchanged from v0.2.x)
# ──────────────────────────────────────────────────────────────────────────────


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

    results: list[R] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(work, it): i for i, it in enumerate(items)}
        for fut in futures:
            idx = futures[fut]
            results[idx] = fut.result()
    return results
