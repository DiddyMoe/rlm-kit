#!/usr/bin/env python3
"""
rlm_backend.py — Full RLM backend for the VS Code / Cursor extension.

Replaces the old repl_bridge.py stub.  This process is spawned by the
TypeScript extension (backendBridge.ts) and communicates over JSON-over-
newline on stdin/stdout.

Architecture:
  • Extension sends {"type":"configure", ...} on startup with provider config
  • Extension sends {"type":"completion", "nonce": ..., "prompt": ..., "context": ...}
  • This backend runs RLM.completion() which may emit:
      {"type":"llm_request", "nonce":..., "prompt":...}  (builtin mode only)
    and expects:
      {"type":"llm_response", "nonce":..., "text":...}
  • When completion finishes:
      {"type":"result", "nonce":..., "text":...}
  • Progress/iteration updates:
      {"type":"progress", "nonce":..., "iteration":..., "maxIterations":..., "text":...}

Provider modes:
  builtin   → Uses VsCodeLM client (routes through extension's vscode.lm API)
  api_key   → Uses get_client() with the specified backend + API key

This process also watches for parent death and self-terminates.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from typing import Any, cast

# ── Parent PID watcher ───────────────────────────────────────────────
_PARENT_PID = os.getppid()


def _watch_parent(interval: float = 2.0) -> None:
    """Kill self if parent process dies (orphan protection)."""
    while True:
        time.sleep(interval)
        if os.getppid() != _PARENT_PID:
            os._exit(0)


threading.Thread(target=_watch_parent, daemon=True).start()

# ── JSON-over-newline IO ─────────────────────────────────────────────

_stdout_lock = threading.Lock()


def send_msg(msg: dict[str, Any]) -> None:
    """Write a JSON message to stdout (to the extension host).

    Thread-safe: multiple threads (completion, execute, VsCodeLM round-trips)
    may call this concurrently.  The lock prevents interleaved writes that
    would produce corrupt JSON lines on the TS side.
    """
    line = json.dumps(msg, default=str) + "\n"
    with _stdout_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


def send_error(nonce: str | None, error: str) -> None:
    send_msg({"type": "error", "nonce": nonce, "error": error})


def send_result(nonce: str, text: str) -> None:
    send_msg({"type": "result", "nonce": nonce, "text": text})


def send_chunk(nonce: str, text: str) -> None:
    send_msg({"type": "chunk", "nonce": nonce, "text": text})


def send_progress(nonce: str, iteration: int, max_iterations: int, text: str = "") -> None:
    send_msg(
        {
            "type": "progress",
            "nonce": nonce,
            "iteration": iteration,
            "maxIterations": max_iterations,
            "text": text,
        }
    )


class SoftCancelRequested(Exception):
    pass


# ── Response registry for VsCodeLM round-trips ──────────────────────
_pending_llm: dict[str, tuple[threading.Event, dict[str, Any]]] = {}
_pending_lock = threading.Lock()


def register_llm_response(nonce: str, event: threading.Event, container: dict[str, Any]) -> None:
    """Register a pending LLM request so the stdin reader can resolve it."""
    with _pending_lock:
        _pending_llm[nonce] = (event, container)


def resolve_llm_response(nonce: str, payload: dict[str, Any]) -> None:
    """Called by stdin reader when an llm_response arrives."""
    with _pending_lock:
        entry = _pending_llm.pop(nonce, None)
    if entry is None:
        return
    event, container = entry
    container.update(payload)
    event.set()


# ── Progress logger (emits progress messages during completion loop) ──


class ProgressLogger:
    """Logger that emits progress messages to the extension (no file output)."""

    def __init__(self) -> None:
        self._iteration_count = 0
        self._last_response = ""

    def reset(self) -> None:
        self._iteration_count = 0
        self._last_response = ""

    def get_last_response(self) -> str:
        return self._last_response

    def log_metadata(self, metadata: Any) -> None:
        """No-op for metadata (we only care about iterations for progress)."""
        pass

    def log(self, iteration: Any) -> None:
        """On each iteration, send a progress message to the extension."""
        self._iteration_count += 1
        nonce = getattr(STATE, "current_progress_nonce", "") or ""
        max_iter = getattr(STATE, "current_progress_max_iterations", 30) or 30
        response = getattr(iteration, "response", None) or ""
        self._last_response = response
        if STATE.cancel_requested.is_set():
            raise SoftCancelRequested()
        text = response[:500]
        send_progress(nonce, self._iteration_count, max_iter, text)


# ── Backend state ────────────────────────────────────────────────────


class BackendState:
    """Singleton holding configuration and the RLM instance."""

    def __init__(self) -> None:
        self.configured = False
        self.provider: str = "builtin"  # "builtin" | "api_key"
        self.backend: str = "vscode_lm"
        self.backend_kwargs: dict[str, Any] = {}
        self.sub_backend: str | None = None
        self.sub_backend_kwargs: dict[str, Any] | None = None
        self.max_iterations: int = 30
        self.max_output_chars: int = 20000
        self.environment: str = "local"
        self.rlm_instance: Any = None  # RLM or None
        self.progress_logger = ProgressLogger()
        self.current_progress_nonce: str = ""
        self.current_progress_max_iterations: int = 30
        self.cancel_requested = threading.Event()

    def emit_root_chunk(self, chunk: str) -> None:
        """Emit a root-stream chunk tied to the currently active completion nonce."""
        nonce = self.current_progress_nonce
        if not nonce or not chunk:
            return
        send_chunk(nonce, chunk)

    def configure(self, msg: dict[str, Any]) -> None:
        """Process a 'configure' message from the extension."""
        self.provider = msg.get("provider", "builtin")
        self.max_iterations = msg.get("maxIterations", 30)
        self.max_output_chars = msg.get("maxOutputChars", 20000)
        self.environment = msg.get("environment", "local")
        self.backend = msg.get("backend", "vscode_lm")
        self.backend_kwargs = msg.get("backendKwargs", {})
        self.sub_backend = msg.get("subBackend")
        self.sub_backend_kwargs = msg.get("subBackendKwargs")

        if self.provider == "builtin":
            # Use VsCodeLM which routes through the extension's LM API
            self.backend = "vscode_lm"
            self.backend_kwargs = {
                "model_name": msg.get("model", "vscode-lm"),
                "send_fn": send_msg,
                "register_response_fn": register_llm_response,
            }
        else:
            self._apply_litellm_backend_aliases()
        # For api_key mode, backend and backend_kwargs come directly from config

        self.configured = True
        self.rlm_instance = None  # Force re-creation on next completion
        send_msg({"type": "configured", "provider": self.provider, "backend": self.backend})

    def _apply_litellm_backend_aliases(self) -> None:
        """Map extension-only backend names to litellm provider routing."""
        aliases: dict[str, str] = {
            "openrouter": "openrouter",
            "vercel": "vercel",
            "vllm": "vllm",
        }

        provider = aliases.get(self.backend)
        if provider is None:
            return

        model_name = self.backend_kwargs.get("model_name")
        if isinstance(model_name, str) and model_name:
            prefixed_model_name = (
                model_name if model_name.startswith(f"{provider}/") else f"{provider}/{model_name}"
            )
            self.backend_kwargs["model_name"] = prefixed_model_name

        self.backend = "litellm"

    def get_or_create_rlm(self, persistent: bool = False) -> Any:
        """Lazily create the RLM instance."""
        if self.rlm_instance is not None:
            return self.rlm_instance

        from rlm.core.rlm import RLM, RLMConfig

        rlm_kwargs: dict[str, Any] = {
            "backend": self.backend,
            "backend_kwargs": self.backend_kwargs,
            "environment": self.environment,
            "environment_kwargs": {},
            "max_iterations": self.max_iterations,
            "persistent": persistent,
            "logger": self.progress_logger,
            "on_root_chunk": self.emit_root_chunk,
        }

        # Wire up sub-LM if configured
        if self.sub_backend and self.sub_backend_kwargs:
            rlm_kwargs["other_backends"] = [self.sub_backend]
            rlm_kwargs["other_backend_kwargs"] = [self.sub_backend_kwargs]

        self.rlm_instance = RLM(RLMConfig(**rlm_kwargs))
        return self.rlm_instance


STATE = BackendState()

# ── Command handlers ─────────────────────────────────────────────────


def handle_configure(msg: dict[str, Any]) -> None:
    STATE.configure(msg)


def _create_rlm_for_completion(persistent: bool) -> Any:
    return STATE.get_or_create_rlm(persistent=persistent)


def _resolve_completion_inputs(msg: dict[str, Any]) -> tuple[str, str, Any, str | None, bool]:
    nonce = cast(str, msg.get("nonce", ""))
    prompt = cast(str, msg.get("prompt", ""))
    context = msg.get("context")
    root_prompt_raw = msg.get("rootPrompt")
    root_prompt = root_prompt_raw if isinstance(root_prompt_raw, str) else None
    persistent = cast(bool, msg.get("persistent", False))
    return nonce, prompt, context, root_prompt, persistent


def _start_completion_tracking(nonce: str) -> None:
    STATE.current_progress_nonce = nonce
    STATE.current_progress_max_iterations = STATE.max_iterations
    STATE.progress_logger.reset()
    STATE.cancel_requested.clear()


def _completion_payload(prompt: str, context: Any) -> Any:
    return context if context else prompt


def _emit_soft_cancelled_result(nonce: str) -> None:
    best_so_far = STATE.progress_logger.get_last_response()
    if not best_so_far:
        best_so_far = "Request cancelled before any completed iteration produced output."
    chunk_size = 256
    for index in range(0, len(best_so_far), chunk_size):
        send_chunk(nonce, best_so_far[index : index + chunk_size])
    send_result(nonce, best_so_far)


def _finish_completion_tracking() -> None:
    STATE.current_progress_nonce = ""
    STATE.cancel_requested.clear()


def handle_completion(msg: dict[str, Any]) -> None:
    """Run a full RLM completion and send back the result."""
    nonce, prompt, context, root_prompt, persistent = _resolve_completion_inputs(msg)

    if not STATE.configured:
        send_error(nonce, "Backend not configured. Send a 'configure' message first.")
        return

    _start_completion_tracking(nonce)

    try:
        rlm = _create_rlm_for_completion(persistent=persistent)
        payload = _completion_payload(prompt, context)
        result = rlm.completion(prompt=payload, root_prompt=root_prompt if root_prompt else prompt)
        response_text = result.response if hasattr(result, "response") else str(result)
        send_result(nonce, response_text)

    except SoftCancelRequested:
        _emit_soft_cancelled_result(nonce)

    except Exception as e:
        send_error(nonce, f"{type(e).__name__}: {e}")
    finally:
        _finish_completion_tracking()


def handle_execute(msg: dict[str, Any]) -> None:
    """Execute raw code in the REPL — used for FINAL_VAR resolution and testing."""
    nonce = msg.get("nonce", "")
    code = msg.get("code", "")

    if not STATE.configured:
        send_error(nonce, "Backend not configured.")
        return

    try:
        from rlm.environments.local_repl import LocalREPL

        repl = None
        if STATE.rlm_instance is not None:
            repl = getattr(STATE.rlm_instance, "_persistent_env", None)

        if repl is None:
            repl = LocalREPL(context_payload="")

        result = repl.execute_code(code)
        send_msg(
            {
                "type": "exec_result",
                "nonce": nonce,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": bool(result.stderr),
            }
        )
    except Exception as e:
        send_msg(
            {
                "type": "exec_result",
                "nonce": nonce,
                "stdout": "",
                "stderr": str(e),
                "error": True,
            }
        )


def handle_ping(msg: dict[str, Any]) -> None:
    nonce = msg.get("nonce", "")
    send_msg({"type": "pong", "nonce": nonce})


def handle_cancel(_msg: dict[str, Any]) -> None:
    STATE.cancel_requested.set()


def handle_shutdown(_msg: dict[str, Any]) -> None:
    """Graceful shutdown."""
    if STATE.rlm_instance is not None:
        try:
            STATE.rlm_instance.close()
        except Exception:
            pass
    sys.exit(0)


HANDLERS: dict[str, Any] = {
    "configure": handle_configure,
    "completion": handle_completion,
    "cancel": handle_cancel,
    "execute": handle_execute,
    "ping": handle_ping,
    "shutdown": handle_shutdown,
}


# ── Stdin reader ─────────────────────────────────────────────────────


def stdin_reader() -> None:
    """Read JSON messages from stdin in a dedicated thread."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type", "")

        # LLM responses are routed to pending VsCodeLM requests
        if msg_type == "llm_response":
            nonce = msg.get("nonce", "")
            resolve_llm_response(nonce, msg)
            continue

        # Dispatch to handler
        handler = HANDLERS.get(msg_type)
        if handler:
            # Run completion in a separate thread so stdin keeps reading
            if msg_type in ("completion", "execute"):
                threading.Thread(target=handler, args=(msg,), daemon=True).start()
            else:
                handler(msg)
        else:
            send_error(msg.get("nonce"), f"Unknown message type: {msg_type}")

    # stdin closed → parent died
    sys.exit(0)


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    # Ignore SIGINT — let the parent handle it
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    send_msg({"type": "ready"})
    stdin_reader()


if __name__ == "__main__":
    main()
