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

    def span_read(
        self,
        session_id: str,
        file_handle: str,
        start_line: int,
        end_line: int,
        max_bytes: int = MAX_SPAN_BYTES,
    ) -> dict[str, Any]:
        """Read a bounded span of a file."""
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

        # Enforce bounds
        if end_line - start_line > MAX_SPAN_LINES:
            return {
                "success": False,
                "error": f"Span too large: {end_line - start_line} > {MAX_SPAN_LINES} lines",
            }

        # Read span (optimized for local IDE: efficient file reading)
        try:
            relative_file_path = str(file_path.relative_to(self.repo_root))

            # R5 Compliance: Check for file looping (duplicate span access)
            is_duplicate = session.has_accessed_span(relative_file_path, start_line, end_line)

            # Optimize: Read file once, extract only needed lines
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()
                total_lines = len(lines)

                # Clamp to file bounds
                start_line = max(1, min(start_line, total_lines))
                end_line = max(start_line, min(end_line, total_lines))

                # Extract only the span lines (optimized slice)
                span_lines = lines[start_line - 1 : end_line]
                content = "".join(span_lines)

                # Enforce byte limit
                content_bytes = len(content.encode("utf-8"))
                if content_bytes > max_bytes:
                    # Truncate to byte limit
                    content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
                    content_bytes = len(content.encode("utf-8"))

                # Track provenance
                provenance = self.provenance_tracker.create_file_provenance(
                    relative_file_path, start_line, end_line, content
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
                    "start_line": start_line,
                    "end_line": end_line,
                    "total_lines": total_lines,
                    "hash": provenance.content_hash,
                    "provenance": provenance.to_dict(),
                    "warning": None,  # Will be set if duplicate or canary detected
                }

                # Warn on duplicate access (R5: file looping prevention)
                if is_duplicate:
                    response["warning"] = (
                        f"WARNING: This span ({start_line}-{end_line}) has been accessed before. "
                        f"This may indicate file looping. Consider using rlm.search.query or rlm.chunk.get "
                        f"for more efficient access patterns."
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
                        f"SECURITY ALERT: Canary token detected in span_read response for {relative_file_path}",
                        file=sys.stderr,
                    )

                return response
        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}
