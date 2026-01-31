"""Provenance tracking for RLM MCP Gateway."""

import hashlib

from rlm.core.types import SnippetProvenance


class ProvenanceTracker:
    """Tracks provenance for all operations."""

    @staticmethod
    def create_file_provenance(
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        content: str | None = None,
    ) -> SnippetProvenance:
        """Create provenance for a file span."""
        content_hash = None
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return SnippetProvenance(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content_hash=content_hash,
            source_type="file",
        )

    @staticmethod
    def create_chunk_provenance(
        file_path: str, chunk_id: str, start_line: int, end_line: int, content: str
    ) -> SnippetProvenance:
        """Create provenance for a chunk."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return SnippetProvenance(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content_hash=content_hash,
            source_type="chunk",
        )
