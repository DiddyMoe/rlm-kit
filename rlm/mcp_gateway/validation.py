"""Path validation and security for RLM MCP Gateway."""

import os
from pathlib import Path


class PathValidator:
    """Validates and normalizes paths with root boundary enforcement.

    When multiple allowed_roots are configured, a path is valid if it falls
    under any one of them (after normalization and symlink resolution).
    """

    _RESTRICTED_PATTERNS = [
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".pytest_cache",
        ".env",
        "secrets",
        "credentials",
        ".secret",
    ]

    RESTRICTED_PATTERNS: tuple[str, ...] = tuple(_RESTRICTED_PATTERNS)

    @staticmethod
    def validate_path(path: str, allowed_roots: list[str]) -> tuple[bool, str | None]:
        """Validate that a path is within allowed roots.

        Enhanced security (R3 compliance):
        - Uses realpath() to resolve symlinks and prevent path traversal attacks
        - Explicitly checks for path traversal patterns (../)
        - Validates symlinks don't point outside roots
        - Normalizes paths before validation
        """
        if not allowed_roots:
            return False, "No allowed roots configured for session"

        traversal_error = PathValidator._check_traversal(path, allowed_roots)
        if traversal_error is not None:
            return False, traversal_error

        try:
            normalized = PathValidator._normalize_and_resolve(path, allowed_roots)
        except Exception as e:
            return False, f"Invalid path: {e}"

        if PathValidator._is_within_allowed_roots(normalized, allowed_roots):
            return True, None

        return False, f"Path '{path}' is outside allowed roots: {allowed_roots}"

    @staticmethod
    def _check_traversal(path: str, allowed_roots: list[str]) -> str | None:
        if ".." not in path and (not path.startswith("/") or path.startswith(tuple(allowed_roots))):
            return None
        normalized_check = os.path.normpath(path)
        if ".." in normalized_check:
            return f"Path traversal detected: '{path}' contains '..'"
        return None

    @staticmethod
    def _normalize_and_resolve(path: str, allowed_roots: list[str]) -> str:
        normalized = os.path.normpath(path)
        if not os.path.isabs(normalized):
            normalized = os.path.abspath(os.path.join(allowed_roots[0], normalized))

        if os.path.islink(normalized):
            PathValidator._validate_symlink_target(path, normalized, allowed_roots)

        return os.path.realpath(normalized)

    @staticmethod
    def _validate_symlink_target(path: str, normalized: str, allowed_roots: list[str]) -> None:
        symlink_resolved = os.path.realpath(normalized)
        if PathValidator._is_within_allowed_roots(symlink_resolved, allowed_roots):
            return
        raise ValueError(f"Symlink '{path}' points outside allowed roots")

    @staticmethod
    def _is_within_allowed_roots(normalized_path: str, allowed_roots: list[str]) -> bool:
        for root in allowed_roots:
            root_norm = os.path.realpath(os.path.normpath(os.path.abspath(root)))
            try:
                Path(normalized_path).relative_to(root_norm)
                return True
            except ValueError:
                continue
        return False

    @classmethod
    def is_restricted_path(cls, path: str) -> bool:
        """Check if a path is restricted (e.g., .git, secrets)."""
        path_str = str(path).lower()
        return any(pattern in path_str for pattern in cls._RESTRICTED_PATTERNS)
