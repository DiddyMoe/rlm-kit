"""Session management tools for RLM MCP Gateway."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.session import SessionManager


class SessionTools:
    """Session management tools."""

    def __init__(
        self,
        session_manager: SessionManager,
        repo_root: Path,
    ) -> None:
        """Initialize session tools.

        Args:
            session_manager: Session manager instance
            repo_root: Repository root path
        """
        self.session_manager = session_manager
        self.repo_root = repo_root

    def session_create(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new RLM session."""
        session = self.session_manager.create_session(config)
        return {
            "session_id": session.session_id,
            "config": asdict(session.config),
            "created_at": session.created_at,
        }

    def session_close(self, session_id: str) -> dict[str, Any]:
        """Close a session."""
        success = self.session_manager.close_session(session_id)
        return {"success": success}

    def roots_set(self, session_id: str, roots: list[str]) -> dict[str, Any]:
        """Set allowed root directories for a session."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Validate roots exist and are absolute
        validated_roots: list[str] = []
        for root in roots:
            root_path = Path(root)
            if not root_path.is_absolute():
                root_path = (self.repo_root / root).resolve()

            if not root_path.exists():
                return {"success": False, "error": f"Root does not exist: {root}"}

            validated_roots.append(str(root_path))

        session.allowed_roots = validated_roots
        return {"success": True, "roots": validated_roots}
