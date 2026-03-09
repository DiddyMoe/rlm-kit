"""
Daytona REPL environment that runs Python code in Daytona sandboxes.

Uses the Daytona API (https://daytona.io/docs) for sandbox management.
"""

import base64
import importlib
import json
import os
import textwrap
import threading
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import requests

try:
    daytona_module = importlib.import_module("daytona")
    CreateSandboxFromImageParams = daytona_module.CreateSandboxFromImageParams
    Daytona = daytona_module.Daytona
    DaytonaConfig = daytona_module.DaytonaConfig
    Image = daytona_module.Image
    Resources = daytona_module.Resources
    SessionExecuteRequest = daytona_module.SessionExecuteRequest
except ImportError:
    CreateSandboxFromImageParams = cast(Any, object)
    Daytona = cast(Any, object)
    DaytonaConfig = cast(Any, object)
    Image = cast(Any, object)
    Resources = cast(Any, object)
    SessionExecuteRequest = cast(Any, object)

from rlm.core.comms_utils import LMRequest, send_lm_request, send_lm_request_batched
from rlm.core.types import REPLResult, RLMChatCompletion
from rlm.environments.base_env import IsolatedEnv


@dataclass
class DaytonaREPLConfig:
    """Configuration for Daytona sandbox environment."""

    api_key: str | None = None
    target: str = "us"
    name: str = "rlm-sandbox"
    timeout: int = 600
    cpu: int = 1
    memory: int = 2
    disk: int = 5
    auto_stop_interval: int = 0
    image: Any | None = None
    lm_handler_address: tuple[str, int] | None = None
    context_payload: dict[str, Any] | list[Any] | str | None = None
    setup_code: str | None = None
    persistent: bool = False
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "target": self.target,
            "name": self.name,
            "timeout": self.timeout,
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "auto_stop_interval": self.auto_stop_interval,
            "image": repr(self.image) if self.image is not None else None,
            "lm_handler_address": list(self.lm_handler_address)
            if self.lm_handler_address is not None
            else None,
            "context_payload": self.context_payload,
            "setup_code": self.setup_code,
            "persistent": self.persistent,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DaytonaREPLConfig":
        addr = data.get("lm_handler_address")
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "lm_handler_address"}
        if addr is not None:
            kwargs["lm_handler_address"] = (str(addr[0]), int(addr[1]))
        return cls(**kwargs)


# =============================================================================
# Default Daytona Image
# =============================================================================


def get_default_image() -> Any:
    """
    Build a default Daytona image with common libraries for data science,
    math, and general Python work.
    """
    return (
        Image.debian_slim("3.11")
        .run_commands(
            "apt-get update && apt-get install -y build-essential \
                 git \
                 curl \
                 wget \
                 libopenblas-dev \
                 liblapack-dev",
        )
        .pip_install(
            # Data science essentials
            "numpy>=1.26.0",
            "pandas>=2.1.0",
            "scipy>=1.11.0",
            # Math & symbolic computation
            "sympy>=1.12",
            # HTTP & APIs
            "requests>=2.31.0",
            "httpx>=0.25.0",
            "flask>=3.0.0",
            # Data formats
            "pyyaml>=6.0",
            "toml>=0.10.2",
            # Utilities
            "tqdm>=4.66.0",
            "python-dateutil>=2.8.2",
            "regex>=2023.0.0",
            # For state serialization
            "dill>=0.3.7",
        )
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
    """Called by DaytonaREPL to get pending requests."""
    with lock:
        pending = [
            {"id": rid, "request": entry["request"]}
            for rid, entry in pending_requests.items()
            if entry["response"] is None
        ]
    return jsonify({"pending": pending})

@app.route("/respond", methods=["POST"])
def respond():
    """Called by DaytonaREPL to submit a response."""
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

    return textwrap.dedent(
        f'''
import sys
import io
import json
import base64
import traceback
import os
import requests

try:
    import dill
except ImportError:
    import pickle as dill

# =============================================================================
# LLM Query Functions (via local broker)
# =============================================================================

BROKER_URL = "http://127.0.0.1:{broker_port}"

def llm_query(prompt, model=None):
    """Query the LM via the broker."""
    try:
        response = requests.post(
            f"{{BROKER_URL}}/enqueue",
            json={{"type": "single", "prompt": prompt, "model": model, "depth": {depth}}},
            timeout=300,
        )
        data = response.json()
        if data.get("error"):
            return f"Error: {{data['error']}}"
        return data.get("response", "Error: No response")
    except Exception as e:
        return f"Error: LM query failed - {{e}}"


def llm_query_batched(prompts, model=None):
    """Query the LM with multiple prompts."""
    try:
        response = requests.post(
            f"{{BROKER_URL}}/enqueue",
            json={{"type": "batched", "prompts": prompts, "model": model, "depth": {depth}}},
            timeout=300,
        )
        data = response.json()
        if data.get("error"):
            return [f"Error: {{data['error']}}"] * len(prompts)
        return data.get("responses", ["Error: No response"] * len(prompts))
    except Exception as e:
        return [f"Error: LM query failed - {{e}}"] * len(prompts)


# =============================================================================
# State Management
# =============================================================================

STATE_FILE = "/tmp/rlm_state.dill"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "rb") as f:
                return dill.load(f)
        except Exception:
            pass
    return {{}}

def save_state(state):
    clean_state = {{}}
    for k, v in state.items():
        if k.startswith("_"):
            continue
        try:
            dill.dumps(v)
            clean_state[k] = v
        except Exception:
            pass
    with open(STATE_FILE, "wb") as f:
        dill.dump(clean_state, f)

def serialize_locals(state):
    result = {{}}
    for k, v in state.items():
        if k.startswith("_"):
            continue
        try:
            result[k] = repr(v)
        except Exception:
            result[k] = f"<{{type(v).__name__}}>"
    return result

# =============================================================================
# Execution
# =============================================================================

_locals = load_state()

def FINAL_VAR(variable_name):
    variable_name = variable_name.strip().strip("\\"\\'")
    if variable_name in _locals:
        return str(_locals[variable_name])
    available = [k for k in _locals.keys() if not k.startswith("_")]
    if available:
        return f"Error: Variable '{{variable_name}}' not found. Available variables: {{available}}. You must create and assign a variable BEFORE calling FINAL_VAR on it."
    return f"Error: Variable '{{variable_name}}' not found. No variables have been created yet. You must create and assign a variable in a REPL block BEFORE calling FINAL_VAR on it."

def SHOW_VARS():
    available = {{k: type(v).__name__ for k, v in _locals.items() if not k.startswith("_")}}
    if not available:
        return "No variables created yet. Use ```repl``` blocks to create variables. When you have your final answer, assign it to a variable and return it with FINAL_VAR('variable_name')."
    return f"Available variables: {{available}}"

_globals = {{
    "__builtins__": __builtins__,
    "__name__": "__main__",
    "llm_query": llm_query,
    "llm_query_batched": llm_query_batched,
    "FINAL_VAR": FINAL_VAR,
    "SHOW_VARS": SHOW_VARS,
}}

code = base64.b64decode("{code_b64}").decode()

stdout_buf = io.StringIO()
stderr_buf = io.StringIO()
old_stdout, old_stderr = sys.stdout, sys.stderr

try:
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf
    combined = {{**_globals, **_locals}}
    exec(code, combined, combined)
    for key, value in combined.items():
        if key not in _globals and not key.startswith("_"):
            _locals[key] = value
except Exception as e:
    traceback.print_exc(file=stderr_buf)
finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr

save_state(_locals)

result = {{
    "stdout": stdout_buf.getvalue(),
    "stderr": stderr_buf.getvalue(),
    "locals": serialize_locals(_locals),
}}
print(json.dumps(result))
'''
    )


class DaytonaREPL(IsolatedEnv):
    """
    Daytona REPL environment that runs Python code in a Daytona Sandbox.

    Uses Daytona preview URLs for LLM communication:
    - Sandbox runs a broker server exposed via preview URL (port 8080)
    - DaytonaREPL polls the broker for pending LLM requests
    - DaytonaREPL forwards requests to the LM handler and posts responses back
    """

    BROKER_PORT = 8080

    def __init__(
        self,
        config: DaytonaREPLConfig,
        **kwargs: Any,
    ) -> None:
        """
        Initialize a Daytona REPL environment.

        Args:
            config: Daytona sandbox configuration (provider-specific and common env fields).
            **kwargs: Additional arguments passed to base class.
        """
        if config.persistent:
            raise NotImplementedError(
                "Persistent REPLs are currently not supported for environment: DaytonaREPL"
            )
        super().__init__(persistent=config.persistent, depth=config.depth, **kwargs)

        self.api_key = config.api_key or os.getenv("DAYTONA_API_KEY")
        self.target = config.target
        self.name = config.name
        self.timeout = config.timeout
        self.cpu = config.cpu
        self.memory = config.memory
        self.disk = config.disk
        self.auto_stop_interval = config.auto_stop_interval
        self.image = config.image or get_default_image()
        self.lm_handler_address = config.lm_handler_address

        self.daytona = None
        self.sandbox = None
        self.broker_session_id: str = "rlm-broker-session"
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

    @property
    def calls_lock(self) -> threading.Lock:
        return self._calls_lock

    @calls_lock.setter
    def calls_lock(self, value: threading.Lock) -> None:
        self._calls_lock = value

    def setup(self) -> None:
        """Create the Daytona sandbox, broker, and start polling."""
        # Initialize Daytona client
        config_kwargs = {"target": self.target}
        if self.api_key:
            config_kwargs["api_key"] = self.api_key

        config = DaytonaConfig(**config_kwargs)
        self.daytona = Daytona(config)

        # Create sandbox with specified resources
        resources = Resources(
            cpu=self.cpu,
            memory=self.memory,
            disk=self.disk,
        )

        params = CreateSandboxFromImageParams(
            name=self.name,
            image=self.image,
            resources=resources,
            auto_stop_interval=self.auto_stop_interval,
        )

        self.sandbox = self.daytona.create(params)

        # Upload the broker script
        self.sandbox.fs.upload_file(
            _BROKER_SCRIPT.encode("utf-8"),
            "broker_server.py",
        )

        # Create a session for the broker server
        self.sandbox.process.create_session(self.broker_session_id)

        # Start the broker server in the session (async execution)
        self.sandbox.process.execute_session_command(
            self.broker_session_id,
            SessionExecuteRequest(
                command="python broker_server.py",
                var_async=True,
            ),
        )

        # Wait for broker to be ready
        time.sleep(3)

        # Get the preview URL for the broker port
        try:
            preview_info = self.sandbox.get_preview_link(self.BROKER_PORT)
            self.broker_url = preview_info.url
            self._preview_token = preview_info.token
        except Exception:
            self.broker_url = None
            self._preview_token = None

        # Start polling thread if we have an LM handler
        if self.lm_handler_address and self.broker_url:
            self.poller_stop.clear()
            self.poller_thread = threading.Thread(target=self._poll_broker, daemon=True)
            self.poller_thread.start()

    def _get_headers(self) -> dict[str, str]:
        """Get headers for broker requests including auth token."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if hasattr(self, "_preview_token") and self._preview_token:
            headers["x-daytona-preview-token"] = str(self._preview_token)
        return headers

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
        resp = requests.get(
            f"{self.broker_url}/pending",
            headers=self._get_headers(),
            timeout=5,
        )
        pending_raw = resp.json().get("pending", [])
        if not isinstance(pending_raw, list):
            return []
        pending_list = cast(list[Any], pending_raw)
        return [cast(dict[str, Any], item) for item in pending_list if isinstance(item, dict)]

    def _forward_pending_requests(self, pending: list[dict[str, Any]]) -> None:
        if self.broker_url is None:
            return
        for item in pending:
            request_id = str(item.get("id", ""))
            req_data = item.get("request")
            if not isinstance(req_data, dict):
                continue
            response = self._handle_llm_request(cast(dict[str, Any], req_data))
            requests.post(
                f"{self.broker_url}/respond",
                headers=self._get_headers(),
                json={"id": request_id, "response": response},
                timeout=10,
            )

    def _handle_llm_request(self, req_data: dict[str, Any]) -> dict[str, Any]:
        """Handle an LLM request from the sandbox."""
        if self.lm_handler_address is None:
            return {"error": "LM handler is not configured"}

        req_type = req_data.get("type")
        model_raw = req_data.get("model")
        model = model_raw if isinstance(model_raw, str) else None

        if req_type == "single":
            return self._handle_single_llm_request(req_data=req_data, model=model)

        if req_type == "batched":
            return self._handle_batched_llm_request(req_data=req_data, model=model)

        return {"error": "Unknown request type"}

    def _handle_single_llm_request(
        self, req_data: dict[str, Any], model: str | None
    ) -> dict[str, Any]:
        if self.lm_handler_address is None:
            return {"error": "LM handler is not configured"}
        prompt_raw = req_data.get("prompt")
        if isinstance(prompt_raw, str):
            prompt: str | list[dict[str, Any]] = prompt_raw
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
        self, req_data: dict[str, Any], model: str | None
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

        return {"responses": results}

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
        """Execute code in the Daytona sandbox and return result."""
        start_time = time.perf_counter()

        if self.sandbox is None:
            raise RuntimeError("Daytona sandbox is not initialized")

        # Clear pending LLM calls
        with self._calls_lock:
            self.pending_llm_calls.clear()

        # Build and execute the script
        script = _build_exec_script(code, self.BROKER_PORT, self.depth)

        # Upload the script as a temporary file
        script_path = "/tmp/rlm_exec_script.py"
        self.sandbox.fs.upload_file(
            script.encode("utf-8"),
            script_path,
        )

        # Execute the script
        response = self.sandbox.process.exec(f"python {script_path}", timeout=self.timeout)

        # Read output
        stdout = response.result if response.exit_code == 0 else ""
        stderr = response.result if response.exit_code != 0 else ""

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

        # Delete the broker session
        if self.sandbox is not None:
            try:
                self.sandbox.process.delete_session(self.broker_session_id)
            except Exception:
                pass

            # Delete the sandbox
            try:
                self.sandbox.delete()
            except Exception:
                pass
            self.sandbox = None

    def __enter__(self) -> "DaytonaREPL":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.cleanup()
        return False

    def __del__(self):
        self.cleanup()
