"""Tests for MCP gateway session span access tracking."""

from rlm.mcp_gateway.session import SessionManager


class TestSessionSpanTracking:
    def test_mark_and_detect_accessed_span(self) -> None:
        manager = SessionManager()
        session = manager.create_session()

        assert session.has_accessed_span("a.py", 1, 10) is False

        session.mark_span_accessed("a.py", 1, 10)

        assert session.has_accessed_span("a.py", 1, 10) is True

    def test_duplicate_span_count(self) -> None:
        manager = SessionManager()
        session = manager.create_session()

        assert session.get_duplicate_span_count("b.py", 3, 7) == 0

        session.mark_span_accessed("b.py", 3, 7)

        assert session.get_duplicate_span_count("b.py", 3, 7) == 1
        assert session.get_duplicate_span_count("b.py", 4, 8) == 0
