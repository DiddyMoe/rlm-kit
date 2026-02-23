import copy
import io
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from types import TracebackType
from typing import Any, cast

from rlm.core.comms_utils import LMRequest, send_lm_request, send_lm_request_batched
from rlm.core.sandbox.safe_builtins import get_safe_builtins_for_repl
from rlm.core.types import REPLResult, RLMChatCompletion
from rlm.environments.base_env import RESERVED_TOOL_NAMES, NonIsolatedEnv

# =============================================================================
# Safe Builtins
# =============================================================================


def _build_local_repl_builtins() -> dict[str, Any]:
    """Build safe builtins for LocalREPL using centralized sandbox defaults.

    LocalREPL intentionally keeps `globals` and `locals` blocked to preserve
    existing behavior in this environment while still sharing the common base
    set with other REPL surfaces.
    """
    builtins = get_safe_builtins_for_repl()
    builtins["globals"] = None
    builtins["locals"] = None
    return builtins


class ExecutionTimeoutError(RuntimeError):
    """Raised when LocalREPL code execution exceeds the configured timeout."""


class LocalREPL(NonIsolatedEnv):
    """
    Local REPL environment with persistent Python namespace.
    Executes code in a sandboxed namespace with access to context data.
    """

    def __init__(
        self,
        lm_handler_address: tuple[str, int] | None = None,
        context_payload: dict[str, Any] | list[Any] | str | None = None,
        setup_code: str | None = None,
        execution_timeout_seconds: float = 60.0,
        persistent: bool = False,
        depth: int = 1,
        recursive_rlm_config: dict[str, Any] | None = None,
        custom_tools: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(persistent=persistent, depth=depth, **kwargs)

        self.lm_handler_address = lm_handler_address
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp(prefix=f"repl_env_{uuid.uuid4()}_")
        self._lock = threading.Lock()
        self._context_count: int = 0
        self._history_count: int = 0
        self.execution_timeout_seconds = execution_timeout_seconds
        self.recursive_rlm_config = copy.deepcopy(recursive_rlm_config)
        self.custom_tools = custom_tools

        # Setup globals, locals, and modules in environment.
        self.setup()

        # Load context if provided
        if context_payload is not None:
            self.load_context(context_payload)

        # Run setup code if provided
        if setup_code:
            self.execute_code(setup_code)

    def setup(self) -> None:
        """Setup the environment."""
        # Create sandboxed globals
        self.globals: dict[str, Any] = {
            "__builtins__": _build_local_repl_builtins(),
            "__name__": "__main__",
        }
        self.locals: dict[str, Any] = {}

        # Track LLM calls made during code execution
        self._pending_llm_calls: list[RLMChatCompletion] = []
        self._final_answer: str | None = None

        # Add helper functions
        self.globals["FINAL"] = self._final
        self.globals["FINAL_VAR"] = self._final_var
        self.globals["SHOW_VARS"] = self._show_vars
        self.globals["llm_query"] = self._llm_query
        self.globals["llm_query_batched"] = self._llm_query_batched

        # Inject custom tools (user-provided callables)
        if self.custom_tools:
            for name, fn in self.custom_tools.items():
                self.globals[name] = fn

        # Store scaffold backups so _restore_scaffold can recover after exec
        self._scaffold_backup: dict[str, Any] = {
            name: self.globals[name] for name in RESERVED_TOOL_NAMES if name in self.globals
        }
        # Also back up custom tool names
        if self.custom_tools:
            self._scaffold_backup.update(
                {name: self.globals[name] for name in self.custom_tools if name in self.globals}
            )

    def _final_var(self, variable_name: str) -> str:
        """Return the value of a variable as a final answer."""
        variable_name = variable_name.strip().strip("\"'")
        if variable_name in self.locals:
            return str(self.locals[variable_name])

        # Provide helpful error message with available variables
        available = [k for k in self.locals.keys() if not k.startswith("_")]
        if available:
            return (
                f"Error: Variable '{variable_name}' not found. "
                f"Available variables: {available}. "
                f"You must create and assign a variable BEFORE calling FINAL_VAR on it."
            )
        return (
            f"Error: Variable '{variable_name}' not found. "
            f"No variables have been created yet. "
            f"You must create and assign a variable in a REPL block BEFORE calling FINAL_VAR on it."
        )

    def _final(self, value: Any) -> str:
        """Set and return the final answer value."""
        self._final_answer = str(value)
        return self._final_answer

    def consume_final_answer(self) -> str | None:
        """Return and clear the final answer set via FINAL(...)."""
        final_answer = self._final_answer
        self._final_answer = None
        return final_answer

    def _show_vars(self) -> str:
        """Show all available variables in the REPL environment."""
        available = {k: type(v).__name__ for k, v in self.locals.items() if not k.startswith("_")}
        if not available:
            return (
                "No variables created yet. Use ```repl``` blocks to create variables. "
                "When you have your final answer, assign it to a variable and return it with "
                "FINAL_VAR('variable_name')."
            )
        return f"Available variables: {available}"

    def _llm_query(self, prompt: str, model: str | None = None) -> str:
        """Query the LM via socket connection to the handler.

        Args:
            prompt: The prompt to send to the LM.
            model: Optional model name to use (if handler has multiple clients).
        """
        recursive_completion = self._recursive_completion(prompt, model)
        if recursive_completion is not None:
            self._pending_llm_calls.append(recursive_completion)
            return recursive_completion.response

        if not self.lm_handler_address:
            return "Error: No LM handler configured"

        try:
            request = LMRequest(prompt=prompt, model=model, depth=self.depth)
            response = send_lm_request(self.lm_handler_address, request)

            if not response.success:
                return f"Error: {response.error}"

            if response.chat_completion is None:
                return "Error: No chat completion returned"

            # Track this LLM call
            self._pending_llm_calls.append(
                response.chat_completion,
            )

            return response.chat_completion.response
        except Exception as e:
            return f"Error: LM query failed - {e}"

    def _llm_query_batched(self, prompts: list[str], model: str | None = None) -> list[str]:
        """Query the LM with multiple prompts concurrently.

        Args:
            prompts: List of prompts to send to the LM.
            model: Optional model name to use (if handler has multiple clients).

        Returns:
            List of responses in the same order as input prompts.
        """
        if self._should_use_recursive_sub_rlm(model):
            return self._recursive_batched_completion(prompts, model)

        if not self.lm_handler_address:
            return ["Error: No LM handler configured"] * len(prompts)

        def response_text(response: Any) -> str:
            if not response.success:
                return f"Error: {response.error}"
            if response.chat_completion is None:
                return "Error: No chat completion returned"
            self._pending_llm_calls.append(response.chat_completion)
            return response.chat_completion.response

        try:
            prompt_payloads: list[str | list[dict[str, Any]]] = list(prompts)
            responses = send_lm_request_batched(
                self.lm_handler_address, prompt_payloads, model=model, depth=self.depth
            )
            return [response_text(response) for response in responses]
        except Exception as e:
            return [f"Error: LM query failed - {e}"] * len(prompts)

    def _recursive_batched_completion(self, prompts: list[str], model: str | None) -> list[str]:
        results: list[str] = []
        for prompt in prompts:
            recursive_completion = self._recursive_completion(prompt, model)
            if recursive_completion is None:
                results.append("Error: Recursive RLM call failed")
                continue
            self._pending_llm_calls.append(recursive_completion)
            results.append(recursive_completion.response)
        return results

    def _should_use_recursive_sub_rlm(self, model: str | None) -> bool:
        """Return True when sub-calls should recurse into a nested RLM."""
        if model is not None:
            return False
        if self.recursive_rlm_config is None:
            return False
        max_depth_value = self.recursive_rlm_config.get("max_depth")
        if not isinstance(max_depth_value, int):
            return False
        return self.depth < max_depth_value

    def _recursive_completion(self, prompt: str, model: str | None) -> RLMChatCompletion | None:
        """Run a recursive RLM sub-call when depth and config allow it."""
        if not self._should_use_recursive_sub_rlm(model):
            return None

        try:
            from rlm.core.rlm import RLM, RLMConfig

            config = self.recursive_rlm_config
            if config is None:
                return None

            nested_rlm = RLM(
                RLMConfig(
                    backend=config["backend"],
                    backend_kwargs=config.get("backend_kwargs"),
                    environment=config.get("environment", "local"),
                    environment_kwargs=config.get("environment_kwargs"),
                    depth=self.depth,
                    max_depth=config.get("max_depth", self.depth + 1),
                    max_iterations=config.get("max_iterations", 30),
                    other_backends=config.get("other_backends"),
                    other_backend_kwargs=config.get("other_backend_kwargs"),
                    max_root_tokens=config.get("max_root_tokens"),
                    max_sub_tokens=config.get("max_sub_tokens"),
                    verbose=False,
                    persistent=False,
                )
            )
            return nested_rlm.completion(prompt)
        except Exception:
            return None

    def load_context(self, context_payload: dict[str, Any] | list[Any] | str) -> None:
        """Load context into the environment as context_0 (and 'context' alias)."""
        self.add_context(context_payload, 0)
        # Update scaffold backup so restore gives back the loaded context
        if "context" in self.locals:
            self._scaffold_backup["context"] = self.locals["context"]

    def add_context(
        self, context_payload: dict[str, Any] | list[Any] | str, context_index: int | None = None
    ) -> int:
        """
        Add a context with versioned variable name.

        Args:
            context_payload: The context data to add
            context_index: Optional explicit index. If None, auto-increments.

        Returns:
            The context index used.
        """
        if context_index is None:
            context_index = self._context_count

        var_name = f"context_{context_index}"

        if isinstance(context_payload, str):
            context_path = os.path.join(self.temp_dir, f"context_{context_index}.txt")
            with open(context_path, "w") as f:
                f.write(context_payload)
            self.execute_code(f"with open(r'{context_path}', 'r') as f:\n    {var_name} = f.read()")
        else:
            context_path = os.path.join(self.temp_dir, f"context_{context_index}.json")
            with open(context_path, "w") as f:
                json.dump(context_payload, f)
            self.execute_code(
                f"import json\nwith open(r'{context_path}', 'r') as f:\n    {var_name} = json.load(f)"
            )

        # Alias context_0 as 'context' for backward compatibility
        if context_index == 0:
            self.execute_code(f"context = {var_name}")

        self._context_count = max(self._context_count, context_index + 1)
        return context_index

    def update_handler_address(self, address: tuple[str, int]) -> None:
        """Update the LM handler address for a new completion call."""
        self.lm_handler_address = address

    def get_context_count(self) -> int:
        """Return the number of contexts loaded."""
        return self._context_count

    def add_history(
        self, message_history: list[dict[str, Any]], history_index: int | None = None
    ) -> int:
        """
        Store a conversation's message history as a versioned variable.

        Args:
            message_history: The list of message dicts from a completion call
            history_index: Optional explicit index. If None, auto-increments.

        Returns:
            The history index used.
        """
        if history_index is None:
            history_index = self._history_count

        var_name = f"history_{history_index}"

        # Store deep copy to avoid reference issues with nested dicts
        self.locals[var_name] = copy.deepcopy(message_history)

        # Alias history_0 as 'history' for convenience
        if history_index == 0:
            self.locals["history"] = self.locals[var_name]
            # Keep scaffold backup in sync
            self._scaffold_backup["history"] = self.locals[var_name]

        self._history_count = max(self._history_count, history_index + 1)
        return history_index

    def get_history_count(self) -> int:
        """Return the number of conversation histories stored."""
        return self._history_count

    def append_compaction_entry(self, entry: list[dict[str, Any]] | dict[str, Any]) -> None:
        """Append messages or a summary entry to the REPL ``history`` variable.

        During compaction the main loop calls this so the REPL code can inspect
        ``history`` for the full trajectory.  The entry is either a list of
        message dicts (an iteration's formatted messages) or a single dict
        (a compaction summary marker).
        """
        if "history" not in self.locals:
            self.locals["history"] = []

        history = self.locals.get("history")
        if not isinstance(history, list):
            history = []
            self.locals["history"] = history

        history_entries = cast(list[dict[str, Any]], history)

        if isinstance(entry, list):
            history_entries.extend(entry)
        else:
            history_entries.append(entry)

        # Keep scaffold backup in sync
        self._scaffold_backup["history"] = self.locals["history"]

    @contextmanager
    def _capture_output(self):
        """Thread-safe context manager to capture stdout/stderr."""
        with self._lock:
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
            try:
                sys.stdout, sys.stderr = stdout_buf, stderr_buf
                yield stdout_buf, stderr_buf
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr

    @contextmanager
    def _temp_cwd(self):
        """Temporarily change to temp directory for execution."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            yield
        finally:
            os.chdir(old_cwd)

    @contextmanager
    def _execution_timeout(self):
        """Apply a per-execution timeout for code execution.

        Timeout enforcement is enabled when running on Unix with `SIGALRM` and
        on the main thread. In other contexts, execution proceeds without signal
        timeout enforcement.
        """
        if self.execution_timeout_seconds <= 0:
            yield
            return

        if threading.current_thread() is not threading.main_thread():
            yield
            return

        if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
            yield
            return

        def _handle_timeout(_signum: int, _frame: Any) -> None:
            raise ExecutionTimeoutError(
                f"Code execution exceeded timeout of {self.execution_timeout_seconds:.1f}s"
            )

        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.execution_timeout_seconds)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous_handler)

    def _restore_scaffold(self) -> None:
        """Restore reserved scaffold names that REPL code may have overwritten."""
        for name, value in self._scaffold_backup.items():
            if name in ("context", "history"):
                # context/history live in locals
                self.locals[name] = value
            else:
                self.globals[name] = value

    def _update_locals_from_combined(self, combined: dict[str, object]) -> None:
        """Update locals with user-defined names from combined execution namespace."""
        for key, value in combined.items():
            if key not in self.globals and not key.startswith("_"):
                self.locals[key] = value

    def execute_code(self, code: str) -> REPLResult:
        """Execute code in the persistent namespace and return result."""
        start_time = time.perf_counter()

        # Clear pending LLM calls from previous execution
        self._pending_llm_calls = []

        with (
            self._capture_output() as (stdout_buf, stderr_buf),
            self._temp_cwd(),
            self._execution_timeout(),
        ):
            try:
                combined = {**self.globals, **self.locals}
                exec(code, combined, combined)
                self._update_locals_from_combined(combined)

                stdout = stdout_buf.getvalue()
                stderr = stderr_buf.getvalue()
            except Exception as e:
                stdout = stdout_buf.getvalue()
                stderr = stderr_buf.getvalue() + f"\n{type(e).__name__}: {e}"

        # Restore scaffold names that user code may have overwritten
        self._restore_scaffold()

        return REPLResult(
            stdout=stdout,
            stderr=stderr,
            locals=self.locals.copy(),
            execution_time=time.perf_counter() - start_time,
            rlm_calls=self._pending_llm_calls.copy(),
        )

    def __enter__(self) -> "LocalREPL":
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

    def cleanup(self) -> None:
        """Clean up temp directory and reset state."""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
        self.globals.clear()
        self.locals.clear()

    def __del__(self):
        self.cleanup()
