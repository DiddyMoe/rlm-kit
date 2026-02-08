"""
Bootstrap: find repo root by walking up until pyproject.toml.
No dependency on path_utils; used so scripts can add repo root to sys.path
before importing path_utils.
"""

from pathlib import Path

_MARKER = "pyproject.toml"
_MAX_ANCESTORS = 30


def find_repo_root(start: Path) -> Path:
    """Return repo root by walking up until a directory contains pyproject.toml."""
    current = start.resolve()
    for _ in range(_MAX_ANCESTORS):
        if (current / _MARKER).is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(f"Repo root not found: no {_MARKER} in ancestors of {start!r}")
