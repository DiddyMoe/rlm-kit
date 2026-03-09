from __future__ import annotations

import json
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from rlm.environments.daytona_repl import DaytonaREPL
from rlm.environments.docker_repl import DockerREPL
from rlm.environments.e2b_repl import E2BREPL
from rlm.environments.modal_repl import ModalREPL
from rlm.environments.prime_repl import PrimeREPL


def _payload(
    stdout: str = "ok", stderr: str = "", locals_dict: dict[str, Any] | None = None
) -> str:
    return json.dumps({"stdout": stdout, "stderr": stderr, "locals": locals_dict or {"x": "1"}})


class _FakeStream:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text


class _FakeModalProcess:
    def __init__(self, stdout_text: str, stderr_text: str = "") -> None:
        self.stdout = _FakeStream(stdout_text)
        self.stderr = _FakeStream(stderr_text)


class _FakeSandboxExecResult:
    def __init__(self, stdout_text: str, stderr_text: str = "") -> None:
        self.stdout = stdout_text
        self.stderr = stderr_text


def _modal_exec(*args: object, **kwargs: object) -> _FakeModalProcess:
    _ = args, kwargs
    return _FakeModalProcess(_payload())


def _prime_execute_command(*args: object, **kwargs: object) -> _FakeSandboxExecResult:
    _ = args, kwargs
    return _FakeSandboxExecResult(_payload())


def _noop(*args: object, **kwargs: object) -> None:
    _ = args, kwargs


def _daytona_exec(*args: object, **kwargs: object) -> SimpleNamespace:
    _ = args, kwargs
    return SimpleNamespace(exit_code=0, result=_payload())


def _e2b_run(*args: object, **kwargs: object) -> SimpleNamespace:
    _ = args, kwargs
    return SimpleNamespace(stdout=_payload(), stderr="")


class TestIsolatedExecuteCode:
    def test_docker_execute_code_parses_payload(self) -> None:
        repl = DockerREPL.__new__(DockerREPL)
        repl.cleanup = lambda: None
        repl.container_id = "container"
        repl.proxy_port = 1234
        repl.depth = 1
        repl.pending_calls = []
        repl.calls_lock = threading.Lock()

        with patch("rlm.environments.docker_repl.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(stdout=_payload(), stderr="", returncode=0)
            result = repl.execute_code("print('ok')")

        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.locals["x"] == "1"

    def test_modal_execute_code_parses_payload(self) -> None:
        repl = ModalREPL.__new__(ModalREPL)
        repl.cleanup = lambda: None
        repl.depth = 1
        repl.BROKER_PORT = 8080
        repl.pending_llm_calls = []
        repl.calls_lock = threading.Lock()
        repl.sandbox = SimpleNamespace(exec=_modal_exec)

        result = repl.execute_code("print('ok')")

        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.locals["x"] == "1"

    def test_prime_execute_code_parses_payload(self) -> None:
        repl = PrimeREPL.__new__(PrimeREPL)
        repl.cleanup = lambda: None
        repl.depth = 1
        repl.BROKER_PORT = 8888
        repl.pending_llm_calls = []
        repl.calls_lock = threading.Lock()
        repl.sandbox_id = "sid"
        repl.client = SimpleNamespace(execute_command=_prime_execute_command)

        result = repl.execute_code("print('ok')")

        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.locals["x"] == "1"

    def test_daytona_execute_code_parses_payload(self) -> None:
        repl = DaytonaREPL.__new__(DaytonaREPL)
        repl.cleanup = lambda: None
        repl.depth = 1
        repl.timeout = 5
        repl.BROKER_PORT = 8080
        repl.pending_llm_calls = []
        repl.calls_lock = threading.Lock()
        repl.sandbox = SimpleNamespace(
            fs=SimpleNamespace(upload_file=_noop),
            process=SimpleNamespace(exec=_daytona_exec),
        )

        result = repl.execute_code("print('ok')")

        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.locals["x"] == "1"

    def test_e2b_execute_code_parses_payload(self) -> None:
        repl = E2BREPL.__new__(E2BREPL)
        repl.cleanup = lambda: None
        repl.depth = 1
        repl.BROKER_PORT = 8889
        repl.pending_llm_calls = []
        repl.calls_lock = threading.Lock()
        repl.sandbox = SimpleNamespace(
            files=SimpleNamespace(write=_noop),
            commands=SimpleNamespace(run=_e2b_run),
        )

        result = repl.execute_code("print('ok')")

        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.locals["x"] == "1"
