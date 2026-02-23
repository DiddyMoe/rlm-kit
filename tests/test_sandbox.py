"""Tests for AST sandbox validation."""

import pytest

from rlm.core.sandbox.ast_validator import (
    BLOCKED_FUNCTIONS,
    BLOCKED_MODULES,
    ASTValidationError,
    validate_ast,
)
from rlm.core.sandbox.safe_builtins import get_safe_builtins


class TestAstValidator:
    """Coverage for blocked and safe AST validation behavior."""

    def test_blocks_import_os(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked import"):
            validate_ast("import os")

    def test_blocks_import_subprocess(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked import"):
            validate_ast("import subprocess")

    @pytest.mark.parametrize(
        "code",
        [
            "import socket",
            "import shutil",
            "import ctypes",
            "from os import path",
        ],
    )
    def test_blocks_additional_imports(self, code: str) -> None:
        with pytest.raises(ASTValidationError, match="Blocked import"):
            validate_ast(code)

    def test_blocks_eval_call(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked function call"):
            validate_ast("eval('1 + 1')")

    def test_blocks_exec_call(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked function call"):
            validate_ast("exec('x = 1')")

    def test_blocks_getattr_bypass(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked dynamic access to builtin"):
            validate_ast("getattr(__builtins__, 'eval')")

    def test_blocks_subscript_bypass(self) -> None:
        with pytest.raises(ASTValidationError, match="Blocked dictionary access to builtin"):
            validate_ast("__builtins__['exec']")

    def test_allows_safe_code(self) -> None:
        validate_ast("import math\nx = 1 + 2\ny = math.sqrt(9)")

    def test_reports_syntax_error(self) -> None:
        with pytest.raises(ASTValidationError, match="Invalid Python syntax"):
            validate_ast("def broken(")

    @pytest.mark.parametrize("module_name", sorted(BLOCKED_MODULES))
    def test_blocks_all_blocked_modules(self, module_name: str) -> None:
        with pytest.raises(ASTValidationError, match="Blocked import"):
            validate_ast(f"import {module_name}")

    @pytest.mark.parametrize("function_name", sorted(BLOCKED_FUNCTIONS))
    def test_blocks_all_blocked_functions(self, function_name: str) -> None:
        call_code = _blocked_function_call(function_name)
        with pytest.raises(ASTValidationError, match="Blocked function call"):
            validate_ast(call_code)


def _blocked_function_call(function_name: str) -> str:
    if function_name in {"exit", "quit"}:
        return f"{function_name}()"
    if function_name == "__import__":
        return "__import__('os')"
    return f"{function_name}('x')"


def test_strict_builtins_block_runtime_input() -> None:
    strict_builtins = get_safe_builtins()
    with pytest.raises(TypeError):
        exec("input('prompt')", {"__builtins__": strict_builtins}, {})
