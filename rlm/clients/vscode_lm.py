"""
VsCodeLM — a BaseLM client that delegates LLM calls back to the VS Code
extension host via the JSON-over-newline stdio bridge.

When the RLM loop runs in rlm_backend.py (spawned by the TypeScript extension),
it needs a way to call the language model. In "builtin" mode the extension owns
the vscode.lm API, so this client sends an ``llm_request`` message over stdout
and blocks until the extension replies on stdin.

Protocol (stdout → extension):
    {"type": "llm_request", "nonce": "<uuid>", "prompt": "<text>", "model": null}

Protocol (stdin ← extension):
    {"type": "llm_response", "nonce": "<uuid>", "text": "<response>"}
  or
    {"type": "llm_response", "nonce": "<uuid>", "error": "<msg>"}

This is the *only* BaseLM implementation that has zero external dependencies —
it relies entirely on the host process bridge.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class VsCodeLM(BaseLM):
    """LM client that relays completions to a VS Code Language Model via stdio."""

    def __init__(
        self,
        model_name: str = "vscode-lm",
        send_fn: Callable[[dict[str, Any]], None] | None = None,
        register_response_fn: Callable[[str, threading.Event, dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            model_name: Identifier surfaced in usage summaries.
            send_fn: Callable that writes a JSON dict to stdout (the bridge).
                     If None, defaults to writing to sys.stdout.
            register_response_fn: Callable(nonce, event, container) that the
                     backend's stdin reader calls ``event.set()`` on when a
                     matching ``llm_response`` arrives.  ``container["text"]``
                     or ``container["error"]`` will be populated.
        """
        super().__init__(model_name=model_name, **kwargs)
        self._send = send_fn or self._default_send
        self._register = register_response_fn
        self._lock = threading.Lock()

        # Usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.last_prompt_tokens: int = 0
        self.last_completion_tokens: int = 0

    # ── IO helpers ───────────────────────────────────────────────────

    @staticmethod
    def _default_send(msg: dict[str, Any]) -> None:
        line = json.dumps(msg) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()

    def _roundtrip(self, prompt: str, model: str | None = None) -> str:
        """Send an llm_request and block until the extension responds."""
        nonce = uuid.uuid4().hex
        request: dict[str, Any] = {
            "type": "llm_request",
            "nonce": nonce,
            "prompt": prompt,
            "model": model,
        }

        if self._register is None:
            raise RuntimeError(
                "VsCodeLM requires register_response_fn to be set. "
                "This client must be used inside rlm_backend.py."
            )

        event = threading.Event()
        container: dict[str, Any] = {}
        self._register(nonce, event, container)

        self._send(request)

        # Block until the extension replies (5 min timeout for long LLM calls)
        if not event.wait(timeout=300):
            raise TimeoutError(f"VsCodeLM: no response for nonce={nonce} after 300s")

        if "error" in container:
            raise RuntimeError(f"VsCodeLM: extension returned error: {container['error']}")

        return container["text"]

    # ── BaseLM interface ─────────────────────────────────────────────

    def completion(
        self, prompt: str | list[dict[str, Any]] | dict[str, Any], model: str | None = None
    ) -> str:
        if isinstance(prompt, list):
            # Flatten message list into a single string for the bridge
            parts = []
            for msg in prompt:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"[{role}]: {content}")
            prompt_str = "\n".join(parts)
        elif isinstance(prompt, dict):
            prompt_str = json.dumps(prompt)
        else:
            prompt_str = str(prompt)

        model = model or self.model_name
        self.model_call_counts[model] += 1

        result = self._roundtrip(prompt_str, model)

        # We don't get token counts from the VS Code LM API on the Python side,
        # but we track call counts for usage summaries.
        return result

    async def acompletion(
        self, prompt: str | list[dict[str, Any]] | dict[str, Any], model: str | None = None
    ) -> str:
        # The VS Code bridge is synchronous (stdin/stdout), so async
        # just delegates to the sync version.
        return self.completion(prompt, model)

    def get_usage_summary(self) -> UsageSummary:
        summaries: dict[str, ModelUsageSummary] = {}
        for model in self.model_call_counts:
            summaries[model] = ModelUsageSummary(
                total_calls=self.model_call_counts[model],
                total_input_tokens=self.model_input_tokens[model],
                total_output_tokens=self.model_output_tokens[model],
            )
        return UsageSummary(model_usage_summaries=summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.last_prompt_tokens,
            total_output_tokens=self.last_completion_tokens,
        )
