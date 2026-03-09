"""Tests for MCP gateway session cancellation (RF-075)."""

from rlm.mcp_gateway.session import Session, SessionConfig, SessionManager


class TestSessionCancellationFlag:
    def test_default_not_cancelled(self) -> None:
        import time

        session = Session(
            session_id="test-1",
            config=SessionConfig(),
            allowed_roots=[],
            created_at=time.time(),
        )
        assert session.cancellation_requested is False

    def test_flag_can_be_set(self) -> None:
        import time

        session = Session(
            session_id="test-2",
            config=SessionConfig(),
            allowed_roots=[],
            created_at=time.time(),
        )
        session.cancellation_requested = True
        assert session.cancellation_requested is True


class TestSessionManagerCancellation:
    def test_cancel_session(self) -> None:
        manager = SessionManager()
        session = manager.create_session()

        result = manager.cancel_session(session.session_id)

        assert result is True
        assert session.cancellation_requested is True

    def test_cancel_nonexistent_session(self) -> None:
        manager = SessionManager()
        result = manager.cancel_session("nonexistent")
        assert result is False

    def test_cancel_by_request_id(self) -> None:
        manager = SessionManager()
        session = manager.create_session()

        manager.register_active_request("req-123", session.session_id)
        result = manager.cancel_by_request_id("req-123")

        assert result is True
        assert session.cancellation_requested is True

    def test_cancel_by_unknown_request_id(self) -> None:
        manager = SessionManager()
        result = manager.cancel_by_request_id("unknown-req")
        assert result is False

    def test_register_and_unregister_request(self) -> None:
        manager = SessionManager()
        session = manager.create_session()

        manager.register_active_request("req-1", session.session_id)
        manager.unregister_active_request("req-1")

        # After unregister, cancel by request should fail
        result = manager.cancel_by_request_id("req-1")
        assert result is False
        assert session.cancellation_requested is False

    def test_check_budget_returns_cancelled(self) -> None:
        manager = SessionManager()
        session = manager.create_session()
        session.cancellation_requested = True

        within_budget, reason = manager.check_budget(session)

        assert within_budget is False
        assert reason == "Cancelled by client"


class TestCancellationErrorInCompleteTools:
    """Test the public cancellation error and callback."""

    def test_cancellation_error_exists(self) -> None:
        from rlm.mcp_gateway.tools.complete_tools import CancellationError

        err = CancellationError("test message")
        assert str(err) == "test message"
        assert isinstance(err, Exception)

    def test_create_rlm_instance_with_cancelled_session(self) -> None:
        """When session.cancellation_requested is True, the on_iteration_start callback
        should raise `CancellationError`."""
        import time

        from rlm.mcp_gateway.tools.complete_tools import CancellationError, CompleteTools

        session = Session(
            session_id="cancel-test",
            config=SessionConfig(),
            allowed_roots=[],
            created_at=time.time(),
        )
        session.cancellation_requested = True

        manager = SessionManager()
        tools = CompleteTools(manager)
        rlm_instance = tools.create_rlm_instance(
            backend="openai",
            backend_kwargs={"model_name": "test-model"},
            max_iterations=5,
            session=session,
        )

        # The on_iteration_start callback should raise when session is cancelled
        assert rlm_instance.on_iteration_start is not None
        import pytest

        with pytest.raises(CancellationError, match="Cancelled by client"):
            rlm_instance.on_iteration_start({"depth": 0, "iteration": 1, "max_iterations": 5})

    def test_create_rlm_instance_without_session_has_no_callback(self) -> None:
        """Without a session, on_iteration_start should be None."""
        from rlm.mcp_gateway.tools.complete_tools import CompleteTools

        manager = SessionManager()
        tools = CompleteTools(manager)
        rlm_instance = tools.create_rlm_instance(
            backend="openai",
            backend_kwargs={"model_name": "test-model"},
            max_iterations=5,
        )
        assert rlm_instance.on_iteration_start is None
