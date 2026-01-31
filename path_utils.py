"""
Repository path utilities.

Repo root is discovered by walking up from this file until a directory
containing pyproject.toml is found. This works regardless of where
path_utils.py lives and avoids brittle .parent.parent chains.

Scripts and examples: add repo root to sys.path before importing:
    import sys
    from pathlib import Path
    _root = _find_repo_root(Path(__file__).resolve().parent)
    sys.path.insert(0, str(_root))
    from path_utils import REPO_ROOT, SCRIPT_DIR  # noqa: E402
"""

from pathlib import Path

_MARKER = "pyproject.toml"
_MAX_ANCESTORS = 30


def find_repo_root(start: Path | None = None) -> Path:
    """Return repo root by walking up until a directory contains pyproject.toml."""
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(_MAX_ANCESTORS):
        if (current / _MARKER).is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(
        f"Repo root not found: no {_MARKER} in ancestors of {start or __file__!r}"
    )


# When this module is at repo root, __file__'s parent is repo root.
REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
SCRIPT_DIR = REPO_ROOT / "scripts"


def ensure_repo_on_path(caller_file: str) -> Path:
    """
    Find repo root from caller's __file__ and prepend it to sys.path.
    Call before importing path_utils from scripts/examples that are not at repo root.
    Returns the repo root Path (then do: from path_utils import REPO_ROOT, SCRIPT_DIR).
    """
    import sys

    root = find_repo_root(Path(caller_file).resolve().parent)
    root_str = str(root)
    # O(1): only check first slot to avoid duplicate insert
    if not sys.path or sys.path[0] != root_str:
        sys.path.insert(0, root_str)
    return root
