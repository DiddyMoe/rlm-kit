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

        # R3 Compliance: Block path traversal patterns before normalization
        if ".." in path or (path.startswith("/") and not path.startswith(tuple(allowed_roots))):
            normalized_check = os.path.normpath(path)
            if ".." in normalized_check:
                return False, f"Path traversal detected: '{path}' contains '..'"

        # Normalize and resolve symlinks (prevents symlink-based path traversal)
        try:
            normalized = os.path.normpath(path)
            if not os.path.isabs(normalized):
                # Make absolute relative to first allowed root
                if allowed_roots:
                    normalized = os.path.abspath(os.path.join(allowed_roots[0], normalized))
                else:
                    normalized = os.path.abspath(normalized)

            # R3 Compliance: Check if path is a symlink pointing outside roots
            if os.path.islink(normalized):
                symlink_resolved = os.path.realpath(normalized)

                # Validate symlink target is within allowed roots
                symlink_valid = False
                for root in allowed_roots:
                    root_norm = os.path.realpath(os.path.abspath(root))
                    try:
                        Path(symlink_resolved).relative_to(root_norm)
                        symlink_valid = True
                        break
                    except ValueError:
                        continue

                if not symlink_valid:
                    return False, f"Symlink '{path}' points outside allowed roots"

            # Resolve symlinks to prevent symlink-based bypass
            normalized = os.path.realpath(normalized)
        except Exception as e:
            return False, f"Invalid path: {e}"

        # Check if within any allowed root (also resolve symlinks in roots)
        for root in allowed_roots:
            root_norm = os.path.normpath(os.path.abspath(root))
            try:
                # Resolve symlinks in root as well
                root_norm = os.path.realpath(root_norm)
                # Check if path is within root
                Path(normalized).relative_to(root_norm)
                return True, None
            except ValueError:
                # Not within this root, try next
                continue

        return False, f"Path '{path}' is outside allowed roots: {allowed_roots}"

    @classmethod
    def is_restricted_path(cls, path: str) -> bool:
        """Check if a path is restricted (e.g., .git, secrets)."""
        path_str = str(path).lower()
        return any(pattern in path_str for pattern in cls._RESTRICTED_PATTERNS)
