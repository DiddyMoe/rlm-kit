"""Tests for MCP gateway resources."""

from pathlib import Path

import pytest

pytest.importorskip("mcp")

from rlm.mcp_gateway.server import RLMMCPGateway


class TestGatewayReadResource:
    def test_read_resource_sessions_returns_created_session(self) -> None:
        gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
        session = gateway.session_manager.create_session()

        response = gateway.read_resource("rlm://sessions")

        assert response["success"] is True
        session_ids = [entry["session_id"] for entry in response["sessions"]]
        assert session.session_id in session_ids

    def test_read_resource_session_returns_session_config(self) -> None:
        gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
        session = gateway.session_manager.create_session()

        response = gateway.read_resource(f"rlm://sessions/{session.session_id}")

        assert response["success"] is True
        assert response["session"]["session_id"] == session.session_id
        assert response["session"]["config"]["max_depth"] == session.config.max_depth

    def test_read_resource_trajectory_returns_session_trajectory(self) -> None:
        gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
        session = gateway.session_manager.create_session()

        response = gateway.read_resource(f"rlm://sessions/{session.session_id}/trajectory")

        assert response["success"] is True
        assert response["session_id"] == session.session_id
        assert response["provenance"] == []
        assert response["accessed_spans"] == {}
