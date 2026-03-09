"""Tests for RLMConfig constructor support."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest

import rlm.core.rlm as rlm_module
from rlm.clients.base_lm import BaseLM
from rlm.core.rlm import RLM, RLMConfig
from rlm.core.types import ModelUsageSummary, UsageSummary


class DummyLM(BaseLM):
    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        return f"{self.model_name}:{prompt}"

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return self.completion(prompt)

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(
            model_usage_summaries={
                self.model_name: ModelUsageSummary(
                    total_calls=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                )
            }
        )

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(total_calls=0, total_input_tokens=0, total_output_tokens=0)

    def stream_completion(
        self,
        prompt: str | list[dict[str, Any]],
        on_chunk: Callable[[str], None],
        model: str | None = None,
    ) -> str:
        _ = model
        response = self.completion(prompt)
        on_chunk(response)
        return response


class TestRLMConfigConstructor:
    def test_accepts_config_object(self) -> None:
        config = RLMConfig(
            backend="openai",
            backend_kwargs={"model_name": "gpt-4o-mini"},
            max_iterations=12,
            compaction=True,
        )

        rlm = RLM(config)

        assert rlm.backend == "openai"
        assert rlm.backend_kwargs == {"model_name": "gpt-4o-mini"}
        assert rlm.max_iterations == 12
        assert rlm.compaction is True

    def test_rejects_additional_init_args(self) -> None:
        config = RLMConfig(backend="openai")

        with pytest.raises(TypeError):
            cast(Any, RLM)(config, max_iterations=50)

    def test_accepts_rf070_phase1_scaffolding_fields(self) -> None:
        events: list[dict[str, Any]] = []

        config = RLMConfig(
            backend="openai",
            max_budget=3.5,
            max_timeout=30.0,
            max_errors=2,
            enable_recursive_subcalls=True,
            on_iteration_start=lambda payload: events.append(payload),
            on_iteration_complete=lambda payload: events.append(payload),
        )

        rlm = RLM(config)

        assert rlm.max_budget == 3.5
        assert rlm.max_timeout == 30.0
        assert rlm.max_errors == 2
        assert rlm.enable_recursive_subcalls is True
        assert rlm.on_iteration_start is not None
        assert rlm.on_iteration_complete is not None

    def test_iteration_callbacks_receive_expected_payload_shape(self) -> None:
        start_events: list[dict[str, Any]] = []
        complete_events: list[dict[str, Any]] = []
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.model_name = "root-model"
            mock_lm.completion.return_value = "FINAL(done)"
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
                    on_iteration_start=lambda payload: start_events.append(payload),
                    on_iteration_complete=lambda payload: complete_events.append(payload),
                )
            )
            _ = rlm.completion("hello")

        assert start_events == [{"depth": 0, "iteration": 1, "max_iterations": 30}]
        assert len(complete_events) == 1
        complete_payload = complete_events[0]
        assert complete_payload["depth"] == 0
        assert complete_payload["iteration"] == 1
        assert complete_payload["response"] == "FINAL(done)"
        assert complete_payload["code_block_count"] == 0
        assert isinstance(complete_payload["iteration_time"], float)

    def test_sub_lms_aliases_register_with_lm_handler(self) -> None:
        fast_client = DummyLM("fast-model")
        strong_client = DummyLM("strong-model")

        rlm = RLM(
            RLMConfig(
                backend="openai",
                backend_kwargs={"model_name": "root-model", "api_key": "test-key"},
                sub_lms={"fast": fast_client, "strong": strong_client},
            )
        )
        lm_handler = rlm.create_lm_handler()

        try:
            assert lm_handler.get_client(model="fast") is fast_client
            assert lm_handler.get_client(model="strong") is strong_client
            assert lm_handler.get_client(model="unknown").model_name == "root-model"
        finally:
            lm_handler.stop()
