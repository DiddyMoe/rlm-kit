"""Restricted execution environment setup for sandboxed code execution."""

import sys
from types import ModuleType
from typing import Any, cast

from rlm.core.sandbox.safe_builtins import get_safe_builtins


class BlockedModule:
    """Blocked module that raises error on any access."""

    def __getattr__(self, name: str) -> None:
        """Block any attribute access.

        Args:
            name: Attribute name

        Raises:
            ImportError: Always raised to block module access
        """
        raise ImportError(
            "Module access blocked for security (R3 compliance). "
            "Network, process, and filesystem access are not allowed in sandbox."
        )

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Block any function call.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Raises:
            ImportError: Always raised to block module calls
        """
        raise ImportError(
            "Module call blocked for security (R3 compliance). "
            "Network, process, and filesystem access are not allowed in sandbox."
        )


# Modules to block at runtime
_BLOCKED_MODULES_LIST = [
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
]


class RestrictedBuiltins:
    """Restricted builtins that blocks dangerous attribute access."""

    def __init__(self, safe_dict: dict[str, Any]) -> None:
        """Initialize restricted builtins.

        Args:
            safe_dict: Dictionary of safe builtins
        """
        object.__setattr__(self, "_safe", safe_dict)

    def __getattr__(self, name: str) -> Any:
        """Get attribute with blocking for dangerous builtins.

        Args:
            name: Attribute name

        Returns:
            Safe builtin value

        Raises:
            AttributeError: If attribute is blocked or not available
        """
        blocked_attrs = {
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "file",
            "input",
            "globals",
            "locals",
        }
        if name in blocked_attrs:
            raise AttributeError(f"Access to '{name}' is blocked for security (R3 compliance)")
        if name in self._safe:
            return self._safe[name]
        raise AttributeError(f"'{name}' is not available in sandbox")

    def __setattr__(self, name: str, value: Any) -> None:
        """Block setting dangerous attributes.

        Args:
            name: Attribute name
            value: Attribute value

        Raises:
            AttributeError: If trying to modify builtins
        """
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"Cannot modify builtins in sandbox (R3 compliance): '{name}'")

    def __getitem__(self, key: str) -> Any:
        """Block dictionary-style access to dangerous builtins.

        Args:
            key: Dictionary key

        Returns:
            Safe builtin value

        Raises:
            KeyError: If key is blocked or not available
        """
        blocked_attrs = {
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "file",
        }
        if key in blocked_attrs:
            raise KeyError(f"Access to '{key}' is blocked for security (R3 compliance)")
        if key in self._safe:
            return self._safe[key]
        raise KeyError(f"'{key}' is not available in sandbox")


def _create_safe_import() -> Any:
    """Create a safe __import__ function that blocks all imports.

    Returns:
        Function that raises ImportError
    """
    blocked = set(_BLOCKED_MODULES_LIST)

    def safe_import(name: str, *args: Any, **kwargs: Any) -> None:
        """Block all imports for security.

        Args:
            name: Module name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Raises:
            ImportError: Always raised to block imports
        """
        if name in blocked or any(name.startswith(b) for b in blocked):
            raise ImportError(f"Import of '{name}' is blocked for security (R3 compliance)")
        # For allowed imports, we still block them at AST level, but this is defense in depth
        raise ImportError("Direct imports are not allowed in sandbox")

    return safe_import


def setup_runtime_blocking() -> dict[str, Any]:
    """
    Setup runtime blocking of dangerous modules in sys.modules.

    Returns:
        Dictionary mapping module names to original module objects (for restoration)
    """
    original_modules: dict[str, Any] = {}
    for mod_name in _BLOCKED_MODULES_LIST:
        if mod_name in sys.modules:
            original_modules[mod_name] = sys.modules[mod_name]
        sys.modules[mod_name] = cast(ModuleType, BlockedModule())
    return original_modules


def restore_sys_modules(original_modules: dict[str, Any]) -> None:
    """
    Restore original sys.modules after execution.

    Args:
        original_modules: Dictionary of original module objects to restore
    """
    for mod_name, mod_obj in original_modules.items():
        sys.modules[mod_name] = mod_obj
    # Remove blocked modules if they weren't there originally
    for mod_name in _BLOCKED_MODULES_LIST:
        if mod_name not in original_modules:
            sys.modules.pop(mod_name, None)


def create_restricted_environment() -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Create a restricted execution environment with safe builtins.

    Returns:
        Tuple of (restricted_globals, restricted_locals) dictionaries
    """
    safe_builtins = get_safe_builtins()
    safe_builtins["__import__"] = _create_safe_import()

    # Replace safe_builtins dict with RestrictedBuiltins class
    restricted_builtins_obj = RestrictedBuiltins(safe_builtins)

    # Create restricted execution environment
    restricted_globals: dict[str, Any] = {
        "__builtins__": restricted_builtins_obj,
        "__name__": "__main__",
        "__doc__": None,
        "__file__": None,
        "__package__": None,
    }
    restricted_locals: dict[str, Any] = {}

    return restricted_globals, restricted_locals
