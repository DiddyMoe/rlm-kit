"""Bounded span reading tools for RLM MCP Gateway."""

import sys
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.constants import MAX_SPAN_BYTES, MAX_SPAN_LINES
from rlm.mcp_gateway.handles import HandleManager
from rlm.mcp_gateway.provenance import ProvenanceTracker
from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.helpers import check_canary_token
from rlm.mcp_gateway.validation import PathValidator


class SpanTools:
    """Bounded span reading tools."""

    def __init__(
        self,
        session_manager: SessionManager,
        handle_manager: HandleManager,
        path_validator: PathValidator,
        provenance_tracker: ProvenanceTracker,
        repo_root: Path,
        canary_token: str | None,
    ) -> None:
        """Initialize span tools.

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

    def _resolve_span_read_request(
        self, session_id: str, file_handle: str
    ) -> tuple[Any | None, Path | None, str | None]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None, None, "Session not found"

        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return None, None, error

        handle_info = self.handle_manager.get_file_handle(file_handle)
        if not handle_info:
            return None, None, "Invalid file handle"

        file_path = Path(handle_info["file_path"])

        valid, error = self.path_validator.validate_path(str(file_path), session.allowed_roots)
        if not valid:
            return None, None, error

        if not file_path.exists() or not file_path.is_file():
            return None, None, f"File not found: {file_path}"

        return session, file_path, None

    def _clamp_span_to_file_bounds(
        self, lines: list[str], start_line: int, end_line: int
    ) -> tuple[int, int, int]:
        total_lines = len(lines)
        bounded_start = max(1, min(start_line, total_lines))
        bounded_end = max(bounded_start, min(end_line, total_lines))
        return bounded_start, bounded_end, total_lines

    def _read_span_content(
        self, file_path: Path, start_line: int, end_line: int, max_bytes: int
    ) -> tuple[str, int, int, int, int, int, bool]:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        bounded_start, bounded_end, total_lines = self._clamp_span_to_file_bounds(
            lines, start_line, end_line
        )
        span_lines = lines[bounded_start - 1 : bounded_end]
        line_count = len(span_lines)
        content = "".join(span_lines)
        content_bytes = len(content.encode("utf-8"))
        is_truncated = False

        if content_bytes > max_bytes:
            content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
            content_bytes = len(content.encode("utf-8"))
            is_truncated = True

        return (
            content,
            bounded_start,
            bounded_end,
            total_lines,
            line_count,
            content_bytes,
            is_truncated,
        )

    def _build_span_warning(
        self, is_duplicate: bool, has_canary: bool, start_line: int, end_line: int
    ) -> str | None:
        warning_parts: list[str] = []
        if is_duplicate:
            warning_parts.append(
                f"WARNING: This span ({start_line}-{end_line}) has been accessed before. "
                f"This may indicate file looping. Consider using rlm.search.query or rlm.chunk.get "
                f"for more efficient access patterns."
            )

        if has_canary:
            warning_parts.append(
                "SECURITY WARNING: Canary token detected in content. "
                "This may indicate a bypass of RLM MCP Gateway. "
                "Content should only be accessed through MCP tools with proper provenance."
            )

        if not warning_parts:
            return None

        return "\n".join(warning_parts)

    def _build_span_response(
        self,
        content: str,
        start_line: int,
        end_line: int,
        total_lines: int,
        line_count: int,
        byte_count: int,
        is_truncated: bool,
        provenance: Any,
        warning: str | None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "label": "DATA",
            "content": content,
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": total_lines,
            "hash": provenance.content_hash,
            "provenance": provenance.to_dict(),
            "metadata": {
                "line_count": line_count,
                "byte_count": byte_count,
                "is_truncated": is_truncated,
            },
            "warning": warning,
        }

    def span_read(
        self,
        session_id: str,
        file_handle: str,
        start_line: int,
        end_line: int,
        max_bytes: int = MAX_SPAN_BYTES,
    ) -> dict[str, Any]:
        """Read a bounded span of a file."""
        session, file_path, error = self._resolve_span_read_request(session_id, file_handle)
        if error:
            return {"success": False, "error": error}

        assert session is not None
        assert file_path is not None

        # Enforce bounds
        if end_line - start_line > MAX_SPAN_LINES:
            return {
                "success": False,
                "error": f"Span too large: {end_line - start_line} > {MAX_SPAN_LINES} lines",
            }

        return self._execute_span_read(
            session=session,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            max_bytes=max_bytes,
        )

    def _execute_span_read(
        self,
        session: Any,
        file_path: Path,
        start_line: int,
        end_line: int,
        max_bytes: int,
    ) -> dict[str, Any]:
        try:
            relative_file_path = str(file_path.relative_to(self.repo_root))
            is_duplicate = session.has_accessed_span(relative_file_path, start_line, end_line)

            (
                content,
                start_line,
                end_line,
                total_lines,
                line_count,
                content_bytes,
                is_truncated,
            ) = self._read_span_content(file_path, start_line, end_line, max_bytes)

            provenance = self.provenance_tracker.create_file_provenance(
                relative_file_path, start_line, end_line, content
            )
            session.provenance.append(provenance)
            session.output_bytes += content_bytes
            session.tool_call_count += 1
            session.mark_span_accessed(relative_file_path, start_line, end_line)

            has_canary = check_canary_token(content, self.canary_token)
            warning = self._build_span_warning(is_duplicate, has_canary, start_line, end_line)
            if has_canary:
                print(
                    f"SECURITY ALERT: Canary token detected in span_read response for {relative_file_path}",
                    file=sys.stderr,
                )

            return self._build_span_response(
                content=content,
                start_line=start_line,
                end_line=end_line,
                total_lines=total_lines,
                line_count=line_count,
                byte_count=content_bytes,
                is_truncated=is_truncated,
                provenance=provenance,
                warning=warning,
            )
        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}
