"""Tests for budget tracking, iteration limits, and BudgetExceededError (RF-090)."""

import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

import rlm.core.rlm as rlm_module
from rlm.core.rlm import RLM, RLMConfig
from rlm.core.types import (
    BudgetExceededError,
    ModelUsageSummary,
    UsageSummary,
)


class TestBudgetExceededError:
    def test_attributes(self) -> None:
        err = BudgetExceededError(1.5, 1.0)
        assert err.cumulative_cost == 1.5
        assert err.max_budget == 1.0

    def test_message_format(self) -> None:
        err = BudgetExceededError(0.0123, 0.01)
        assert "$0.0123" in str(err)
        assert "$0.0100" in str(err)
        assert "Budget exceeded" in str(err)

    def test_is_exception(self) -> None:
        with pytest.raises(BudgetExceededError):
            raise BudgetExceededError(2.0, 1.0)


class TestCumulativeCostTracking:
    """Test that _cumulative_cost is initialised and updated."""

    def test_cumulative_cost_init(self) -> None:
        rlm = RLM(RLMConfig(backend="openai"))
        assert rlm.cumulative_cost == 0.0
        assert rlm.last_handler_tokens == 0

    def test_update_handler_cost_increases_cumulative(self) -> None:
        """_update_handler_cost should add delta * 0.00001 to _cumulative_cost."""
        rlm = RLM(RLMConfig(backend="openai"))

        mock_client = Mock()
        mock_client.get_total_tokens.return_value = 10000

        mock_handler = Mock()
        mock_handler.default_client = mock_client

        rlm.update_handler_cost(mock_handler)

        # 10000 tokens * 0.00001 = 0.1
        assert abs(rlm.cumulative_cost - 0.1) < 1e-9
        assert rlm.last_handler_tokens == 10000

    def test_update_handler_cost_tracks_delta(self) -> None:
        """Second call should only add the delta since last sync."""
        rlm = RLM(RLMConfig(backend="openai"))

        mock_client = Mock()
        mock_handler = Mock()
        mock_handler.default_client = mock_client

        mock_client.get_total_tokens.return_value = 5000
        rlm.update_handler_cost(mock_handler)
        assert abs(rlm.cumulative_cost - 0.05) < 1e-9

        mock_client.get_total_tokens.return_value = 8000
        rlm.update_handler_cost(mock_handler)
        # Delta is 3000 tokens = 0.03 additional
        assert abs(rlm.cumulative_cost - 0.08) < 1e-9

    def test_update_handler_cost_no_change(self) -> None:
        """If no new tokens, cost stays the same."""
        rlm = RLM(RLMConfig(backend="openai"))

        mock_client = Mock()
        mock_client.get_total_tokens.return_value = 0
        mock_handler = Mock()
        mock_handler.default_client = mock_client

        rlm.update_handler_cost(mock_handler)
        assert rlm.cumulative_cost == 0.0


class TestCheckIterationLimits:
    """Test _check_iteration_limits raises on budget / timeout exceeded."""

    def test_budget_exceeded_raises(self) -> None:
        rlm = RLM(RLMConfig(backend="openai", max_budget=0.5))
        rlm.cumulative_cost = 0.6

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter()

        with pytest.raises(BudgetExceededError) as exc_info:
            rlm.check_iteration_limits(mock_loop_state)
        assert exc_info.value.cumulative_cost == 0.6
        assert exc_info.value.max_budget == 0.5

    def test_budget_not_exceeded_passes(self) -> None:
        rlm = RLM(RLMConfig(backend="openai", max_budget=1.0))
        rlm.cumulative_cost = 0.5

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter()

        # Should not raise
        rlm.check_iteration_limits(mock_loop_state)

    def test_no_budget_skips_check(self) -> None:
        rlm = RLM(RLMConfig(backend="openai"))
        rlm.cumulative_cost = 999.0

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter()

        # Should not raise — max_budget is None
        rlm.check_iteration_limits(mock_loop_state)

    def test_timeout_exceeded_raises(self) -> None:
        rlm = RLM(RLMConfig(backend="openai", max_timeout=0.001))

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter() - 1.0  # 1s ago

        with pytest.raises(TimeoutError, match="RLM timeout"):
            rlm.check_iteration_limits(mock_loop_state)

    def test_timeout_not_exceeded_passes(self) -> None:
        rlm = RLM(RLMConfig(backend="openai", max_timeout=60.0))

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter()

        # Should not raise
        rlm.check_iteration_limits(mock_loop_state)

    def test_max_errors_exceeded_raises(self) -> None:
        rlm = RLM(RLMConfig(backend="openai", max_errors=2))
        rlm.error_count = 2

        mock_loop_state = Mock()
        mock_loop_state.time_start = time.perf_counter()

        with pytest.raises(RuntimeError, match="error limit"):
            rlm.check_iteration_limits(mock_loop_state)


class TestBudgetIntegration:
    """Integration test: budget enforcement during completion."""

    def test_budget_exceeded_during_completion(self) -> None:
        """When the LM generates enough tokens, BudgetExceededError propagates."""
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            # Return a non-FINAL response so iteration continues
            mock_lm.completion.return_value = "thinking..."
            mock_lm.get_usage_summary.return_value = UsageSummary(
                model_usage_summaries={
                    "root-model": ModelUsageSummary(
                        total_calls=1,
                        total_input_tokens=50000,
                        total_output_tokens=50000,
                    )
                }
            )
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 100000
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_budget=0.001,  # Very low budget
                    max_iterations=10,
                )
            )

            # 100K tokens * $0.00001/token = $1.00, well above $0.001 budget
            with pytest.raises(BudgetExceededError):
                rlm.completion("hello")

    def test_max_errors_enforced_during_completion(self) -> None:
        """A stderr-producing REPL block should count toward max_errors."""
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.side_effect = [
                "```repl\nraise RuntimeError('boom')\n```",
                "FINAL(done)",
            ]
            mock_lm.get_usage_summary.return_value = UsageSummary(
                model_usage_summaries={
                    "root-model": ModelUsageSummary(
                        total_calls=2,
                        total_input_tokens=20,
                        total_output_tokens=10,
                    )
                }
            )
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 0
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_errors=1,
                    max_iterations=3,
                )
            )

            with pytest.raises(RuntimeError, match="error limit"):
                rlm.completion("hello")

    def test_budget_enforced_on_first_iteration_final_answer(self) -> None:
        """Budget overflow in iteration 1 should raise even if response is FINAL(...)."""
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.return_value = "FINAL(done)"
            mock_lm.get_usage_summary.return_value = UsageSummary(
                model_usage_summaries={
                    "root-model": ModelUsageSummary(
                        total_calls=1,
                        total_input_tokens=100000,
                        total_output_tokens=100000,
                    )
                }
            )
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 200000
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_budget=0.001,
                    max_iterations=1,
                )
            )

            with pytest.raises(BudgetExceededError):
                rlm.completion("hello")

    def test_max_errors_enforced_on_first_iteration_final_answer(self) -> None:
        """Error-producing iteration should raise on max_errors before returning FINAL."""
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.return_value = """```repl
raise RuntimeError('boom')
```
FINAL(done)"""
            mock_lm.get_usage_summary.return_value = UsageSummary(
                model_usage_summaries={
                    "root-model": ModelUsageSummary(
                        total_calls=1,
                        total_input_tokens=20,
                        total_output_tokens=10,
                    )
                }
            )
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 0
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_errors=1,
                    max_iterations=1,
                )
            )

            with pytest.raises(RuntimeError, match="error limit"):
                rlm.completion("hello")

    def test_timeout_enforced_after_slow_iteration_before_finalizing(self) -> None:
        """Timeout should be enforced if elapsed time exceeds limit during iteration work."""
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.get_usage_summary.return_value = UsageSummary(
                model_usage_summaries={
                    "root-model": ModelUsageSummary(
                        total_calls=1,
                        total_input_tokens=10,
                        total_output_tokens=5,
                    )
                }
            )
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 0
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_timeout=0.001,
                    max_iterations=1,
                )
            )

            original_completion_turn: Any = rlm.completion_turn

            def slow_completion_turn(*args: Any, **kwargs: Any) -> Any:
                time.sleep(0.01)
                return original_completion_turn(*args, **kwargs)

            with patch.object(rlm, "completion_turn", side_effect=slow_completion_turn):
                mock_lm.completion.return_value = "FINAL(done)"
                with pytest.raises(TimeoutError, match="RLM timeout"):
                    rlm.completion("hello")


class TestSubcallCostAccumulation:
    """RF-094: Verify subcall cost accumulates into parent _cumulative_cost."""

    def test_subcall_cost_added_to_parent(self) -> None:
        """Child RLM cost should be added to parent's _cumulative_cost after subcall."""
        parent = RLM(
            RLMConfig(
                backend="openai",
                backend_kwargs={"model_name": "parent-model"},
                enable_recursive_subcalls=True,
                max_depth=2,
            )
        )
        assert parent.cumulative_cost == 0.0

        # Simulate a subcall that consumed cost
        child = RLM(
            RLMConfig(
                backend="openai",
                backend_kwargs={"model_name": "child-model"},
                depth=1,
                max_depth=2,
            )
        )
        child.cumulative_cost = 0.25

        # Parent accumulates child cost
        parent.cumulative_cost += child.cumulative_cost
        assert abs(parent.cumulative_cost - 0.25) < 1e-9

    def test_handler_delta_plus_subcall_cost(self) -> None:
        """Handler delta cost and subcall cost should both contribute to cumulative cost."""
        parent = RLM(
            RLMConfig(
                backend="openai",
                backend_kwargs={"model_name": "parent-model"},
                max_depth=2,
            )
        )

        # Simulate handler delta
        mock_client = Mock()
        mock_client.get_total_tokens.return_value = 10000
        mock_handler = Mock()
        mock_handler.default_client = mock_client
        parent.update_handler_cost(mock_handler)
        handler_cost = parent.cumulative_cost
        assert handler_cost > 0

        # Simulate subcall adding cost
        subcall_cost = 0.15
        parent.cumulative_cost += subcall_cost

        # Total should be handler delta + subcall
        assert abs(parent.cumulative_cost - (handler_cost + subcall_cost)) < 1e-9

    def test_multiple_iterations_accumulate_cost(self) -> None:
        """Cost should accumulate across multiple handler delta updates (simulating iterations)."""
        rlm_instance = RLM(RLMConfig(backend="openai"))

        mock_client = Mock()
        mock_handler = Mock()
        mock_handler.default_client = mock_client

        # Iteration 1: 5000 tokens
        mock_client.get_total_tokens.return_value = 5000
        rlm_instance.update_handler_cost(mock_handler)
        cost_after_iter1 = rlm_instance.cumulative_cost

        # Iteration 2: 12000 total tokens (delta = 7000)
        mock_client.get_total_tokens.return_value = 12000
        rlm_instance.update_handler_cost(mock_handler)
        cost_after_iter2 = rlm_instance.cumulative_cost

        # Iteration 3: 20000 total tokens (delta = 8000)
        mock_client.get_total_tokens.return_value = 20000
        rlm_instance.update_handler_cost(mock_handler)
        cost_after_iter3 = rlm_instance.cumulative_cost

        assert cost_after_iter1 < cost_after_iter2 < cost_after_iter3
        # Total: 20000 tokens * $0.00001 = $0.20
        assert abs(cost_after_iter3 - 0.20) < 1e-9
