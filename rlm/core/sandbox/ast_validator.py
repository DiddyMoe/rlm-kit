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


def _check_import_node(node: ast.Import | ast.ImportFrom) -> str | None:
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
    elif isinstance(node, ast.ImportFrom):
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
    if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
        return None

    if len(node.args) < 2:
        return None

    first_arg = node.args[0]
    second_arg = node.args[1]

    # Check if accessing __builtins__
    is_builtins_access = False
    if isinstance(first_arg, ast.Name) and first_arg.id == "__builtins__":
        is_builtins_access = True
    elif isinstance(first_arg, ast.Attribute):
        if isinstance(first_arg.value, ast.Name) and first_arg.value.id == "__builtins__":
            is_builtins_access = True

    if not is_builtins_access:
        return None

    # Extract attribute name
    if isinstance(second_arg, ast.Constant):
        attr_name = second_arg.value
    elif isinstance(second_arg, ast.Str):  # Python < 3.8
        attr_name = second_arg.s
    else:
        return None

    if attr_name in _BLOCKED_FUNCTIONS:
        return f"Blocked dynamic access to builtin: getattr(__builtins__, '{attr_name}')"

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

    # Extract key
    if isinstance(node.slice, ast.Constant):
        key = node.slice.value
    elif isinstance(node.slice, ast.Str):  # Python < 3.8
        key = node.slice.s
    elif isinstance(node.slice, ast.Index):  # Python < 3.9
        if isinstance(node.slice.value, ast.Constant):
            key = node.slice.value.value
        elif isinstance(node.slice.value, ast.Str):
            key = node.slice.value.s
        else:
            return None
    else:
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

    # Walk AST and check for blocked operations
    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            error = _check_import_node(node)
            if error:
                raise ASTValidationError(error)

        # Check function calls
        if isinstance(node, ast.Call):
            error = _check_call_node(node)
            if error:
                raise ASTValidationError(error)

            # Check for getattr(__builtins__, ...) bypass attempts
            error = _check_getattr_builtin_access(node)
            if error:
                raise ASTValidationError(error)

        # Check for __builtins__["..."] bypass attempts
        if isinstance(node, ast.Subscript):
            error = _check_subscript_builtin_access(node)
            if error:
                raise ASTValidationError(error)
