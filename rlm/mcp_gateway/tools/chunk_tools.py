"""Chunk creation and retrieval tools for RLM MCP Gateway."""

import sys
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.constants import MAX_CHUNK_BYTES, MAX_CHUNK_LINES
from rlm.mcp_gateway.handles import HandleManager
from rlm.mcp_gateway.provenance import ProvenanceTracker
from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.helpers import check_canary_token
from rlm.mcp_gateway.validation import PathValidator


class ChunkTools:
    """Chunk creation and retrieval tools."""

    def __init__(
        self,
        session_manager: SessionManager,
        handle_manager: HandleManager,
        path_validator: PathValidator,
        provenance_tracker: ProvenanceTracker,
        repo_root: Path,
        canary_token: str | None,
    ) -> None:
        """Initialize chunk tools.

        Args:
            session_manager: Session manager instance
            handle_manager: Handle manager instance
            path_validator: Path validator instance
            provenance_tracker: Provenance tracker instance
            repo_root: Repository root path
            canary_token: Optional canary token for bypass detection
        """
        self.session_manager = session_manager
        self.handle_manager = handle_manager
        self.path_validator = path_validator
        self.provenance_tracker = provenance_tracker
        self.repo_root = repo_root
        self.canary_token = canary_token

    def chunk_create(
        self,
        session_id: str,
        file_handle: str,
        strategy: str = "line_based",
        chunk_size: int = 100,
        overlap: int = 10,
        budget: int = 10,
    ) -> dict[str, Any]:
        """Create chunk IDs for a file."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Get file handle
        handle_info = self.handle_manager.get_file_handle(file_handle)
        if not handle_info:
            return {"success": False, "error": "Invalid file handle"}

        file_path = Path(handle_info["file_path"])

        # Validate path
        valid, error = self.path_validator.validate_path(str(file_path), session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        if not file_path.exists() or not file_path.is_file():
            return {"success": False, "error": f"File not found: {file_path}"}

        # Enforce limits
        if chunk_size > MAX_CHUNK_LINES:
            return {
                "success": False,
                "error": f"Chunk size too large: {chunk_size} > {MAX_CHUNK_LINES}",
            }

        if budget > 50:  # Reasonable limit
            return {"success": False, "error": f"Budget too large: {budget} > 50"}

        # Create chunks
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            chunk_ids: list[str] = []
            total_chunks = min(budget, (len(lines) + chunk_size - 1) // chunk_size)

            for i in range(total_chunks):
                chunk_id = self.handle_manager.create_chunk_id(file_handle, i)
                chunk_ids.append(chunk_id)

            session.tool_call_count += 1
            return {"success": True, "chunk_ids": chunk_ids, "total_chunks": len(chunk_ids)}
        except Exception as e:
            return {"success": False, "error": f"Error creating chunks: {e}"}

    def chunk_get(
        self, session_id: str, chunk_id: str, max_bytes: int = MAX_CHUNK_BYTES
    ) -> dict[str, Any]:
        """Get a chunk by ID."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Get chunk info
        chunk_info = self.handle_manager.get_chunk_info(chunk_id)
        if not chunk_info:
            return {"success": False, "error": "Invalid chunk ID"}

        # Get file handle
        handle_info = self.handle_manager.get_file_handle(chunk_info["file_handle"])
        if not handle_info:
            return {"success": False, "error": "Invalid file handle"}

        file_path = Path(handle_info["file_path"])

        # Validate path
        valid, error = self.path_validator.validate_path(str(file_path), session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        # Read file to determine chunk boundaries
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)
            chunk_index = chunk_info["chunk_index"]

            # Determine chunk boundaries (simplified - assumes 100 line chunks)
            # In full implementation, would track actual chunk boundaries from chunk_create
            chunk_size = 100  # Default chunk size
            start_line = chunk_index * chunk_size + 1
            end_line = min((chunk_index + 1) * chunk_size, total_lines)

            # R5 Compliance: Check for file looping (duplicate span access)
            relative_file_path = str(file_path.relative_to(self.repo_root))
            is_duplicate = session.has_accessed_span(relative_file_path, start_line, end_line)

            # Read chunk content
            chunk_lines = lines[start_line - 1 : end_line]
            content = "".join(chunk_lines)

            # Enforce byte limit
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > max_bytes:
                content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
                content_bytes = len(content.encode("utf-8"))

            # Track provenance
            provenance = self.provenance_tracker.create_chunk_provenance(
                relative_file_path, chunk_id, start_line, end_line, content
            )
            session.provenance.append(provenance)
            session.output_bytes += content_bytes
            session.tool_call_count += 1

            # Mark span as accessed (R5: deterministic progress)
            session.mark_span_accessed(relative_file_path, start_line, end_line)

            # Check for canary token (bypass detection)
            has_canary = check_canary_token(content, self.canary_token)

            # Build response with output labeling (bypass resistance)
            response: dict[str, Any] = {
                "success": True,
                "label": "DATA",  # Explicit labeling: content is DATA, not instructions
                "content": content,
                "chunk_id": chunk_id,
                "file_path": relative_file_path,
                "start_line": start_line,
                "end_line": end_line,
                "hash": provenance.content_hash,
                "provenance": provenance.to_dict(),
                "warning": None,  # Will be set if duplicate or canary detected
            }

            # Warn on duplicate access (R5: file looping prevention)
            if is_duplicate:
                response["warning"] = (
                    f"WARNING: This chunk span ({start_line}-{end_line}) has been accessed before. "
                    f"This may indicate file looping. Consider using rlm.search.query for more efficient access patterns."
                )

            # Warn on canary token detection (bypass detection)
            if has_canary:
                canary_warning = (
                    "SECURITY WARNING: Canary token detected in content. "
                    "This may indicate a bypass of RLM MCP Gateway. "
                    "Content should only be accessed through MCP tools with proper provenance."
                )
                if response["warning"]:
                    response["warning"] = response["warning"] + "\n" + canary_warning
                else:
                    response["warning"] = canary_warning
                # Log to stderr for monitoring
                print(
                    f"SECURITY ALERT: Canary token detected in chunk_get response for {relative_file_path}",
                    file=sys.stderr,
                )

            return response
        except Exception as e:
            return {"success": False, "error": f"Error reading chunk: {e}"}
