"""Provenance reporting tools for RLM MCP Gateway."""

from typing import Any

from rlm.mcp_gateway.session import SessionManager


class ProvenanceTools:
    """Provenance reporting tools."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize provenance tools.

        Args:
            session_manager: Session manager instance
        """
        self.session_manager = session_manager

    def provenance_report(self, session_id: str, export_json: bool = False) -> dict[str, Any]:
        """Get complete provenance graph for a session.

        Args:
            session_id: Session ID.
            export_json: If True, include "export_payload" with a JSON string
                suitable for writing to a file (audit/SIEM).
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Calculate file access statistics (R5: deterministic progress tracking)
        file_access_stats: dict[str, dict[str, Any]] = {}
        for file_path, spans in session.accessed_spans.items():
            file_access_stats[file_path] = {
                "unique_spans_accessed": len(spans),
                "spans": sorted(list(spans)),  # Sorted for deterministic output
            }

        provenance_graph = {
            "spans": [p.to_dict() for p in session.provenance if p.file_path],
            "session_id": session_id,
            "tool_calls": session.tool_call_count,
            "output_bytes": session.output_bytes,
            "file_access_stats": file_access_stats,
        }
        out: dict[str, Any] = {
            "success": True,
            "label": "DATA",
            "provenance_graph": provenance_graph,
        }
        if export_json:
            import json

            out["export_payload"] = json.dumps({"provenance_graph": provenance_graph}, indent=2)
        return out
