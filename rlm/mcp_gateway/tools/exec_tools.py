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
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Enforce code size limit
        code_bytes = len(code.encode("utf-8"))
        if code_bytes > MAX_EXEC_CODE_SIZE:
            return {
                "success": False,
                "error": f"Code too large: {code_bytes} > {MAX_EXEC_CODE_SIZE} bytes",
            }

        # Enforce timeout
        if timeout_ms > 30000:  # Max 30 seconds
            return {"success": False, "error": f"Timeout too large: {timeout_ms}ms > 30000ms"}

        # Security: AST-based blocking (more robust than pattern matching)
        try:
            validate_ast(code)
        except ASTValidationError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            # If AST parsing fails, fall back to pattern matching (shouldn't happen)
            return {"success": False, "error": f"Code validation error: {e}"}

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
                # R3 Compliance: Execute with timeout and resource limits
                result_queue: queue.Queue[bool] = queue.Queue()
                exception_queue: queue.Queue[Exception] = queue.Queue()

                # R3 Compliance: Set memory limit if possible (Unix only)
                if hasattr(resource, "RLIMIT_AS") and memory_limit_mb > 0:
                    try:
                        # Set memory limit (RLIMIT_AS = address space limit)
                        memory_bytes = memory_limit_mb * 1024 * 1024
                        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
                        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, hard))
                    except (OSError, ValueError):
                        # Memory limits not supported on this platform
                        pass

                def execute_in_thread() -> None:
                    try:
                        exec(code, restricted_globals, restricted_locals)
                        result_queue.put(True)
                    except MemoryError:
                        exception_queue.put(
                            MemoryError(
                                f"Memory limit exceeded: {memory_limit_mb}MB (R3 compliance)"
                            )
                        )
                    except Exception as e:
                        exception_queue.put(e)

                thread = threading.Thread(target=execute_in_thread, daemon=True)
                thread.start()
                thread.join(timeout=timeout_ms / 1000.0)

                # R3 Compliance: Check if thread is still alive (timeout exceeded)
                if thread.is_alive():
                    # Thread is still running - we can't kill it directly, but daemon=True
                    # means it will be terminated when main thread exits
                    # Log warning for monitoring
                    print(
                        f"WARNING: Execution thread exceeded timeout {timeout_ms}ms (R3 compliance)",
                        file=sys.stderr,
                    )
                    # Restore sys.modules before returning
                    restore_sys_modules(original_modules)
                    return {
                        "success": False,
                        "error": f"Execution timeout: exceeded {timeout_ms}ms (R3 compliance)",
                    }

                # Check for exceptions
                if not exception_queue.empty():
                    raise exception_queue.get()

                # Check if execution completed
                if result_queue.empty():
                    # R3 Compliance: Restore sys.modules before returning
                    restore_sys_modules(original_modules)
                    return {"success": False, "error": "Execution did not complete"}

            execution_time = time.time() - start_time

            stdout = stdout_buf.getvalue()
            stderr = stderr_buf.getvalue()
        except Exception as e:
            restore_sys_modules(original_modules)
            execution_time = time.time() - start_time
            stderr = stderr_buf.getvalue() + f"\n{type(e).__name__}: {e}"
            return {
                "success": False,
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr,
                "execution_time": execution_time,
                "error": str(e),
            }
        finally:
            restore_sys_modules(original_modules)

        # Success path: enforce output limits and provenance
        stdout_bytes = len(stdout.encode("utf-8"))
        stderr_bytes = len(stderr.encode("utf-8"))
        total_output = stdout_bytes + stderr_bytes

        if total_output > 1048576:  # 1MB max
            stdout = stdout[:500000]
            stderr = stderr[:500000]
            total_output = 1000000

        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        provenance = SnippetProvenance(
            file_path=None,
            start_line=None,
            end_line=None,
            content_hash=code_hash,
            source_type="execution",
        )
        session.provenance.append(provenance)
        session.output_bytes += total_output
        session.tool_call_count += 1

        return {
            "success": True,
            "stdout": stdout,
            "stderr": stderr,
            "execution_time": execution_time,
            "artifacts": [],
            "provenance": {"code_hash": code_hash, "inputs": [], "outputs": []},
        }
