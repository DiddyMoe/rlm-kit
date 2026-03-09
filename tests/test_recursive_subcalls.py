"""Tests for RF-070 Phase 2b recursive subcall activation."""

import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

import rlm.core.rlm as rlm_module
from rlm.core.rlm import RLM, RLMConfig
from rlm.core.types import ModelUsageSummary, RLMChatCompletion, UsageSummary
from rlm.environments.local_repl import LocalREPL


def _usage_summary(model_name: str = "mock") -> UsageSummary:
    return UsageSummary(
        model_usage_summaries={
            model_name: ModelUsageSummary(
                total_calls=1,
                total_input_tokens=10,
                total_output_tokens=5,
            )
        }
    )


class TestRecursiveSubcallActivation:
    def test_subcall_spawns_child_depth_plus_one_and_emits_callbacks(self) -> None:
        subcall_start_events: list[dict[str, Any]] = []
        subcall_complete_events: list[dict[str, Any]] = []
        iteration_start_events: list[dict[str, Any]] = []

        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.return_value = "FINAL(child done)"
            mock_lm.get_usage_summary.return_value = _usage_summary("root-model")
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 100
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_depth=3,
                    enable_recursive_subcalls=True,
                    on_subcall_start=lambda payload: subcall_start_events.append(payload),
                    on_subcall_complete=lambda payload: subcall_complete_events.append(payload),
                    on_iteration_start=lambda payload: iteration_start_events.append(payload),
                )
            )

            result = rlm.subcall("run nested")

        assert result.response == "child done"
        assert subcall_start_events == [{"parent_depth": 0, "child_depth": 1, "max_depth": 3}]
        assert len(subcall_complete_events) == 1
        assert subcall_complete_events[0]["status"] == "success"
        assert subcall_complete_events[0]["child_depth"] == 1
        assert any(event["depth"] == 1 for event in iteration_start_events)

    def test_subcall_respects_remaining_parent_error_budget(self) -> None:
        subcall_complete_events: list[dict[str, Any]] = []

        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.return_value = "FINAL(child done)"
            mock_lm.get_usage_summary.return_value = _usage_summary("root-model")
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 0
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_depth=3,
                    max_errors=1,
                    enable_recursive_subcalls=True,
                    on_subcall_complete=lambda payload: subcall_complete_events.append(payload),
                )
            )
            rlm.error_count = 1

            with pytest.raises(RuntimeError, match="error limit"):
                rlm.subcall("run nested")

        assert len(subcall_complete_events) == 1
        assert subcall_complete_events[0]["status"] == "error"
        assert "error limit" in subcall_complete_events[0]["error"]

    def test_subcall_rolls_up_child_error_count_to_parent(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            # First iteration: code block raises error (no text FINAL alongside)
            # Second iteration: text-only FINAL (no code blocks) — detected normally
            mock_lm.completion.side_effect = [
                "```repl\nraise RuntimeError('boom')\n```",
                "FINAL(child done)",
            ]
            mock_lm.get_usage_summary.return_value = _usage_summary("root-model")
            mock_lm.get_last_usage.return_value = mock_lm.get_usage_summary.return_value
            mock_lm.get_total_tokens.return_value = 0
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_depth=3,
                    max_errors=3,
                    enable_recursive_subcalls=True,
                )
            )

            result = rlm.subcall("run nested")

        assert result.response == "child done"
        assert rlm.error_count == 1

    def test_subcall_propagates_remaining_timeout_to_child(self) -> None:
        captured_child_timeouts: list[float | None] = []

        def fake_completion(
            instance: RLM, prompt: str | dict[str, Any], root_prompt: str | None = None
        ) -> RLMChatCompletion:
            _ = prompt, root_prompt
            captured_child_timeouts.append(instance.max_timeout)
            return RLMChatCompletion(
                root_model="child-model",
                prompt="nested",
                response="nested response",
                usage_summary=_usage_summary("child-model"),
                execution_time=0.01,
                metadata=None,
            )

        with patch.object(RLM, "completion", new=fake_completion):
            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "root-model"},
                    max_depth=3,
                    max_timeout=5.0,
                    enable_recursive_subcalls=True,
                )
            )
            rlm.active_time_start = time.perf_counter() - 2.0

            result = rlm.subcall("run nested")

        assert result.response == "nested response"
        assert len(captured_child_timeouts) == 1
        assert captured_child_timeouts[0] is not None
        assert 0.0 < captured_child_timeouts[0] < 5.0

    def test_subcall_raises_when_remaining_timeout_exhausted(self) -> None:
        subcall_complete_events: list[dict[str, Any]] = []

        rlm = RLM(
            RLMConfig(
                backend="openai",
                backend_kwargs={"model_name": "root-model"},
                max_depth=3,
                max_timeout=1.0,
                enable_recursive_subcalls=True,
                on_subcall_complete=lambda payload: subcall_complete_events.append(payload),
            )
        )
        rlm.active_time_start = time.perf_counter() - 2.0

        with pytest.raises(TimeoutError, match="RLM timeout"):
            rlm.subcall("run nested")

        assert len(subcall_complete_events) == 1
        assert subcall_complete_events[0]["status"] == "error"
        assert "RLM timeout" in subcall_complete_events[0]["error"]


class TestLocalREPLRecursiveSubcallHook:
    def test_local_repl_uses_recursive_subcall_fn_when_enabled(self) -> None:
        called_prompts: list[str] = []

        def fake_subcall(
            prompt: str | dict[str, Any], root_prompt: str | None = None
        ) -> RLMChatCompletion:
            _ = root_prompt
            called_prompts.append(str(prompt))
            return RLMChatCompletion(
                root_model="child-model",
                prompt=prompt,
                response="nested response",
                usage_summary=_usage_summary("child-model"),
                execution_time=0.01,
                metadata=None,
            )

        repl = LocalREPL(
            recursive_rlm_config={"max_depth": 3, "enable_recursive_subcalls": True},
            recursive_subcall_fn=fake_subcall,
            depth=1,
        )
        try:
            response = repl.llm_query("hello from repl")
        finally:
            repl.cleanup()

        assert response == "nested response"
        assert called_prompts == ["hello from repl"]
        assert len(repl.pending_llm_calls) == 1
