"""Helper functions for MCP Gateway tools."""

import hashlib
import re
from pathlib import Path


def load_canary_token(repo_root: Path) -> str | None:
    """Load canary token from repository for bypass detection."""
    canary_file = repo_root / ".rlm_canary_token.txt"
    if canary_file.exists():
        try:
            content = canary_file.read_text()
            # Extract token (format: "Token: RLM_CANARY_...")
            match = re.search(r"Token:\s*(RLM_CANARY_\w+)", content)
            if match:
                return match.group(1)
        except Exception:
            pass
    return None


def check_canary_token(content: str, canary_token: str | None) -> bool:
    """Check if content contains canary token (indicates potential bypass)."""
    if not canary_token:
        return False
    return canary_token in content


def file_hash(file_path: Path) -> str:
    """Compute hash of a file."""
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return ""


def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return len(f.readlines())
    except Exception:
        return 0
