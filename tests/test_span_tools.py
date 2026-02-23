from __future__ import annotations

from pathlib import Path

from rlm.mcp_gateway.handles import HandleManager
from rlm.mcp_gateway.provenance import ProvenanceTracker
from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.span_tools import SpanTools
from rlm.mcp_gateway.validation import PathValidator


def _build_span_tools(repo_root: Path) -> SpanTools:
    return SpanTools(
        session_manager=SessionManager(),
        handle_manager=HandleManager(),
        path_validator=PathValidator(),
        provenance_tracker=ProvenanceTracker(),
        repo_root=repo_root,
        canary_token=None,
    )


class TestSpanTools:
    def test_span_read_returns_content_for_valid_range(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.txt"
        file_path.write_text("a\nb\nc\n", encoding="utf-8")

        tools = _build_span_tools(tmp_path)
        session = tools.session_manager.create_session()
        session.allowed_roots = [str(tmp_path)]
        handle = tools.handle_manager.create_file_handle(str(file_path), session.session_id)

        result = tools.span_read(session.session_id, handle, 2, 3)

        assert result["success"] is True
        assert result["content"] == "b\nc\n"
        assert result["start_line"] == 2
        assert result["end_line"] == 3

    def test_span_read_clamps_line_range_to_file_bounds(self, tmp_path: Path) -> None:
        file_path = tmp_path / "bounds.txt"
        file_path.write_text("line1\nline2\n", encoding="utf-8")

        tools = _build_span_tools(tmp_path)
        session = tools.session_manager.create_session()
        session.allowed_roots = [str(tmp_path)]
        handle = tools.handle_manager.create_file_handle(str(file_path), session.session_id)

        result = tools.span_read(session.session_id, handle, -10, 50)

        assert result["success"] is True
        assert result["start_line"] == 1
        assert result["end_line"] == 2
        assert result["content"] == "line1\nline2\n"

    def test_span_read_returns_error_for_invalid_session(self, tmp_path: Path) -> None:
        file_path = tmp_path / "x.txt"
        file_path.write_text("x\n", encoding="utf-8")

        tools = _build_span_tools(tmp_path)
        fake_handle = tools.handle_manager.create_file_handle(str(file_path), "fake")

        result = tools.span_read("missing-session", fake_handle, 1, 1)

        assert result["success"] is False
        assert "Session not found" in result["error"]

    def test_span_read_rejects_path_traversal_attempt(self, tmp_path: Path) -> None:
        tools = _build_span_tools(tmp_path)
        session = tools.session_manager.create_session()
        session.allowed_roots = [str(tmp_path)]

        handle = tools.handle_manager.create_file_handle("../secret.txt", session.session_id)
        result = tools.span_read(session.session_id, handle, 1, 1)

        assert result["success"] is False
        assert "Path traversal detected" in result["error"]

    def test_build_span_response_has_expected_metadata(self, tmp_path: Path) -> None:
        file_path = tmp_path / "meta.txt"
        file_path.write_text("row1\nrow2\n", encoding="utf-8")

        tools = _build_span_tools(tmp_path)
        session = tools.session_manager.create_session()
        session.allowed_roots = [str(tmp_path)]
        handle = tools.handle_manager.create_file_handle(str(file_path), session.session_id)

        result = tools.span_read(session.session_id, handle, 1, 2)

        assert result["success"] is True
        assert "metadata" in result
        metadata = result["metadata"]
        assert metadata["line_count"] == 2
        assert metadata["byte_count"] == len(result["content"].encode("utf-8"))
        assert metadata["is_truncated"] is False

    def test_span_read_respects_max_bytes_truncation(self, tmp_path: Path) -> None:
        file_path = tmp_path / "truncate.txt"
        file_path.write_text("12345\n67890\n", encoding="utf-8")

        tools = _build_span_tools(tmp_path)
        session = tools.session_manager.create_session()
        session.allowed_roots = [str(tmp_path)]
        handle = tools.handle_manager.create_file_handle(str(file_path), session.session_id)

        result = tools.span_read(session.session_id, handle, 1, 2, max_bytes=4)

        assert result["success"] is True
        assert len(result["content"].encode("utf-8")) <= 4
        assert result["metadata"]["is_truncated"] is True
