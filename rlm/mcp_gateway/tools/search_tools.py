"""Search tools for RLM MCP Gateway."""

import fnmatch
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

    def _matches_patterns(self, file_path: Path, scope_path: Path, patterns: list[str]) -> bool:
        relative_path = str(file_path.relative_to(scope_path))
        file_name = file_path.name
        return any(
            fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(file_name, pattern)
            for pattern in patterns
        )

    def _compile_regex(self, pattern: str) -> tuple[re.Pattern[str] | None, str | None]:
        try:
            return re.compile(pattern), None
        except re.error as e:
            return None, f"Invalid regex pattern: {e}"

    def _compute_regex_score(self, line: str, match: re.Match[str] | None) -> float:
        match_length = len(match.group()) if match else len(line)
        return max(0.5, 1.0 - (match_length / 100.0))

    def _format_regex_match(
        self, file_path: Path, line: str, line_number: int, relevance_score: float
    ) -> dict[str, Any]:
        return {
            "file_path": str(file_path.relative_to(self.repo_root)),
            "start_line": line_number,
            "end_line": line_number,
            "relevance_score": relevance_score,
            "snippet": line.strip()[:200],
            "snippet_hash": hashlib.sha256(line.encode()).hexdigest()[:16],
        }

    def _prepare_search_request(
        self, session_id: str, scope: str, k: int
    ) -> tuple[Any | None, Path | None, int, str | None]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None, None, k, "Session not found"

        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return None, None, k, error

        valid, error = self.path_validator.validate_path(scope, session.allowed_roots)
        if not valid:
            return None, None, k, error

        return session, Path(scope), min(k, MAX_SEARCH_RESULTS), None

    def _iter_files(
        self,
        scope_path: Path,
        include_patterns: list[str] | None,
        max_depth: int,
        max_files_scanned: int,
    ) -> list[Path]:
        """Return bounded candidate files under scope_path using include patterns."""
        patterns = include_patterns or ["*.py"]
        normalized_patterns = [pattern.strip() for pattern in patterns if pattern.strip()]
        if not normalized_patterns:
            normalized_patterns = ["*.py"]

        candidates: list[Path] = []
        for file_path in scope_path.rglob("*"):
            if not self._is_valid_candidate(file_path, scope_path, max_depth, normalized_patterns):
                continue

            candidates.append(file_path)
            if len(candidates) >= max_files_scanned:
                break

        return candidates

    def _is_valid_candidate(
        self, file_path: Path, scope_path: Path, max_depth: int, patterns: list[str]
    ) -> bool:
        if not file_path.is_file():
            return False
        if self.path_validator.is_restricted_path(str(file_path)):
            return False

        depth = len(file_path.relative_to(scope_path).parts)
        if depth > max_depth:
            return False

        return self._matches_patterns(file_path, scope_path, patterns)

    def _collect_regex_matches_for_file(
        self, file_path: Path, regex: re.Pattern[str], k: int, current_count: int
    ) -> list[dict[str, Any]]:
        file_results: list[dict[str, Any]] = []
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                match = regex.search(line)
                if not match:
                    continue

                base_score = self._compute_regex_score(line, match)
                file_results.append(
                    self._format_regex_match(
                        file_path=file_path,
                        line=line,
                        line_number=i,
                        relevance_score=base_score,
                    )
                )
                if current_count + len(file_results) >= k:
                    break

        return file_results

    def _search_regex_files(
        self,
        scope_path: Path,
        include_patterns: list[str] | None,
        max_depth: int,
        max_files_scanned: int,
        regex: re.Pattern[str],
        k: int,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for file_path in self._iter_files(
            scope_path=scope_path,
            include_patterns=include_patterns,
            max_depth=max_depth,
            max_files_scanned=max_files_scanned,
        ):
            if len(results) >= k:
                break

            try:
                results.extend(
                    self._collect_regex_matches_for_file(
                        file_path=file_path,
                        regex=regex,
                        k=k,
                        current_count=len(results),
                    )
                )
            except Exception:
                continue

        return results

    def _format_query_match(
        self, file_path: Path, line: str, line_number: int, relevance_score: float
    ) -> dict[str, Any]:
        return {
            "file_path": str(file_path.relative_to(self.repo_root)),
            "start_line": line_number,
            "end_line": line_number,
            "relevance_score": relevance_score,
            "snippet": line.strip()[:200],
            "snippet_hash": hashlib.sha256(line.encode()).hexdigest()[:16],
        }

    def _collect_query_matches_for_file(
        self, file_path: Path, query: str, k: int, current_count: int
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        query_lower = query.lower()
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
            for line_number, line in enumerate(lines, 1):
                if query_lower not in line.lower():
                    continue

                relevance_score = score_line_match(query, line)
                matches.append(
                    self._format_query_match(file_path, line, line_number, relevance_score)
                )
                if current_count + len(matches) >= k:
                    break

        return matches

    def _search_query_files(
        self,
        scope_path: Path,
        include_patterns: list[str] | None,
        max_depth: int,
        max_files_scanned: int,
        query: str,
        k: int,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for file_path in self._iter_files(
            scope_path=scope_path,
            include_patterns=include_patterns,
            max_depth=max_depth,
            max_files_scanned=max_files_scanned,
        ):
            if len(results) >= k:
                break

            try:
                results.extend(
                    self._collect_query_matches_for_file(
                        file_path=file_path,
                        query=query,
                        k=k,
                        current_count=len(results),
                    )
                )
            except Exception:
                continue

        return results

    def _rank_results(self, results: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
        ranked = sorted(results, key=lambda item: item.get("relevance_score", 0.0), reverse=True)
        return ranked[:k]

    def search_query(
        self,
        session_id: str,
        query: str,
        scope: str,
        k: int = 5,
        include_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Semantic search returning span references only."""
        session, scope_path, k, error = self._prepare_search_request(session_id, scope, k)
        if error:
            return {"success": False, "error": error}

        assert session is not None
        assert scope_path is not None

        max_search_depth = 5
        max_files_scanned = 100

        try:
            results = self._search_query_files(
                scope_path=scope_path,
                include_patterns=include_patterns,
                max_depth=max_search_depth,
                max_files_scanned=max_files_scanned,
                query=query,
                k=k,
            )
        except Exception as e:
            return {"success": False, "error": f"Error searching: {e}"}

        session.tool_call_count += 1
        return {"success": True, "results": self._rank_results(results, k)}

    def search_regex(
        self,
        session_id: str,
        pattern: str,
        scope: str,
        k: int = 10,
        include_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Regex search returning span references only."""
        session, scope_path, k, error = self._prepare_search_request(session_id, scope, k)
        if error:
            return {"success": False, "error": error}

        assert session is not None
        assert scope_path is not None

        # Regex search
        results: list[dict[str, Any]] = []
        max_search_depth = 5
        max_files_scanned = 100

        regex, regex_error = self._compile_regex(pattern)
        if regex_error:
            return {"success": False, "error": regex_error}

        assert regex is not None
        try:
            results = self._search_regex_files(
                scope_path=scope_path,
                include_patterns=include_patterns,
                max_depth=max_search_depth,
                max_files_scanned=max_files_scanned,
                regex=regex,
                k=k,
            )
        except Exception as e:
            return {"success": False, "error": f"Error searching: {e}"}

        # Sort regex results by relevance (shorter matches = more specific = higher score)
        results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

        session.tool_call_count += 1
        return {"success": True, "results": results}
