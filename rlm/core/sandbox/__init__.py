"""Shared sandbox modules for safe code execution.

This module provides common sandbox functionality used across RLM environments
and execution tools, eliminating code duplication.

Safe builtins split (important for security and REPL correctness):
- **Strict sandbox (MCP rlm.exec.run):** Uses ``get_safe_builtins()`` only. Does not
  include ``globals``, ``locals``, ``__import__``, or ``open``. Use for bounded
  code execution from IDE agents (rlm.exec.run tool).
- **REPL environments (LocalREPL, DockerREPL, etc.):** Use ``get_safe_builtins_for_repl()``,
  which adds ``globals``, ``locals``, ``__import__``, and ``open`` so that RLM
  code can inspect the REPL namespace and load context. Only use in trusted
  REPL processes, not for arbitrary MCP-submitted code.
"""

from rlm.core.sandbox.ast_validator import (
    ASTValidationError,
    validate_ast,
)
from rlm.core.sandbox.restricted_exec import (
    BlockedModule,
    RestrictedBuiltins,
    create_restricted_environment,
    restore_sys_modules,
    setup_runtime_blocking,
)
from rlm.core.sandbox.safe_builtins import (
    get_safe_builtins,
    get_safe_builtins_for_repl,
)

__all__ = [
    "ASTValidationError",
    "BlockedModule",
    "RestrictedBuiltins",
    "create_restricted_environment",
    "get_safe_builtins",
    "get_safe_builtins_for_repl",
    "restore_sys_modules",
    "setup_runtime_blocking",
    "validate_ast",
]
