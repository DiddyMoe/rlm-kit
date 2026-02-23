"""Handle management for RLM MCP Gateway."""

import time
import uuid
from typing import Any


class HandleManager:
    """Manages file handles and chunk IDs.

    Optimized for local IDE integration:
    - Fast O(1) handle lookup
    - Efficient memory usage with bounded cache
    - Automatic cleanup of stale handles
    """

    def __init__(self, max_handles: int = 1000) -> None:
        """Initialize handle manager.

        Args:
            max_handles: Maximum number of handles to cache (default: 1000 for local IDE)
        """
        self._handles: dict[str, dict[str, Any]] = {}
        self._chunks: dict[str, dict[str, Any]] = {}
        self.max_handles = max_handles

    def create_file_handle(self, file_path: str, session_id: str) -> str:
        """Create a handle for a file.

        Optimized for local IDE: automatic cleanup when cache is full.
        """
        # Cleanup old handles if cache is full (optimized for memory)
        if len(self._handles) >= self.max_handles:
            # Remove oldest handles (simple FIFO cleanup)
            oldest_handles = sorted(self._handles.items(), key=lambda x: x[1].get("created_at", 0))[
                : self.max_handles // 2
            ]
            for handle_id, _ in oldest_handles:
                del self._handles[handle_id]

        handle_id = f"file_{uuid.uuid4().hex[:8]}"
        self._handles[handle_id] = {
            "file_path": file_path,
            "session_id": session_id,
            "created_at": time.time(),
        }
        return handle_id

    def get_file_handle(self, handle_id: str) -> dict[str, Any] | None:
        """Get file handle info."""
        return self._handles.get(handle_id)

    def list_file_handle_ids(self, prefix: str = "", session_id: str | None = None) -> list[str]:
        """List file handle IDs, optionally filtered by prefix and session ID."""
        handle_ids: list[str] = []
        for handle_id, handle in self._handles.items():
            if prefix and not handle_id.startswith(prefix):
                continue
            if session_id is not None and handle.get("session_id") != session_id:
                continue
            handle_ids.append(handle_id)
        return sorted(handle_ids)

    def create_chunk_id(
        self,
        file_handle: str,
        chunk_index: int,
        start_line: int | None = None,
        end_line: int | None = None,
        chunk_size: int | None = None,
        overlap: int | None = None,
        strategy: str | None = None,
    ) -> str:
        """Create a chunk ID."""
        chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
        self._chunks[chunk_id] = {
            "file_handle": file_handle,
            "chunk_index": chunk_index,
            "start_line": start_line,
            "end_line": end_line,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "strategy": strategy,
            "created_at": time.time(),
        }
        return chunk_id

    def get_chunk_info(self, chunk_id: str) -> dict[str, Any] | None:
        """Get chunk info."""
        return self._chunks.get(chunk_id)

    def list_chunk_ids(self, prefix: str = "") -> list[str]:
        """List chunk IDs, optionally filtered by prefix."""
        if not prefix:
            return sorted(self._chunks.keys())
        return sorted(chunk_id for chunk_id in self._chunks if chunk_id.startswith(prefix))
