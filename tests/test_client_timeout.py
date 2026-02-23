"""Tests for per-client timeout parameter (RF-053).

Verifies that:
1. BaseLM stores timeout attribute
2. OpenAIClient passes timeout to openai SDK clients
3. Timeout defaults to None (no timeout)
"""

from typing import Any
from unittest.mock import patch

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class _ConcreteLM(BaseLM):
    """Minimal concrete subclass for testing BaseLM."""

    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        return "ok"

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return "ok"

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(model_usage_summaries={})

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(total_calls=0, total_input_tokens=0, total_output_tokens=0)


class TestBaseLMTimeout:
    def test_timeout_stored(self) -> None:
        lm = _ConcreteLM(model_name="test", timeout=30.0)
        assert lm.timeout == 30.0

    def test_timeout_defaults_to_none(self) -> None:
        lm = _ConcreteLM(model_name="test")
        assert lm.timeout is None


class TestOpenAIClientTimeout:
    def test_timeout_passed_to_sdk(self) -> None:
        with (
            patch("rlm.clients.openai.openai.OpenAI") as mock_openai,
            patch("rlm.clients.openai.openai.AsyncOpenAI") as mock_async_openai,
        ):
            from rlm.clients.openai import OpenAIClient

            client = OpenAIClient(api_key="test-key", model_name="gpt-4o", timeout=42.0)
            assert client.timeout == 42.0
            # Verify timeout was passed to SDK constructors
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args
            assert (
                call_kwargs.kwargs.get("timeout") == 42.0 or call_kwargs[1].get("timeout") == 42.0
            )

            mock_async_openai.assert_called_once()
            async_call_kwargs = mock_async_openai.call_args
            assert (
                async_call_kwargs.kwargs.get("timeout") == 42.0
                or async_call_kwargs[1].get("timeout") == 42.0
            )

    def test_no_timeout_uses_not_given(self) -> None:
        import openai as openai_module

        with (
            patch("rlm.clients.openai.openai.OpenAI") as mock_openai,
            patch("rlm.clients.openai.openai.AsyncOpenAI"),
        ):
            from rlm.clients.openai import OpenAIClient

            OpenAIClient(api_key="test-key", model_name="gpt-4o")
            call_kwargs = mock_openai.call_args
            timeout_val = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
            assert timeout_val is openai_module.NOT_GIVEN
