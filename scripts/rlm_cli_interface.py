#!/usr/bin/env python3
"""
RLM-Enforced CLI Interface for Repository Access

This CLI acts as the sole mediator between AI agents and the repository.
All interactions must go through this interface, ensuring:

1. RLM Architecture Enforcement: All AI interactions use proper RLM
2. Controlled Access: Only audited operations are permitted
3. Security Boundary: No direct repository access by AI agents
4. Audit Trail: All operations are logged and traceable

Based on "Recursive Language Models" (arXiv:2512.24601) - ensuring AI agents
can only access repository context through controlled, recursive mechanisms.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Bootstrap: repo root on path so path_utils and rlm are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
import hashlib

from path_utils import REPO_ROOT  # noqa: E402
from rlm import RLMEnforcementError
from rlm.core.rlm_enforcement import RLMContext
from rlm.core.types import SnippetProvenance
from rlm.logger import RLMLogger


class RepositoryAccessError(Exception):
    """Raised when repository access violates security policies."""

    pass


class RLMCLIInterface:
    """
    Secure CLI interface that mediates all AI agent interactions with the repository.

    This interface ensures that:
    - All operations require proper RLM context
    - Only audited operations are permitted
    - No direct file access is allowed
    - All interactions are logged
    """

    def __init__(self):
        self.logger = RLMLogger(log_dir="./logs", file_name="cli_interface")
        self.allowed_operations = {
            "search_code": self._search_code,
            "read_file": self._read_file,
            "read_span": self._read_span,  # New: bounded span reading
            "list_directory": self._list_directory,
            "run_analysis": self._run_analysis,
            "get_structure": self._get_structure,
            "execute_safe_code": self._execute_safe_code,
        }

    def validate_rlm_context(self) -> None:
        """
        Validate that this operation is occurring within proper RLM context.

        This is the critical security check that ensures all AI agent interactions
        go through the RLM architecture as mandated by the academic paper.

        Allowed contexts:
        - RLM agents (programmatic use)
        - MCP server (for built-in AI chat integration)
        """
        current_context = RLMContext.get_current_context()

        # Allow MCP server context (for built-in AI chat integration)
        if current_context == "mcp_server":
            return

        # Allow programmatic RLM agent contexts
        if current_context and current_context.startswith(("rlm_agent", "test")):
            return

        # Block all other direct access
        if not RLMContext.is_in_rlm_context():
            raise RLMEnforcementError(
                "🚫 SECURITY VIOLATION: Direct CLI access forbidden outside RLM context.\n\n"
                "ACADEMIC PAPER REQUIREMENT: All AI agent interactions must use RLM architecture "
                "(https://arxiv.org/abs/2512.24601) to ensure proper recursive reasoning and context handling.\n\n"
                "SOLUTION: Use AgentRLM for all repository interactions:\n"
                "```python\n"
                "from rlm import create_enforced_agent\n"
                "agent = create_enforced_agent(backend='openai')\n"
                "# Use CLI through agent.chat() with tool integration\n"
                "```\n\n"
                "For built-in AI chat: Use the RLM MCP server integration."
            )

    def execute_operation(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a controlled repository operation.

        All operations validate RLM context and are audited.
        """
        self.validate_rlm_context()

        if operation not in self.allowed_operations:
            raise RepositoryAccessError(f"Operation '{operation}' is not permitted")

        # Log the operation
        self.logger.log_operation(
            {
                "operation": operation,
                "params": params,
                "timestamp": RLMLogger.get_timestamp(),
                "rlm_context": RLMContext.get_current_context(),
            }
        )

        try:
            result = self.allowed_operations[operation](**params)
            return {"success": True, "operation": operation, "result": result}
        except Exception as e:
            return {
                "success": False,
                "operation": operation,
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def _search_code(
        self, query: str, file_pattern: str = "*.py", max_results: int = 10
    ) -> list[dict[str, str]]:
        """Search code using controlled patterns."""

        results = []
        repo_root = REPO_ROOT

        # Only allow safe file patterns
        safe_patterns = ["*.py", "*.md", "*.txt", "*.json", "*.yaml", "*.yml"]
        if file_pattern not in safe_patterns:
            raise RepositoryAccessError(f"File pattern '{file_pattern}' not permitted")

        for file_path in repo_root.rglob(file_pattern):
            if file_path.is_file() and not self._is_restricted_path(file_path):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # Simple text search (could be enhanced with proper indexing)
                    if query.lower() in content.lower():
                        # Find context around matches
                        lines = content.split("\n")
                        for i, line in enumerate(lines):
                            if query.lower() in line.lower():
                                start = max(0, i - 2)
                                end = min(len(lines), i + 3)
                                context = "\n".join(lines[start:end])
                                results.append(
                                    {
                                        "file": str(file_path.relative_to(repo_root)),
                                        "line": i + 1,
                                        "context": context,
                                    }
                                )
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue

        return results

    def _read_file(
        self,
        file_path: str,
        max_lines: int = 50,
        start_line: int | None = None,
        end_line: int | None = None,
        max_bytes: int = 8192,
    ) -> dict[str, Any]:
        """Read file contents with bounded span restrictions.

        This implements RLM semantics: only read bounded spans, never entire files.
        """
        repo_root = REPO_ROOT
        full_path = (repo_root / file_path).resolve()

        # Security checks
        if not full_path.is_relative_to(repo_root):
            raise RepositoryAccessError("Access outside repository not permitted")

        if self._is_restricted_path(full_path):
            raise RepositoryAccessError(f"Access to '{file_path}' is restricted")

        if not full_path.exists() or not full_path.is_file():
            raise RepositoryAccessError(f"File '{file_path}' not found or not accessible")

        try:
            # Read all lines (we need to know total for bounds checking)
            with open(full_path, encoding="utf-8") as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)

            # Determine span bounds
            if start_line is not None and end_line is not None:
                # Bounded span reading (RLM semantics)
                start_line = max(1, min(start_line, total_lines))
                end_line = max(start_line, min(end_line, total_lines))

                # Enforce max span size
                if end_line - start_line > 200:  # MAX_SPAN_LINES
                    raise RepositoryAccessError(
                        f"Span too large: {end_line - start_line} lines > 200 lines maximum"
                    )

                span_lines = all_lines[start_line - 1 : end_line]
                content = "".join(span_lines)
                content_bytes = len(content.encode("utf-8"))
                if content_bytes > max_bytes:
                    content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
                    content_bytes = len(content.encode("utf-8"))
                content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
                provenance = SnippetProvenance(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    content_hash=content_hash,
                    source_type="file",
                )
                return {
                    "path": file_path,
                    "total_lines": total_lines,
                    "content": content,
                    "start_line": start_line,
                    "end_line": end_line,
                    "truncated": content_bytes >= max_bytes,
                    "span_size_bytes": content_bytes,
                    "provenance": provenance.to_dict(),
                }
            # Legacy mode: read from start with max_lines limit
            start_line = 1
            effective_max = 50 if max_lines is None else max_lines
            end_line = min(effective_max, total_lines)
            span_lines = all_lines[start_line - 1 : end_line]
            content = "".join(span_lines)
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > max_bytes:
                content = content.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
                content_bytes = len(content.encode("utf-8"))
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            provenance = SnippetProvenance(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content_hash=content_hash,
                source_type="file",
            )
            return {
                "path": file_path,
                "total_lines": total_lines,
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "truncated": len(all_lines) > effective_max or content_bytes >= max_bytes,
                "span_size_bytes": content_bytes,
                "provenance": provenance.to_dict(),
            }
        except Exception as e:
            raise RepositoryAccessError(f"Error reading file: {e}") from e

    def _read_span(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        max_bytes: int = 8192,
    ) -> dict[str, Any]:
        """Read a bounded span of a file (RLM semantics).

        This is the preferred method for reading file content, as it enforces
        RLM semantics: only read bounded spans, never entire files.
        """
        return self._read_file(
            file_path=file_path,
            max_lines=None,  # Not used in span mode
            start_line=start_line,
            end_line=end_line,
            max_bytes=max_bytes,
        )

    def _list_directory(self, dir_path: str = ".", max_depth: int = 2) -> dict[str, Any]:
        """List directory contents with restrictions."""
        repo_root = REPO_ROOT
        full_path = (repo_root / dir_path).resolve()

        if not full_path.is_relative_to(repo_root):
            raise RepositoryAccessError("Access outside repository not permitted")

        if self._is_restricted_path(full_path):
            raise RepositoryAccessError(f"Access to '{dir_path}' is restricted")

        def list_recursive(path: Path, current_depth: int = 0) -> dict[str, Any]:
            if current_depth > max_depth:
                return {"type": "directory", "truncated": True}

            try:
                items = []
                for item in sorted(path.iterdir()):
                    if self._is_restricted_path(item):
                        continue

                    if item.is_file():
                        items.append(
                            {"name": item.name, "type": "file", "size": item.stat().st_size}
                        )
                    elif item.is_dir() and current_depth < max_depth:
                        items.append(
                            {
                                "name": item.name,
                                "type": "directory",
                                "contents": list_recursive(item, current_depth + 1),
                            }
                        )

                return {"type": "directory", "contents": items}
            except Exception:
                return {"type": "directory", "error": "Access denied"}

        return list_recursive(full_path)

    def _run_analysis(self, analysis_type: str, target: str) -> dict[str, Any]:
        """Run controlled analysis operations."""
        allowed_analyses = {
            "file_stats": self._analyze_file_stats,
            "import_deps": self._analyze_imports,
            "code_structure": self._analyze_code_structure,
        }

        if analysis_type not in allowed_analyses:
            raise RepositoryAccessError(f"Analysis type '{analysis_type}' not permitted")

        return allowed_analyses[analysis_type](target)

    def _get_structure(self) -> dict[str, Any]:
        """Get repository structure overview."""
        return self._list_directory(".", max_depth=3)

    def _execute_safe_code(self, code: str) -> dict[str, Any]:
        """Execute code in controlled environment (highly restricted)."""
        # This would be extremely limited - probably just basic calculations
        # or analysis operations that don't access the filesystem

        # For now, just reject all direct code execution
        raise RepositoryAccessError(
            "Direct code execution not permitted through CLI interface. "
            "Use RLM's controlled execution environments instead."
        )

    def _is_restricted_path(self, path: Path) -> bool:
        """Check if a path is restricted from access."""
        restricted_patterns = [
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "node_modules",
            ".pytest_cache",
            "*.pyc",
            ".env*",
            "logs",
            "secrets",
            "credentials",
        ]

        path_str = str(path)
        for pattern in restricted_patterns:
            if pattern in path_str or path_str.endswith(pattern):
                return True

        return False

    def _analyze_file_stats(self, file_path: str) -> dict[str, Any]:
        """Analyze basic file statistics."""
        result = self._read_file(file_path, max_lines=1000)
        content = result["content"]

        return {
            "path": file_path,
            "lines": result["total_lines"],
            "characters": len(content),
            "functions": content.count("def "),
            "classes": content.count("class "),
            "imports": content.count("import ") + content.count("from "),
        }

    def _analyze_imports(self, file_path: str) -> dict[str, Any]:
        """Analyze import dependencies."""
        result = self._read_file(file_path, max_lines=1000)
        content = result["content"]

        imports = []
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                imports.append(line)

        return {
            "path": file_path,
            "imports": imports,
            "total_imports": len(imports),
        }

    def _analyze_code_structure(self, file_path: str) -> dict[str, Any]:
        """Analyze code structure."""
        from rlm.utils.parsing import find_code_blocks

        result = self._read_file(file_path, max_lines=1000)
        content = result["content"]

        code_blocks = find_code_blocks(content)

        return {
            "path": file_path,
            "code_blocks": len(code_blocks),
            "functions": content.count("def "),
            "classes": content.count("class "),
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RLM-Enforced CLI Interface for Secure Repository Access",
        epilog="""
This CLI acts as the sole mediator between AI agents and the repository.
All interactions must occur through proper RLM architecture.

Academic Paper: https://arxiv.org/abs/2512.24601
        """,
    )

    parser.add_argument(
        "operation",
        choices=[
            "search_code",
            "read_file",
            "read_span",  # New: bounded span reading
            "list_directory",
            "run_analysis",
            "get_structure",
            "execute_safe_code",
        ],
        help="Operation to perform",
    )

    parser.add_argument("--params", type=json.loads, default={}, help="Parameters as JSON string")

    parser.add_argument("--rlm-context", type=str, help="RLM context identifier (for validation)")

    args = parser.parse_args()

    def run():
        cli = RLMCLIInterface()
        return cli.execute_operation(args.operation, args.params)

    try:
        if args.rlm_context:
            with RLMContext.set_context(args.rlm_context):
                result = run()
        else:
            result = run()
        print(json.dumps(result, indent=2))

    except RLMEnforcementError as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "RLM Enforcement Violation",
                    "message": str(e),
                    "solution": "Use AgentRLM for all AI agent interactions",
                },
                indent=2,
            )
        )
        sys.exit(1)

    except RepositoryAccessError as e:
        print(
            json.dumps(
                {"success": False, "error": "Repository Access Violation", "message": str(e)},
                indent=2,
            )
        )
        sys.exit(1)

    except Exception as e:
        print(
            json.dumps({"success": False, "error": "Unexpected Error", "message": str(e)}, indent=2)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
