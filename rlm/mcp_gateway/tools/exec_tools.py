"""Sandboxed execution tools for RLM MCP Gateway."""

import hashlib
import io
import queue
import resource
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from rlm.core.sandbox import (
    ASTValidationError,
    create_restricted_environment,
    restore_sys_modules,
    setup_runtime_blocking,
    validate_ast,
)
from rlm.core.types import SnippetProvenance
from rlm.mcp_gateway.constants import MAX_EXEC_CODE_SIZE, MAX_EXEC_MEMORY_MB, MAX_EXEC_TIMEOUT_MS
from rlm.mcp_gateway.session import SessionManager


class ExecTools:
    """Sandboxed execution tools."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize exec tools.

        Args:
            session_manager: Session manager instance
        """
        self.session_manager = session_manager

    def _resolve_session(self, session_id: str) -> tuple[Any | None, str | None]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None, "Session not found"

        within_budget, budget_error = self.session_manager.check_budget(session)
        if not within_budget:
            return None, budget_error

        return session, None

    def _validate_exec_request(self, code: str, timeout_ms: int) -> str | None:
        code_bytes = len(code.encode("utf-8"))
        if code_bytes > MAX_EXEC_CODE_SIZE:
            return f"Code too large: {code_bytes} > {MAX_EXEC_CODE_SIZE} bytes"

        if timeout_ms > 30000:
            return f"Timeout too large: {timeout_ms}ms > 30000ms"

        try:
            validate_ast(code)
        except ASTValidationError as error:
            return error.message
        except Exception as error:
            return f"Code validation error: {error}"

        return None

    def _apply_memory_limit(self, memory_limit_mb: int) -> None:
        if not hasattr(resource, "RLIMIT_AS") or memory_limit_mb <= 0:
            return

        try:
            memory_bytes = memory_limit_mb * 1024 * 1024
            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, hard))
        except (OSError, ValueError):
            return

    def _run_code(
        self,
        code: str,
        timeout_ms: int,
        memory_limit_mb: int,
        restricted_globals: dict[str, Any],
        restricted_locals: dict[str, Any],
    ) -> tuple[bool, str | None, Exception | None]:
        result_queue: queue.Queue[bool] = queue.Queue()
        exception_queue: queue.Queue[Exception] = queue.Queue()

        self._apply_memory_limit(memory_limit_mb)

        def execute_in_thread() -> None:
            try:
                exec(code, restricted_globals, restricted_locals)
                result_queue.put(True)
            except MemoryError:
                exception_queue.put(
                    MemoryError(f"Memory limit exceeded: {memory_limit_mb}MB (R3 compliance)")
                )
            except Exception as error:
                exception_queue.put(error)

        thread = threading.Thread(target=execute_in_thread, daemon=True)
        thread.start()
        thread.join(timeout=timeout_ms / 1000.0)

        if thread.is_alive():
            print(
                f"WARNING: Execution thread exceeded timeout {timeout_ms}ms (R3 compliance)",
                file=sys.stderr,
            )
            return False, f"Execution timeout: exceeded {timeout_ms}ms (R3 compliance)", None

        if not exception_queue.empty():
            return False, None, exception_queue.get()

        if result_queue.empty():
            return False, "Execution did not complete", None

        return True, None, None

    def _build_failure_result(
        self,
        stdout_buf: io.StringIO,
        stderr_buf: io.StringIO,
        error: Exception,
        execution_time: float,
    ) -> dict[str, Any]:
        stderr = stderr_buf.getvalue() + f"\n{type(error).__name__}: {error}"
        return {
            "success": False,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr,
            "execution_time": execution_time,
            "error": str(error),
        }

    def _truncate_output(self, stdout: str, stderr: str) -> tuple[str, str, int]:
        stdout_bytes = len(stdout.encode("utf-8"))
        stderr_bytes = len(stderr.encode("utf-8"))
        total_output = stdout_bytes + stderr_bytes

        if total_output > 1048576:
            return stdout[:500000], stderr[:500000], 1000000

        return stdout, stderr, total_output

    def _record_exec_provenance(self, session: Any, code: str, output_bytes: int) -> str:
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        provenance = SnippetProvenance(
            file_path=None,
            start_line=None,
            end_line=None,
            content_hash=code_hash,
            source_type="execution",
        )
        session.provenance.append(provenance)
        session.output_bytes += output_bytes
        session.tool_call_count += 1
        return code_hash

    def exec_run(
        self,
        session_id: str,
        code: str,
        timeout_ms: int = MAX_EXEC_TIMEOUT_MS,
        memory_limit_mb: int = MAX_EXEC_MEMORY_MB,
    ) -> dict[str, Any]:
        """
        Execute safe code in isolated sandbox.

        Security improvements (R3 compliance):
        - AST-based blocking (prevents string manipulation bypass)
        - Comprehensive safe builtins (blocks eval, exec, compile, etc.)
        - Threading-based timeout (more reliable than signal)
        - Defense in depth: multiple layers of blocking

        Note: For stronger isolation, consider using Docker container mode
        (requires Docker infrastructure).
        """
        session, session_error = self._resolve_session(session_id)
        if session_error:
            return {"success": False, "error": session_error}

        validation_error = self._validate_exec_request(code, timeout_ms)
        if validation_error:
            return {"success": False, "error": validation_error}

        # Execute in restricted environment
        start_time = time.time()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        # R3 Compliance: Setup runtime blocking of dangerous modules
        original_modules = setup_runtime_blocking()

        # Create restricted execution environment
        restricted_globals, restricted_locals = create_restricted_environment()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                completed, execution_error, exception = self._run_code(
                    code=code,
                    timeout_ms=timeout_ms,
                    memory_limit_mb=memory_limit_mb,
                    restricted_globals=restricted_globals,
                    restricted_locals=restricted_locals,
                )

                if not completed and execution_error is not None:
                    return {"success": False, "error": execution_error}

                if exception is not None:
                    raise exception

            execution_time = time.time() - start_time

            stdout = stdout_buf.getvalue()
            stderr = stderr_buf.getvalue()
        except Exception as error:
            execution_time = time.time() - start_time
            return self._build_failure_result(stdout_buf, stderr_buf, error, execution_time)
        finally:
            restore_sys_modules(original_modules)

        # Success path: enforce output limits and provenance
        stdout, stderr, total_output = self._truncate_output(stdout, stderr)
        code_hash = self._record_exec_provenance(session, code, total_output)

        return {
            "success": True,
            "stdout": stdout,
            "stderr": stderr,
            "execution_time": execution_time,
            "artifacts": [],
            "provenance": {"code_hash": code_hash, "inputs": [], "outputs": []},
        }
