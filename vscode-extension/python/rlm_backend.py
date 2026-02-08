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
from typing import Any

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
        self.rlm_instance: Any = None  # RLM or None

    def configure(self, msg: dict[str, Any]) -> None:
        """Process a 'configure' message from the extension."""
        self.provider = msg.get("provider", "builtin")
        self.max_iterations = msg.get("maxIterations", 30)
        self.max_output_chars = msg.get("maxOutputChars", 20000)
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
        # For api_key mode, backend and backend_kwargs come directly from config

        self.configured = True
        self.rlm_instance = None  # Force re-creation on next completion
        send_msg({"type": "configured", "provider": self.provider, "backend": self.backend})

    def get_or_create_rlm(self, persistent: bool = False) -> Any:
        """Lazily create the RLM instance."""
        if self.rlm_instance is not None:
            return self.rlm_instance

        from rlm.core.rlm import RLM

        rlm_kwargs: dict[str, Any] = {
            "backend": self.backend,
            "backend_kwargs": self.backend_kwargs,
            "environment": "local",
            "environment_kwargs": {},
            "max_iterations": self.max_iterations,
            "persistent": persistent,
        }

        # Wire up sub-LM if configured
        if self.sub_backend and self.sub_backend_kwargs:
            rlm_kwargs["other_backends"] = [self.sub_backend]
            rlm_kwargs["other_backend_kwargs"] = [self.sub_backend_kwargs]

        self.rlm_instance = RLM(**rlm_kwargs)
        return self.rlm_instance


STATE = BackendState()

# ── Command handlers ─────────────────────────────────────────────────


def handle_configure(msg: dict[str, Any]) -> None:
    STATE.configure(msg)


def handle_completion(msg: dict[str, Any]) -> None:
    """Run a full RLM completion and send back the result."""
    nonce = msg.get("nonce", "")
    prompt = msg.get("prompt", "")
    context = msg.get("context")
    root_prompt = msg.get("rootPrompt")
    persistent = msg.get("persistent", False)

    if not STATE.configured:
        send_error(nonce, "Backend not configured. Send a 'configure' message first.")
        return

    try:
        rlm = STATE.get_or_create_rlm(persistent=persistent)

        # The context (file contents, references, etc.) is the main payload.
        # The prompt is the user's question.
        payload = context if context else prompt

        result = rlm.completion(prompt=payload, root_prompt=root_prompt or prompt)
        response_text = result.response if hasattr(result, "response") else str(result)
        send_result(nonce, response_text)

    except Exception as e:
        send_error(nonce, f"{type(e).__name__}: {e}")


def handle_execute(msg: dict[str, Any]) -> None:
    """Execute raw code in the REPL — used for FINAL_VAR resolution and testing."""
    nonce = msg.get("nonce", "")
    code = msg.get("code", "")

    if not STATE.configured:
        send_error(nonce, "Backend not configured.")
        return

    try:
        from rlm.environments.local_repl import LocalREPL

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
