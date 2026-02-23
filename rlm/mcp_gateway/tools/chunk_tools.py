"""Chunk creation and retrieval tools for RLM MCP Gateway."""

import sys
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.constants import MAX_CHUNK_BYTES, MAX_CHUNK_LINES
from rlm.mcp_gateway.handles import HandleManager
from rlm.mcp_gateway.provenance import ProvenanceTracker
from rlm.mcp_gateway.session import Session, SessionManager
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

    def _validate_chunk_params(self, chunk_size: int, overlap: int, budget: int) -> str | None:
        if chunk_size > MAX_CHUNK_LINES:
            return f"Chunk size too large: {chunk_size} > {MAX_CHUNK_LINES}"
        if budget > 50:
            return f"Budget too large: {budget} > 50"
        if chunk_size <= 0:
            return f"Invalid chunk_size: {chunk_size}"
        if overlap < 0:
            return f"Invalid overlap: {overlap}"
        return None

    def _detect_chunk_overlap(self, chunk_size: int, overlap: int) -> tuple[int, str | None]:
        if overlap >= chunk_size:
            return 0, f"Invalid overlap: {overlap} must be less than chunk_size {chunk_size}"
        return chunk_size - overlap, None

    def _create_chunk_ids(
        self,
        lines: list[str],
        file_handle: str,
        chunk_size: int,
        overlap_step: int,
        budget: int,
        strategy: str,
    ) -> list[str]:
        chunk_ids: list[str] = []
        total_lines = len(lines)
        start_line = 1
        chunk_index = 0

        while start_line <= total_lines and len(chunk_ids) < budget:
            end_line = min(start_line + chunk_size - 1, total_lines)
            chunk_id = self.handle_manager.create_chunk_id(
                file_handle=file_handle,
                chunk_index=chunk_index,
                start_line=start_line,
                end_line=end_line,
                chunk_size=chunk_size,
                overlap=chunk_size - overlap_step,
                strategy=strategy,
            )
            chunk_ids.append(chunk_id)
            chunk_index += 1
            start_line += overlap_step

        return chunk_ids

    def _resolve_chunk_create_context(
        self, session_id: str, file_handle: str
    ) -> tuple[Session | None, Path | None, str | None]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None, None, "Session not found"

        within_budget, budget_error = self.session_manager.check_budget(session)
        if not within_budget:
            return None, None, budget_error

        handle_info = self.handle_manager.get_file_handle(file_handle)
        if not handle_info:
            return None, None, "Invalid file handle"

        file_path = Path(handle_info["file_path"])
        valid, path_error = self.path_validator.validate_path(str(file_path), session.allowed_roots)
        if not valid:
            return None, None, path_error

        if not file_path.exists() or not file_path.is_file():
            return None, None, f"File not found: {file_path}"

        return session, file_path, None

    def _resolve_chunk_get_context(
        self, session_id: str, chunk_id: str
    ) -> tuple[Session | None, dict[str, Any] | None, Path | None, str | None]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None, None, None, "Session not found"

        within_budget, budget_error = self.session_manager.check_budget(session)
        if not within_budget:
            return None, None, None, budget_error

        chunk_info = self.handle_manager.get_chunk_info(chunk_id)
        if not chunk_info:
            return None, None, None, "Invalid chunk ID"

        handle_info = self.handle_manager.get_file_handle(chunk_info["file_handle"])
        if not handle_info:
            return None, None, None, "Invalid file handle"

        file_path = Path(handle_info["file_path"])
        valid, path_error = self.path_validator.validate_path(str(file_path), session.allowed_roots)
        if not valid:
            return None, None, None, path_error

        return session, chunk_info, file_path, None

    def _reconstruct_metadata(
        self, chunk_info: dict[str, Any], total_lines: int, chunk_id: str
    ) -> tuple[int, int, str | None]:
        chunk_index = int(chunk_info.get("chunk_index", 0))
        stored_start = chunk_info.get("start_line")
        stored_end = chunk_info.get("end_line")

        if isinstance(stored_start, int) and isinstance(stored_end, int):
            start_line = max(1, stored_start)
            end_line = min(total_lines, stored_end)
        else:
            chunk_size = int(chunk_info.get("chunk_size") or 100)
            start_line = chunk_index * chunk_size + 1
            end_line = min((chunk_index + 1) * chunk_size, total_lines)

        if end_line < start_line:
            return 0, 0, f"Invalid chunk bounds for {chunk_id}"

        return start_line, end_line, None

    def _append_warning(self, warning: str | None, extra_warning: str) -> str:
        if warning:
            return warning + "\n" + extra_warning
        return extra_warning

    def _format_chunk_result(
        self,
        chunk_id: str,
        relative_file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        provenance_hash: str,
        provenance: dict[str, Any],
        warning: str | None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "label": "DATA",
            "content": content,
            "chunk_id": chunk_id,
            "file_path": relative_file_path,
            "start_line": start_line,
            "end_line": end_line,
            "hash": provenance_hash,
            "provenance": provenance,
            "warning": warning,
        }

    def _truncate_content(self, content: str, max_bytes: int) -> tuple[str, int]:
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= max_bytes:
            return content, content_bytes
        truncated = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        return truncated, len(truncated.encode("utf-8"))

    def _build_chunk_warning(
        self,
        is_duplicate: bool,
        has_canary: bool,
        start_line: int,
        end_line: int,
        relative_file_path: str,
    ) -> str | None:
        warning: str | None = None
        if is_duplicate:
            warning = (
                f"WARNING: This chunk span ({start_line}-{end_line}) has been accessed before. "
                f"This may indicate file looping. Consider using rlm.search.query for more efficient access patterns."
            )
        if not has_canary:
            return warning

        canary_warning = (
            "SECURITY WARNING: Canary token detected in content. "
            "This may indicate a bypass of RLM MCP Gateway. "
            "Content should only be accessed through MCP tools with proper provenance."
        )
        warning = self._append_warning(warning, canary_warning)
        print(
            f"SECURITY ALERT: Canary token detected in chunk_get response for {relative_file_path}",
            file=sys.stderr,
        )
        return warning

    def _assemble_chunk_result(
        self,
        session: Session,
        chunk_id: str,
        relative_file_path: str,
        start_line: int,
        end_line: int,
        lines: list[str],
        max_bytes: int,
    ) -> dict[str, Any]:
        is_duplicate = session.has_accessed_span(relative_file_path, start_line, end_line)
        chunk_lines = lines[start_line - 1 : end_line]
        content = "".join(chunk_lines)
        content, content_bytes = self._truncate_content(content, max_bytes)

        provenance = self.provenance_tracker.create_chunk_provenance(
            relative_file_path, chunk_id, start_line, end_line, content
        )
        session.provenance.append(provenance)
        session.output_bytes += content_bytes
        session.tool_call_count += 1
        session.mark_span_accessed(relative_file_path, start_line, end_line)

        has_canary = check_canary_token(content, self.canary_token)
        warning = self._build_chunk_warning(
            is_duplicate=is_duplicate,
            has_canary=has_canary,
            start_line=start_line,
            end_line=end_line,
            relative_file_path=relative_file_path,
        )
        return self._format_chunk_result(
            chunk_id=chunk_id,
            relative_file_path=relative_file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            provenance_hash=provenance.content_hash or "",
            provenance=provenance.to_dict(),
            warning=warning,
        )

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
        session, file_path, context_error = self._resolve_chunk_create_context(
            session_id, file_handle
        )
        if context_error:
            return {"success": False, "error": context_error}
        if session is None or file_path is None:
            return {"success": False, "error": "Invalid chunk creation context"}

        params_error = self._validate_chunk_params(chunk_size, overlap, budget)
        if params_error:
            return {"success": False, "error": params_error}

        step, overlap_error = self._detect_chunk_overlap(chunk_size, overlap)
        if overlap_error:
            return {"success": False, "error": overlap_error}

        # Create chunks
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            chunk_ids = self._create_chunk_ids(
                lines=lines,
                file_handle=file_handle,
                chunk_size=chunk_size,
                overlap_step=step,
                budget=budget,
                strategy=strategy,
            )

            session.tool_call_count += 1
            return {"success": True, "chunk_ids": chunk_ids, "total_chunks": len(chunk_ids)}
        except Exception as e:
            return {"success": False, "error": f"Error creating chunks: {e}"}

    def chunk_get(
        self, session_id: str, chunk_id: str, max_bytes: int = MAX_CHUNK_BYTES
    ) -> dict[str, Any]:
        """Get a chunk by ID."""
        session, chunk_info, file_path, context_error = self._resolve_chunk_get_context(
            session_id, chunk_id
        )
        if context_error:
            return {"success": False, "error": context_error}
        if session is None or chunk_info is None or file_path is None:
            return {"success": False, "error": "Invalid chunk retrieval context"}

        # Read file to determine chunk boundaries
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start_line, end_line, metadata_error = self._reconstruct_metadata(
                chunk_info=chunk_info, total_lines=total_lines, chunk_id=chunk_id
            )
            if metadata_error:
                return {"success": False, "error": metadata_error}

            relative_file_path = str(file_path.relative_to(self.repo_root))
            return self._assemble_chunk_result(
                session=session,
                chunk_id=chunk_id,
                relative_file_path=relative_file_path,
                start_line=start_line,
                end_line=end_line,
                lines=lines,
                max_bytes=max_bytes,
            )
        except Exception as e:
            return {"success": False, "error": f"Error reading chunk: {e}"}
