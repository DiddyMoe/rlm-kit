import importlib.util
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from rlm.clients.vscode_lm import VsCodeLM


def _load_backend_module() -> ModuleType:
    backend_path = (
        Path(__file__).resolve().parents[1] / "vscode-extension" / "python" / "rlm_backend.py"
    )
    spec = importlib.util.spec_from_file_location("test_rlm_backend_module", backend_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load rlm_backend module spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def backend_module() -> ModuleType:
    return _load_backend_module()


def test_completion_handler_dispatches_and_sends_result(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[dict[str, Any]] = []

    def _send_msg(msg: dict[str, Any]) -> None:
        messages.append(msg)

    monkeypatch.setattr(backend_module, "send_msg", _send_msg)

    class StubRLM:
        def completion(self, prompt: object, root_prompt: str) -> SimpleNamespace:
            assert prompt == "hello"
            assert root_prompt == "hello"
            return SimpleNamespace(response="done")

    backend_module.STATE.configured = True
    backend_module.STATE.max_iterations = 5
    backend_module.STATE.cancel_requested.clear()
    monkeypatch.setattr(
        backend_module.STATE, "get_or_create_rlm", lambda persistent=False: StubRLM()
    )

    backend_module.HANDLERS["completion"]({"type": "completion", "nonce": "n1", "prompt": "hello"})

    assert messages[-1] == {"type": "result", "nonce": "n1", "text": "done"}


def test_execute_handler_dispatches_and_sends_exec_result(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[dict[str, Any]] = []

    def _send_msg(msg: dict[str, Any]) -> None:
        messages.append(msg)

    monkeypatch.setattr(backend_module, "send_msg", _send_msg)

    backend_module.STATE.configured = True
    backend_module.STATE.rlm_instance = None

    backend_module.HANDLERS["execute"]({"type": "execute", "nonce": "n2", "code": "print('ok')"})

    assert messages[-1]["type"] == "exec_result"
    assert messages[-1]["nonce"] == "n2"
    assert messages[-1]["stdout"] == "ok\n"
    assert messages[-1]["stderr"] == ""
    assert messages[-1]["error"] is False


def test_ping_handler_dispatches_and_sends_pong(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[dict[str, Any]] = []

    def _send_msg(msg: dict[str, Any]) -> None:
        messages.append(msg)

    monkeypatch.setattr(backend_module, "send_msg", _send_msg)

    backend_module.HANDLERS["ping"]({"type": "ping", "nonce": "n3"})

    assert messages[-1] == {"type": "pong", "nonce": "n3"}


def test_completion_handler_sends_error_when_unconfigured(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[dict[str, Any]] = []

    def _send_msg(msg: dict[str, Any]) -> None:
        messages.append(msg)

    monkeypatch.setattr(backend_module, "send_msg", _send_msg)

    backend_module.STATE.configured = False

    backend_module.HANDLERS["completion"]({"type": "completion", "nonce": "n4", "prompt": "hello"})

    assert messages[-1]["type"] == "error"
    assert messages[-1]["nonce"] == "n4"
    assert "Backend not configured" in str(messages[-1]["error"])


def test_configure_handler_updates_state(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[dict[str, Any]] = []

    def _send_msg(msg: dict[str, Any]) -> None:
        messages.append(msg)

    monkeypatch.setattr(backend_module, "send_msg", _send_msg)

    backend_module.STATE.configured = False
    backend_module.STATE.rlm_instance = object()

    backend_module.HANDLERS["configure"](
        {
            "type": "configure",
            "provider": "api_key",
            "backend": "openai",
            "model": "gpt-4o-mini",
            "backendKwargs": {"api_key": "test-key", "model_name": "gpt-4o-mini"},
            "maxIterations": 7,
            "maxOutputChars": 9999,
            "environment": "local",
        }
    )

    assert backend_module.STATE.configured is True
    assert backend_module.STATE.provider == "api_key"
    assert backend_module.STATE.backend == "openai"
    assert backend_module.STATE.backend_kwargs["api_key"] == "test-key"
    assert backend_module.STATE.max_iterations == 7
    assert backend_module.STATE.max_output_chars == 9999
    assert backend_module.STATE.environment == "local"
    assert backend_module.STATE.rlm_instance is None
    assert messages[-1] == {"type": "configured", "provider": "api_key", "backend": "openai"}


def test_cancel_handler_sets_cancel_requested(backend_module: ModuleType) -> None:
    backend_module.STATE.cancel_requested.clear()

    backend_module.HANDLERS["cancel"]({"type": "cancel"})

    assert backend_module.STATE.cancel_requested.is_set()


def test_llm_request_round_trip_resolves_pending_response(backend_module: ModuleType) -> None:
    requests: list[dict[str, Any]] = []

    def send_fn(payload: dict[str, Any]) -> None:
        requests.append(payload)
        backend_module.resolve_llm_response(
            str(payload["nonce"]),
            {
                "type": "llm_response",
                "nonce": payload["nonce"],
                "text": "mock completion",
                "promptTokens": 3,
                "completionTokens": 5,
            },
        )

    client = VsCodeLM(
        model_name="vscode-lm",
        send_fn=send_fn,
        register_response_fn=backend_module.register_llm_response,
    )

    result = client.completion("hello", model="vscode-lm")

    assert result == "mock completion"
    assert len(requests) == 1
    request = requests[0]
    assert request["type"] == "llm_request"
    assert request["prompt"] == "hello"
    assert request["model"] == "vscode-lm"


def test_shutdown_handler_closes_rlm_and_exits(
    backend_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = threading.Event()

    class StubRLM:
        def close(self) -> None:
            closed.set()

    backend_module.STATE.rlm_instance = StubRLM()
    exit_codes: list[int] = []

    def fake_exit(code: int) -> None:
        exit_codes.append(code)

    monkeypatch.setattr(backend_module.sys, "exit", fake_exit)

    backend_module.HANDLERS["shutdown"]({"type": "shutdown"})

    assert closed.is_set()
    assert exit_codes == [0]
