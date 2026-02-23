from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

pytest.importorskip("mcp")

from rlm.mcp_gateway.session import SessionManager
from rlm.mcp_gateway.tools.search_tools import SearchTools
from rlm.mcp_gateway.validation import PathValidator


class TestSearchTools:
    def test_search_query_respects_include_patterns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            python_file = root / "app.py"
            markdown_file = root / "README.md"
            python_file.write_text("def run_app():\n    return 'ok'\n", encoding="utf-8")
            markdown_file.write_text("RLM_SEARCH_NEEDLE\n", encoding="utf-8")

            session_manager = SessionManager()
            session = session_manager.create_session()
            session.allowed_roots = [str(root)]

            tools = SearchTools(session_manager, PathValidator(), root)
            default_result = tools.search_query(
                session_id=session.session_id,
                query="RLM_SEARCH_NEEDLE",
                scope=str(root),
            )
            assert default_result["success"] is True
            assert default_result["results"] == []

            markdown_result = tools.search_query(
                session_id=session.session_id,
                query="RLM_SEARCH_NEEDLE",
                scope=str(root),
                include_patterns=["*.md"],
            )
            assert markdown_result["success"] is True
            assert len(markdown_result["results"]) == 1
            assert markdown_result["results"][0]["file_path"].endswith("README.md")

    def test_search_regex_respects_include_patterns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            python_file = root / "service.py"
            typescript_file = root / "index.ts"
            python_file.write_text("class ApiService:\n    pass\n", encoding="utf-8")
            typescript_file.write_text("export const MCP_EVENT = 'ready';\n", encoding="utf-8")

            session_manager = SessionManager()
            session = session_manager.create_session()
            session.allowed_roots = [str(root)]

            tools = SearchTools(session_manager, PathValidator(), root)
            default_result = tools.search_regex(
                session_id=session.session_id,
                pattern="MCP_EVENT",
                scope=str(root),
            )
            assert default_result["success"] is True
            assert default_result["results"] == []

            typescript_result = tools.search_regex(
                session_id=session.session_id,
                pattern="MCP_EVENT",
                scope=str(root),
                include_patterns=["*.ts"],
            )
            assert typescript_result["success"] is True
            assert len(typescript_result["results"]) == 1
            assert typescript_result["results"][0]["file_path"].endswith("index.ts")
