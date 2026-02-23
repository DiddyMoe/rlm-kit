import base64
import importlib
import json
import textwrap
import threading
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import requests

try:
    modal = importlib.import_module("modal")
except ImportError:
    modal = cast(Any, object)

from rlm.core.comms_utils import LMRequest, send_lm_request, send_lm_request_batched
from rlm.core.types import REPLResult, RLMChatCompletion
from rlm.environments.base_env import IsolatedEnv
from rlm.environments.constants import APT_PACKAGES, PIP_PACKAGES
from rlm.environments.exec_script_templates import MODAL_EXEC_SCRIPT_TEMPLATE, render_exec_script


@dataclass
class ModalREPLConfig:
    """Configuration for Modal sandbox environment."""

    app_name: str = "rlm-sandbox"
    image: Any | None = None
    timeout: int = 600
    lm_handler_address: tuple[str, int] | None = None
    context_payload: dict[str, Any] | list[Any] | str | None = None
    setup_code: str | None = None
    persistent: bool = False
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "image": repr(self.image) if self.image is not None else None,
            "timeout": self.timeout,
            "lm_handler_address": list(self.lm_handler_address)
            if self.lm_handler_address is not None
            else None,
            "context_payload": self.context_payload,
            "setup_code": self.setup_code,
            "persistent": self.persistent,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModalREPLConfig":
        addr = data.get("lm_handler_address")
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "lm_handler_address"}
        if addr is not None:
            kwargs["lm_handler_address"] = (str(addr[0]), int(addr[1]))
        return cls(**kwargs)


# =============================================================================
# Default Modal Image
# =============================================================================


def get_default_image() -> Any:
    """
    Build a default Modal image with common libraries for data science,
    math, and general Python work.
    """
    return (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install(*APT_PACKAGES)
        .pip_install(*PIP_PACKAGES)
    )


# =============================================================================
# Broker Server Script (runs inside sandbox, handles LLM request queue)
# =============================================================================

_BROKER_SCRIPT = textwrap.dedent(
    '''
import json
import threading
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

# Request queue: {request_id: {"request": {...}, "response": None, "event": Event}}
pending_requests = {}
lock = threading.Lock()

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/enqueue", methods=["POST"])
def enqueue():
    """Called by sandbox code to submit an LLM request and wait for response."""
    data = request.json
    request_id = str(uuid.uuid4())
    event = threading.Event()

    with lock:
        pending_requests[request_id] = {
            "request": data,
            "response": None,
            "event": event,
        }

    # Wait for response (with timeout)
    event.wait(timeout=300)

    with lock:
        entry = pending_requests.pop(request_id, None)

    if entry and entry["response"] is not None:
        return jsonify(entry["response"])
    else:
        return jsonify({"error": "Request timed out"}), 504

@app.route("/pending")
def get_pending():
    """Called by ModalREPL to get pending requests."""
    with lock:
        pending = [
            {"id": rid, "request": entry["request"]}
            for rid, entry in pending_requests.items()
            if entry["response"] is None
        ]
    return jsonify({"pending": pending})

@app.route("/respond", methods=["POST"])
def respond():
    """Called by ModalREPL to submit a response."""
    data = request.json
    request_id = data.get("id")
    response = data.get("response")

    with lock:
        if request_id in pending_requests:
            pending_requests[request_id]["response"] = response
            pending_requests[request_id]["event"].set()
            return jsonify({"status": "ok"})

    return jsonify({"error": "Request not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
'''
)


# =============================================================================
# Execution Script (runs inside the sandbox for each code block)
# =============================================================================


def _build_exec_script(code: str, broker_port: int = 8080, depth: int = 1) -> str:
    """
    Build a script that executes code with state persistence.
    LLM queries go through the local broker server.
    """
    code_b64 = base64.b64encode(code.encode()).decode()

    return render_exec_script(
        MODAL_EXEC_SCRIPT_TEMPLATE,
        {
            "__BROKER_PORT__": str(broker_port),
            "__DEPTH__": str(depth),
            "__CODE_B64__": code_b64,
        },
    )


class ModalREPL(IsolatedEnv):
    """
    Modal REPL environment that runs Python code in a Modal Sandbox.

    Uses Modal tunnels for LLM communication:
    - Sandbox runs a broker server exposed via encrypted_ports
    - ModalREPL polls the broker for pending LLM requests
    - ModalREPL forwards requests to the LM handler and posts responses back
    """

    BROKER_PORT = 8080

    def __init__(
        self,
        config: ModalREPLConfig,
        **kwargs: Any,
    ) -> None:
        if config.persistent:
            raise NotImplementedError(
                "Persistent REPLs are currently not supported for environment: ModalREPL"
            )
        super().__init__(persistent=config.persistent, depth=config.depth, **kwargs)

        self.app_name = config.app_name
        self.timeout = config.timeout
        self.lm_handler_address = config.lm_handler_address

        self.image = config.image or get_default_image()

        self.app = None
        self.sandbox = None
        self.broker_process = None
        self.broker_url: str | None = None
        self.poller_thread: threading.Thread | None = None
        self.poller_stop = threading.Event()
        self.pending_llm_calls: list[RLMChatCompletion] = []
        self._calls_lock = threading.Lock()

        self.setup()

        if config.context_payload is not None:
            self.load_context(config.context_payload)

        if config.setup_code:
            self.execute_code(config.setup_code)

    def setup(self) -> None:
        """Create the Modal app, sandbox, broker, and start polling."""
        self.app = modal.App.lookup(self.app_name, create_if_missing=True)

        # Create sandbox with encrypted port for broker
        self.sandbox = modal.Sandbox.create(
            app=self.app,
            image=self.image,
            timeout=self.timeout,
            encrypted_ports=[self.BROKER_PORT],
        )

        # Start the broker server in the sandbox
        self.broker_process = self.sandbox.exec(
            "python",
            "-c",
            _BROKER_SCRIPT,
        )

        # Wait for broker to be ready
        time.sleep(2)

        # Get the tunnel URL
        tunnels = self.sandbox.tunnels()
        if self.BROKER_PORT in tunnels:
            self.broker_url = tunnels[self.BROKER_PORT].url

        # Start polling thread if we have an LM handler
        if self.lm_handler_address and self.broker_url:
            self.poller_stop.clear()
            self.poller_thread = threading.Thread(target=self._poll_broker, daemon=True)
            self.poller_thread.start()

    def _poll_broker(self) -> None:
        """Poll the broker for pending LLM requests and handle them."""
        while not self.poller_stop.is_set():
            if self.broker_url is None:
                time.sleep(0.1)
                continue
            try:
                pending = self._fetch_pending_requests()
                self._forward_pending_requests(pending)

            except requests.exceptions.RequestException:
                pass
            except Exception:
                pass

            time.sleep(0.1)

    def _fetch_pending_requests(self) -> list[dict[str, Any]]:
        if self.broker_url is None:
            return []
        resp = requests.get(f"{self.broker_url}/pending", timeout=5)
        pending_raw = resp.json().get("pending", [])
        if not isinstance(pending_raw, list):
            return []
        pending_list = cast(list[Any], pending_raw)
        return [cast(dict[str, Any], item) for item in pending_list if isinstance(item, dict)]

    def _forward_pending_requests(self, pending: list[dict[str, Any]]) -> None:
        for item in pending:
            request_id = str(item.get("id", ""))
            req_data = item["request"]
            if not isinstance(req_data, dict):
                continue
            response = self._handle_llm_request(cast(dict[str, Any], req_data))
            if self.broker_url is None:
                continue
            requests.post(
                f"{self.broker_url}/respond",
                json={"id": request_id, "response": response},
                timeout=10,
            )

    def _handle_single_llm_request(
        self,
        req_data: dict[str, Any],
        model: str | None,
    ) -> dict[str, Any]:
        if self.lm_handler_address is None:
            return {"error": "LM handler is not configured"}

        prompt_raw = req_data.get("prompt")
        prompt: str | list[dict[str, Any]]
        if isinstance(prompt_raw, str):
            prompt = prompt_raw
        elif isinstance(prompt_raw, list):
            prompt = cast(list[dict[str, Any]], prompt_raw)
        else:
            return {"error": "Invalid single prompt payload"}

        request = LMRequest(prompt=prompt, model=model, depth=self.depth)
        response = send_lm_request(self.lm_handler_address, request)
        if not response.success:
            return {"error": response.error}
        if response.chat_completion is None:
            return {"error": "No chat completion returned"}

        with self._calls_lock:
            self.pending_llm_calls.append(response.chat_completion)
        return {"response": response.chat_completion.response}

    def _handle_batched_llm_request(
        self,
        req_data: dict[str, Any],
        model: str | None,
    ) -> dict[str, Any]:
        if self.lm_handler_address is None:
            return {"error": "LM handler is not configured"}

        prompts_raw = req_data.get("prompts", [])
        if not isinstance(prompts_raw, list):
            return {"error": "Invalid batched prompts payload"}
        prompts = cast(list[str | list[dict[str, Any]]], prompts_raw)
        responses = send_lm_request_batched(
            self.lm_handler_address, prompts, model=model, depth=self.depth
        )
        return {"responses": self._handle_batched(responses)}

    def _handle_llm_request(self, req_data: dict[str, Any]) -> dict[str, Any]:
        """Handle an LLM request from the sandbox."""
        req_type = req_data.get("type")
        model_raw = req_data.get("model")
        model = model_raw if isinstance(model_raw, str) else None

        if req_type == "single":
            return self._handle_single_llm_request(req_data, model)

        if req_type == "batched":
            return self._handle_batched_llm_request(req_data, model)

        return {"error": "Unknown request type"}

    def _handle_batched(self, responses: list[Any]) -> list[str]:
        results: list[str] = []
        for response in responses:
            if not response.success:
                results.append(f"Error: {response.error}")
                continue

            if response.chat_completion is None:
                results.append("Error: No chat completion returned")
                continue

            with self._calls_lock:
                self.pending_llm_calls.append(response.chat_completion)
            results.append(response.chat_completion.response)

        return results

    def load_context(self, context_payload: dict[str, Any] | list[Any] | str) -> None:
        """Load context into the sandbox environment."""
        if isinstance(context_payload, str):
            escaped = context_payload.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            context_code = f'context = """{escaped}"""'
        else:
            context_json = json.dumps(context_payload)
            escaped_json = context_json.replace("\\", "\\\\").replace("'", "\\'")
            context_code = f"import json; context = json.loads('{escaped_json}')"

        self.execute_code(context_code)

    def _parse_execution_payload(self, stdout: str) -> tuple[str, str, dict[str, Any]] | None:
        lines = stdout.strip().split("\n")
        result_json = lines[-1] if lines else "{}"
        try:
            result_raw = json.loads(result_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(result_raw, dict):
            return None

        result = cast(dict[str, Any], result_raw)
        stdout_value = str(result.get("stdout", ""))
        stderr_value = str(result.get("stderr", ""))
        locals_value = result.get("locals", {})
        normalized_locals = (
            cast(dict[str, Any], locals_value) if isinstance(locals_value, dict) else {}
        )
        return stdout_value, stderr_value, normalized_locals

    def execute_code(self, code: str) -> REPLResult:
        """Execute code in the Modal sandbox and return result."""
        start_time = time.perf_counter()

        if self.sandbox is None:
            raise RuntimeError("Modal sandbox is not initialized")

        # Clear pending LLM calls
        with self._calls_lock:
            self.pending_llm_calls.clear()

        # Build and execute the script
        script = _build_exec_script(code, self.BROKER_PORT, self.depth)
        process = self.sandbox.exec("python", "-c", script)

        # Read output
        stdout = process.stdout.read()
        stderr = process.stderr.read()

        # Collect LLM calls made during this execution
        with self._calls_lock:
            pending_calls = self.pending_llm_calls.copy()
            self.pending_llm_calls.clear()

        execution_time = time.perf_counter() - start_time

        parsed_payload = self._parse_execution_payload(stdout)
        if parsed_payload is None:
            return REPLResult(
                stdout=stdout,
                stderr=stderr or "Failed to parse execution result",
                locals={},
                execution_time=execution_time,
                rlm_calls=pending_calls,
            )

        stdout_value, stderr_value, normalized_locals = parsed_payload
        return REPLResult(
            stdout=stdout_value,
            stderr=stderr_value + stderr,
            locals=normalized_locals,
            execution_time=execution_time,
            rlm_calls=pending_calls,
        )

    def cleanup(self) -> None:
        """Terminate the sandbox and stop polling."""
        # Stop the poller thread
        if self.poller_thread is not None:
            self.poller_stop.set()
            self.poller_thread.join(timeout=2)
            self.poller_thread = None

        if self.sandbox is not None:
            try:
                self.sandbox.terminate()
            except Exception:
                pass
            self.sandbox = None

    def __enter__(self) -> "ModalREPL":
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
