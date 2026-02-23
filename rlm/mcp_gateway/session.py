"""Session management for RLM MCP Gateway."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from rlm.core.types import SnippetProvenance
from rlm.mcp_gateway.constants import MAX_SESSION_OUTPUT_BYTES


def _default_provenance() -> list[SnippetProvenance]:
    return []


def _default_accessed_spans() -> dict[str, set[tuple[int, int]]]:
    return {}


@dataclass
class SessionConfig:
    """Configuration for an RLM session."""

    max_depth: int = 10
    max_iterations: int = 30
    max_tool_calls: int = 100
    timeout_ms: int = 300000  # 5 minutes
    max_output_bytes: int = MAX_SESSION_OUTPUT_BYTES


@dataclass
class Session:
    """Represents an active RLM session."""

    session_id: str
    config: SessionConfig
    allowed_roots: list[str]
    created_at: float
    tool_call_count: int = 0
    output_bytes: int = 0
    provenance: list[SnippetProvenance] = field(default_factory=_default_provenance)
    accessed_spans: dict[str, set[tuple[int, int]]] = field(default_factory=_default_accessed_spans)

    def has_accessed_span(self, file_path: str, start_line: int, end_line: int) -> bool:
        """Check if a span has been accessed before."""
        if file_path not in self.accessed_spans:
            return False
        span_tuple = (start_line, end_line)
        return span_tuple in self.accessed_spans[file_path]

    def mark_span_accessed(self, file_path: str, start_line: int, end_line: int) -> None:
        """Mark a span as accessed."""
        if file_path not in self.accessed_spans:
            self.accessed_spans[file_path] = set()
        self.accessed_spans[file_path].add((start_line, end_line))

    def get_duplicate_span_count(self, file_path: str, start_line: int, end_line: int) -> int:
        """Get count of how many times this exact span has been accessed."""
        if file_path not in self.accessed_spans:
            return 0
        span_tuple = (start_line, end_line)
        return 1 if span_tuple in self.accessed_spans[file_path] else 0


class SessionManager:
    """Manages RLM sessions with caching and automatic cleanup.

    Optimized for local IDE integration:
    - Fast session lookup with dict caching
    - Automatic cleanup of expired sessions
    - Efficient budget checking
    """

    def __init__(self) -> None:
        """Initialize session manager."""
        self._sessions: dict[str, Session] = {}
        self._last_cleanup: float = time.time()
        self._cleanup_interval: float = 60.0  # Cleanup every 60 seconds

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions to prevent memory leaks.

        Optimized for local IDE: periodic cleanup with minimal overhead.
        """
        current_time = time.time()
        # Only cleanup periodically to avoid overhead on every call
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = current_time
        expired_sessions: list[str] = []

        for session_id, session in self._sessions.items():
            elapsed_ms = (current_time - session.created_at) * 1000
            if elapsed_ms >= session.config.timeout_ms:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self._sessions[session_id]

    def create_session(self, config: dict[str, Any] | None = None) -> Session:
        """Create a new session."""
        self._cleanup_expired_sessions()
        session_id = str(uuid.uuid4())
        session_config = SessionConfig(**(config or {}))
        session = Session(
            session_id=session_id,
            config=session_config,
            allowed_roots=[],
            created_at=time.time(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID with cached lookup.

        Optimized for local IDE: O(1) dict lookup with periodic cleanup.
        """
        # Periodic cleanup (non-blocking, minimal overhead)
        if time.time() - self._last_cleanup >= self._cleanup_interval:
            self._cleanup_expired_sessions()
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_session_ids(self, prefix: str = "") -> list[str]:
        """List active session IDs, optionally filtered by prefix."""
        self._cleanup_expired_sessions()
        if not prefix:
            return sorted(self._sessions.keys())
        return sorted(session_id for session_id in self._sessions if session_id.startswith(prefix))

    def check_budget(self, session: Session) -> tuple[bool, str | None]:
        """Check if session is within budget.

        Optimized for local IDE: fast budget checks with early returns.
        """
        if session.tool_call_count >= session.config.max_tool_calls:
            return (
                False,
                f"Tool call budget exceeded: {session.tool_call_count} >= {session.config.max_tool_calls}",
            )

        if session.output_bytes >= session.config.max_output_bytes:
            return (
                False,
                f"Output budget exceeded: {session.output_bytes} >= {session.config.max_output_bytes}",
            )

        elapsed_ms = (time.time() - session.created_at) * 1000
        if elapsed_ms >= session.config.timeout_ms:
            return False, f"Timeout exceeded: {elapsed_ms}ms >= {session.config.timeout_ms}ms"

        return True, None
