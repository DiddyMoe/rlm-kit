"""Search tools for RLM MCP Gateway."""

import hashlib
import re
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.constants import MAX_SEARCH_RESULTS
from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.search_scorer import score_line_match
from rlm.mcp_gateway.validation import PathValidator


class SearchTools:
    """Search tools (references only)."""

    def __init__(
        self,
        session_manager: SessionManager,
        path_validator: PathValidator,
        repo_root: Path,
    ) -> None:
        """Initialize search tools.

        Args:
            session_manager: Session manager instance
            path_validator: Path validator instance
            repo_root: Repository root path
        """
        self.session_manager = session_manager
        self.path_validator = path_validator
        self.repo_root = repo_root

    def search_query(self, session_id: str, query: str, scope: str, k: int = 5) -> dict[str, Any]:
        """Semantic search returning span references only."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Validate scope
        valid, error = self.path_validator.validate_path(scope, session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        # Enforce k limit
        k = min(k, MAX_SEARCH_RESULTS)

        # R3 Compliance: Add depth and file count limits to prevent unbounded scanning
        max_search_depth = 5  # Limit recursive search depth
        max_files_scanned = 100  # Limit total files scanned
        files_scanned = 0

        # Simple text search (would be enhanced with proper indexing)
        scope_path = Path(scope)
        results: list[dict[str, Any]] = []

        try:
            for file_path in scope_path.rglob("*.py"):
                if self.path_validator.is_restricted_path(str(file_path)):
                    continue

                # R3 Compliance: Enforce file count limit
                files_scanned += 1
                if files_scanned > max_files_scanned:
                    break

                # R3 Compliance: Enforce depth limit
                depth = len(file_path.relative_to(scope_path).parts)
                if depth > max_search_depth:
                    continue

                if len(results) >= k:
                    break

                try:
                    with open(file_path, encoding="utf-8") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines, 1):
                            if query.lower() in line.lower():
                                # Calculate actual relevance score
                                relevance_score = score_line_match(query, line)
                                results.append(
                                    {
                                        "file_path": str(file_path.relative_to(self.repo_root)),
                                        "start_line": i,
                                        "end_line": i,
                                        "relevance_score": relevance_score,
                                        "snippet": line.strip()[
                                            :200
                                        ],  # Include snippet for better scoring
                                        "snippet_hash": hashlib.sha256(line.encode()).hexdigest()[
                                            :16
                                        ],
                                    }
                                )
                                if len(results) >= k:
                                    break
                except Exception:
                    continue
        except Exception as e:
            return {"success": False, "error": f"Error searching: {e}"}

        session.tool_call_count += 1
        return {"success": True, "results": results}

    def search_regex(
        self, session_id: str, pattern: str, scope: str, k: int = 10
    ) -> dict[str, Any]:
        """Regex search returning span references only."""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Validate scope
        valid, error = self.path_validator.validate_path(scope, session.allowed_roots)
        if not valid:
            return {"success": False, "error": error}

        # Enforce k limit
        k = min(k, MAX_SEARCH_RESULTS)

        # Regex search
        scope_path = Path(scope)
        results: list[dict[str, Any]] = []

        try:
            regex = re.compile(pattern)
            for file_path in scope_path.rglob("*.py"):
                if self.path_validator.is_restricted_path(str(file_path)):
                    continue

                if len(results) >= k:
                    break

                try:
                    with open(file_path, encoding="utf-8") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines, 1):
                            if regex.search(line):
                                # For regex matches, use a base score (regex is pattern-based, not semantic)
                                # Higher score for shorter matches (more specific)
                                match = regex.search(line)
                                match_length = len(match.group()) if match else len(line)
                                base_score = max(
                                    0.5, 1.0 - (match_length / 100.0)
                                )  # Shorter = higher score
                                results.append(
                                    {
                                        "file_path": str(file_path.relative_to(self.repo_root)),
                                        "start_line": i,
                                        "end_line": i,
                                        "relevance_score": base_score,
                                        "snippet": line.strip()[:200],
                                        "snippet_hash": hashlib.sha256(line.encode()).hexdigest()[
                                            :16
                                        ],
                                    }
                                )
                                if len(results) >= k:
                                    break
                except Exception:
                    continue
        except re.error as e:
            return {"success": False, "error": f"Invalid regex pattern: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Error searching: {e}"}

        # Sort regex results by relevance (shorter matches = more specific = higher score)
        results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

        session.tool_call_count += 1
        return {"success": True, "results": results}
