"""Filesystem metadata tools for RLM MCP Gateway."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rlm.mcp_gateway.constants import MAX_FS_LIST_ITEMS
from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.file_cache import get_file_cache
from rlm.mcp_gateway.validation import PathValidator

if TYPE_CHECKING:
    from rlm.mcp_gateway.handles import HandleManager


class FilesystemTools:
    """Filesystem metadata tools (no content)."""

    def __init__(
        self,
        session_manager: SessionManager,
        path_validator: PathValidator,
        repo_root: Path,
    ) -> None:
        """Initialize filesystem tools.

        Args:
            session_manager: Session manager instance
            path_validator: Path validator instance
            repo_root: Repository root path
        """
        self.session_manager = session_manager
        self.path_validator = path_validator
        self.repo_root = repo_root
        self.file_cache = get_file_cache()  # Shared LRU cache for file metadata

    def fs_list(
        self, session_id: str, root: str, depth: int = 2, patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """List directory contents (metadata only, no content)."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Validate path
        valid, error = self.path_validator.validate_path(root, session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            return {"success": False, "error": f"Not a directory: {root}"}

        # List items (metadata only)
        items: list[dict[str, Any]] = []
        try:
            for item in sorted(root_path.iterdir()):
                if self.path_validator.is_restricted_path(str(item)):
                    continue

                if len(items) >= MAX_FS_LIST_ITEMS:
                    items.append({"type": "truncated", "message": "Max items reached"})
                    break

                if item.is_file():
                    # Use cache for file metadata
                    metadata = self.file_cache.get_or_compute_metadata(
                        item, include_hash=True, include_lines=False
                    )
                    items.append(
                        {
                            "type": "file",
                            "path": str(item.relative_to(self.repo_root)),
                            "size": metadata["size"],
                            "hash": metadata.get("hash"),
                        }
                    )
                elif item.is_dir() and depth > 0:
                    items.append(
                        {
                            "type": "directory",
                            "path": str(item.relative_to(self.repo_root)),
                            "item_count": len(list(item.iterdir())) if depth > 1 else None,
                        }
                    )
        except Exception as e:
            return {"success": False, "error": f"Error listing directory: {e}"}

        session.tool_call_count += 1
        return {"success": True, "items": items}

    def fs_handle_create(
        self,
        session_id: str,
        file_path: str,
        handle_manager: "HandleManager",  # type: ignore[name-defined]
    ) -> dict[str, Any]:
        """Create a file handle from a file path."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Validate path
        valid, error = self.path_validator.validate_path(file_path, session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        file_path_obj = Path(file_path)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            return {"success": False, "error": f"File not found: {file_path}"}

        # Create handle
        handle_id = handle_manager.create_file_handle(str(file_path_obj.resolve()), session_id)
        session.tool_call_count += 1

        return {
            "success": True,
            "file_handle": handle_id,
            "file_path": str(file_path_obj.relative_to(self.repo_root)),
        }

    def fs_manifest(self, session_id: str, root: str) -> dict[str, Any]:
        """Get file manifest (hashes and sizes only)."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Validate path
        valid, error = self.path_validator.validate_path(root, session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        root_path = Path(root)
        if not root_path.exists():
            return {"success": False, "error": f"Path does not exist: {root}"}

        # Collect file metadata
        files: list[dict[str, Any]] = []
        total_size = 0

        # R3 Compliance: Add depth limit to prevent unbounded enumeration
        max_manifest_depth = 10
        files_scanned = 0
        max_files_manifest = 1000  # Limit total files in manifest

        try:
            for file_path in root_path.rglob("*"):
                # R3 Compliance: Enforce depth limit
                depth = len(file_path.relative_to(root_path).parts)
                if depth > max_manifest_depth:
                    continue

                # R3 Compliance: Enforce file count limit
                files_scanned += 1
                if files_scanned > max_files_manifest:
                    break

                if file_path.is_file() and not self.path_validator.is_restricted_path(
                    str(file_path)
                ):
                    # Use cache for file metadata
                    metadata = self.file_cache.get_or_compute_metadata(
                        file_path, include_hash=True, include_lines=True
                    )
                    files.append(
                        {
                            "path": str(file_path.relative_to(self.repo_root)),
                            "size": metadata["size"],
                            "hash": metadata.get("hash"),
                            "lines": metadata.get("lines"),
                        }
                    )
                    total_size += metadata["size"]

                    if len(files) >= MAX_FS_LIST_ITEMS:
                        break
        except Exception as e:
            return {"success": False, "error": f"Error creating manifest: {e}"}

        session.tool_call_count += 1
        return {"success": True, "files": files, "total_size": total_size}
