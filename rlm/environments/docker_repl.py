"""
Docker REPL environment that runs Python code in a Docker container.

Setup:
    docker build -t rlm-sandbox -f Dockerfile.sandbox .

Or use any Python 3.11+ image with: pip install dill requests
"""

import base64
import json
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import TracebackType
from typing import Any, cast

from rlm.core.comms_utils import LMRequest, send_lm_request, send_lm_request_batched
from rlm.core.types import REPLResult, RLMChatCompletion
from rlm.environments.base_env import NonIsolatedEnv
from rlm.environments.exec_script_templates import DOCKER_EXEC_SCRIPT_TEMPLATE, render_exec_script


@dataclass
class DockerREPLConfig:
    """Configuration for Docker container environment."""

    image: str = "python:3.11-slim"
    lm_handler_address: tuple[str, int] | None = None
    context_payload: dict[str, Any] | list[Any] | str | None = None
    setup_code: str | None = None
    persistent: bool = False
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "lm_handler_address": list(self.lm_handler_address)
            if self.lm_handler_address is not None
            else None,
            "context_payload": self.context_payload,
            "setup_code": self.setup_code,
            "persistent": self.persistent,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DockerREPLConfig":
        addr = data.get("lm_handler_address")
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "lm_handler_address"}
        if addr is not None:
            kwargs["lm_handler_address"] = (str(addr[0]), int(addr[1]))
        return cls(**kwargs)


class LLMProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler for LLM requests from the container."""

    lm_handler_address: tuple[str, int] | None = None
    pending_calls: list[RLMChatCompletion] = []
    lock: threading.Lock = threading.Lock()
    depth: int = 1

    def log_message(self, format: str, *args: Any) -> None:
        _ = format, args

    def do_POST(self) -> None:
        body_raw = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not isinstance(body_raw, dict):
            self._respond(400, {"error": "Invalid request payload"})
            return
        body = cast(dict[str, Any], body_raw)

        if self.path == "/llm_query":
            result = self._handle_single(body)
        elif self.path == "/llm_query_batched":
            result = self._handle_batched(body)
        else:
            self._respond(404, {"error": "Not found"})
            return

        self._respond(200, result)

    def _respond(self, status: int, data: dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_single(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.lm_handler_address:
            return {"error": "No LM handler configured"}

        prompt_raw = body.get("prompt")
        prompt: str | list[dict[str, Any]]
        if isinstance(prompt_raw, str):
            prompt = prompt_raw
        elif isinstance(prompt_raw, list):
            prompt = cast(list[dict[str, Any]], prompt_raw)
        else:
            return {"error": "Invalid prompt payload"}

        model_raw = body.get("model")
        model = model_raw if isinstance(model_raw, str) else None

        request = LMRequest(prompt=prompt, model=model, depth=self.depth)
        response = send_lm_request(self.lm_handler_address, request)

        if not response.success:
            return {"error": response.error}

        if response.chat_completion is None:
            return {"error": "No chat completion returned"}

        with self.lock:
            self.pending_calls.append(response.chat_completion)

        return {"response": response.chat_completion.response}

    def _handle_batched(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.lm_handler_address:
            return {"error": "No LM handler configured"}

        prompts_raw = body.get("prompts", [])
        if not isinstance(prompts_raw, list):
            return {"error": "Invalid prompts payload"}
        prompts = cast(list[str | list[dict[str, Any]]], prompts_raw)
        model_raw = body.get("model")
        model = model_raw if isinstance(model_raw, str) else None

        responses = send_lm_request_batched(
            self.lm_handler_address, prompts, model=model, depth=self.depth
        )

        results = [self._response_text(resp) for resp in responses]

        return {"responses": results}

    def _response_text(self, response: Any) -> str:
        if not response.success:
            return f"Error: {response.error}"
        if response.chat_completion is None:
            return "Error: No chat completion returned"
        with self.lock:
            self.pending_calls.append(response.chat_completion)
        return response.chat_completion.response


def _build_exec_script(code: str, proxy_port: int, depth: int = 1) -> str:
    """Build execution script for the container."""
    code_b64 = base64.b64encode(code.encode()).decode()
    return render_exec_script(
        DOCKER_EXEC_SCRIPT_TEMPLATE,
        {
            "__PROXY_PORT__": str(proxy_port),
            "__DEPTH__": str(depth),
            "__CODE_B64__": code_b64,
        },
    )


class DockerREPL(NonIsolatedEnv):
    """
    Docker REPL - runs Python in a Docker container with LLM support.

    Requires: Docker with a Python 3.11+ image (default: python:3.11-slim).
    """

    def __init__(
        self,
        config: DockerREPLConfig,
        **kwargs: Any,
    ) -> None:
        if config.persistent:
            raise NotImplementedError(
                "Persistent REPLs are currently not supported for environment: DockerREPL"
            )
        super().__init__(persistent=config.persistent, depth=config.depth, **kwargs)

        self.image = config.image
        self.lm_handler_address = config.lm_handler_address
        self.container_id: str | None = None
        self.proxy_server: HTTPServer | None = None
        self.proxy_thread: threading.Thread | None = None
        self.proxy_port: int = 0
        base_dir = os.environ.get(
            "RLM_DOCKER_WORKSPACE_DIR", os.path.join(os.getcwd(), ".rlm_workspace")
        )
        os.makedirs(base_dir, exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(prefix="docker_repl_", dir=base_dir)
        self.pending_calls: list[RLMChatCompletion] = []
        self._calls_lock = threading.Lock()

        self.setup()

        if config.context_payload:
            self.load_context(config.context_payload)
        if config.setup_code:
            self.execute_code(config.setup_code)

    def setup(self) -> None:
        """Start the proxy server and Docker container."""
        # Start LLM proxy server
        handler = type(
            "Handler",
            (LLMProxyHandler,),
            {
                "lm_handler_address": self.lm_handler_address,
                "pending_calls": self.pending_calls,
                "lock": self._calls_lock,
                "depth": self.depth,
            },
        )
        self.proxy_server = HTTPServer(("127.0.0.1", 0), handler)
        self.proxy_port = self.proxy_server.server_address[1]
        self.proxy_thread = threading.Thread(target=self.proxy_server.serve_forever, daemon=True)
        self.proxy_thread.start()

        # Start Docker container
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-v",
                f"{self.temp_dir}:/workspace",
                "--add-host",
                "host.docker.internal:host-gateway",
                self.image,
                "tail",
                "-f",
                "/dev/null",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")

        self.container_id = result.stdout.strip()

        # Install dependencies
        subprocess.run(
            ["docker", "exec", self.container_id, "pip", "install", "-q", "dill", "requests"],
            capture_output=True,
        )

    def load_context(self, context_payload: dict[str, Any] | list[Any] | str) -> None:
        """Load context by writing to a file in the mounted workspace."""
        if isinstance(context_payload, str):
            context_path = os.path.join(self.temp_dir, "context.txt")
            with open(context_path, "w") as f:
                f.write(context_payload)
            self.execute_code(
                "with open('/workspace/context.txt', 'r') as f:\n    context = f.read()"
            )
        else:
            context_path = os.path.join(self.temp_dir, "context.json")
            with open(context_path, "w") as f:
                json.dump(context_payload, f)
            self.execute_code(
                "import json\nwith open('/workspace/context.json', 'r') as f:\n    context = json.load(f)"
            )

    def _parse_execution_payload(self, stdout: str) -> tuple[str, str, dict[str, Any]] | None:
        lines = stdout.strip().split("\n")
        result_json = lines[-1] if lines else "{}"
        try:
            data_raw = json.loads(result_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(data_raw, dict):
            return None

        data = cast(dict[str, Any], data_raw)
        stdout_value = str(data.get("stdout", ""))
        stderr_value = str(data.get("stderr", ""))
        locals_value = data.get("locals", {})
        normalized_locals = (
            cast(dict[str, Any], locals_value) if isinstance(locals_value, dict) else {}
        )
        return stdout_value, stderr_value, normalized_locals

    def execute_code(self, code: str) -> REPLResult:
        start = time.perf_counter()

        if self.container_id is None:
            raise RuntimeError("Docker container is not initialized")

        container_id = self.container_id

        with self._calls_lock:
            self.pending_calls.clear()

        script = _build_exec_script(code, self.proxy_port, self.depth)
        result = subprocess.run(
            ["docker", "exec", container_id, "python", "-c", script],
            capture_output=True,
            text=True,
        )

        with self._calls_lock:
            calls = self.pending_calls.copy()
            self.pending_calls.clear()

        execution_time = time.perf_counter() - start
        parsed_payload = self._parse_execution_payload(result.stdout)
        if parsed_payload is None:
            return REPLResult(
                stdout=result.stdout,
                stderr=result.stderr or "Parse error",
                locals={},
                execution_time=execution_time,
                rlm_calls=calls,
            )

        stdout_value, stderr_value, normalized_locals = parsed_payload
        return REPLResult(
            stdout=stdout_value,
            stderr=stderr_value + result.stderr,
            locals=normalized_locals,
            execution_time=execution_time,
            rlm_calls=calls,
        )

    def cleanup(self) -> None:
        if hasattr(self, "container_id") and self.container_id:
            subprocess.run(["docker", "stop", self.container_id], capture_output=True)
            self.container_id = None
        if hasattr(self, "proxy_server") and self.proxy_server:
            self.proxy_server.shutdown()
            self.proxy_server = None
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __enter__(self) -> "DockerREPL":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        _ = exc_type, exc_val, exc_tb
        self.cleanup()
        return False

    def __del__(self):
        self.cleanup()
