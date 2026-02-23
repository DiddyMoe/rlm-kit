"""AST-based code validation for sandboxed execution."""

import ast


class ASTValidationError(Exception):
    """Raised when AST validation fails."""

    def __init__(self, message: str) -> None:
        """Initialize validation error.

        Args:
            message: Error message describing the validation failure
        """
        super().__init__(message)
        self.message = message


# Blocked modules (network, process, filesystem)
_BLOCKED_MODULES = {
    "socket",
    "requests",
    "urllib",
    "urllib2",
    "http",
    "httpx",
    "subprocess",
    "multiprocessing",
    "os",
    "sys",
    "shutil",
    "pickle",
    "marshal",
    "ctypes",
    "importlib",
    "__builtin__",
    "builtins",
    "imp",
    "pkgutil",
    "pydoc",
    "runpy",
    "zipimport",
}

# Blocked function calls
_BLOCKED_FUNCTIONS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "file",
    "input",
    "raw_input",
    "execfile",
    "reload",
    "exit",
    "quit",
}

BLOCKED_MODULES: frozenset[str] = frozenset(_BLOCKED_MODULES)
BLOCKED_FUNCTIONS: frozenset[str] = frozenset(_BLOCKED_FUNCTIONS)


def _extract_string_constant(node: ast.AST) -> str | None:
    """Extract string values from AST constant nodes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _check_import_node(node: ast.AST) -> str | None:
    """Check if an import node is blocked.

    Args:
        node: AST import node to check

    Returns:
        Error message if blocked, None otherwise
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in _BLOCKED_MODULES:
                return f"Blocked import: {alias.name}"
    if isinstance(node, ast.ImportFrom):
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in _BLOCKED_MODULES:
                return f"Blocked import: {node.module}"
    return None


def _check_call_node(node: ast.Call) -> str | None:
    """Check if a function call node is blocked.

    Args:
        node: AST call node to check

    Returns:
        Error message if blocked, None otherwise
    """
    if isinstance(node.func, ast.Name):
        if node.func.id in _BLOCKED_FUNCTIONS:
            return f"Blocked function call: {node.func.id}()"
    elif isinstance(node.func, ast.Attribute):
        # Check for os.system, subprocess.call, etc.
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id in _BLOCKED_MODULES:
                return f"Blocked module call: {node.func.value.id}.{node.func.attr}()"
    return None


def _check_getattr_builtin_access(node: ast.Call) -> str | None:
    """Check if getattr is accessing dangerous builtin attributes.

    Args:
        node: AST call node to check

    Returns:
        Error message if blocked, None otherwise
    """
    if not _is_getattr_call(node):
        return None

    if len(node.args) < 2:
        return None

    first_arg = node.args[0]
    second_arg = node.args[1]

    if not _is_builtins_access_target(first_arg):
        return None

    attr_name = _extract_string_constant(second_arg)
    if attr_name is None:
        return None

    if attr_name in _BLOCKED_FUNCTIONS:
        return f"Blocked dynamic access to builtin: getattr(__builtins__, '{attr_name}')"

    return None


def _is_getattr_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "getattr"


def _is_builtins_access_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "__builtins__"

    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id == "__builtins__"

    return False


def _check_node_safety(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _check_import_node(node)

    if isinstance(node, ast.Call):
        error = _check_call_node(node)
        if error:
            return error
        return _check_getattr_builtin_access(node)

    if isinstance(node, ast.Subscript):
        return _check_subscript_builtin_access(node)

    return None


def _check_subscript_builtin_access(node: ast.Subscript) -> str | None:
    """Check if dictionary-style access to dangerous builtins is attempted.

    Args:
        node: AST subscript node to check

    Returns:
        Error message if blocked, None otherwise
    """
    if not isinstance(node.value, ast.Name) or node.value.id != "__builtins__":
        return None

    key = _extract_string_constant(node.slice)
    if key is None:
        return None

    if key in _BLOCKED_FUNCTIONS:
        return f"Blocked dictionary access to builtin: __builtins__['{key}']"

    return None


def validate_ast(code: str) -> None:
    """
    Validate code using AST analysis to block dangerous operations.

    Args:
        code: Python code to validate

    Raises:
        ASTValidationError: If code contains blocked operations
        SyntaxError: If code has invalid Python syntax
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise ASTValidationError(f"Invalid Python syntax: {e}") from e

    for node in ast.walk(tree):
        error = _check_node_safety(node)
        if error:
            raise ASTValidationError(error)
