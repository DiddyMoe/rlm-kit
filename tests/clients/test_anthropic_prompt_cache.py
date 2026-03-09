from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("anthropic")

from rlm.clients.anthropic import AnthropicClient


def _mock_anthropic_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=4,
            cache_creation_input_tokens=7,
            cache_read_input_tokens=3,
        ),
    )


def test_completion_adds_cache_control_to_system_and_context_messages() -> None:
    with (
        patch("rlm.clients.anthropic.anthropic.Anthropic") as mock_sync_cls,
        patch("rlm.clients.anthropic.anthropic.AsyncAnthropic"),
    ):
        mock_sync_client = mock_sync_cls.return_value
        mock_sync_client.messages.create.return_value = _mock_anthropic_response("ok")

        client = AnthropicClient(
            api_key="test-key",
            model_name="claude-3-5-sonnet",
            enable_prompt_cache=True,
        )

        response = client.completion(
            [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Long context"},
                {"role": "assistant", "content": "intermediate"},
                {"role": "user", "content": "Final question"},
            ]
        )

        assert response == "ok"
        request_kwargs = mock_sync_client.messages.create.call_args.kwargs

        system = request_kwargs["system"]
        assert isinstance(system, list)
        assert system[0]["cache_control"] == {"type": "ephemeral"}

        first_user = request_kwargs["messages"][0]
        assert isinstance(first_user["content"], list)
        assert first_user["content"][0]["cache_control"] == {"type": "ephemeral"}

        second_user = request_kwargs["messages"][-1]
        assert isinstance(second_user["content"], str)


def test_usage_summary_includes_prompt_cache_token_stats() -> None:
    with (
        patch("rlm.clients.anthropic.anthropic.Anthropic") as mock_sync_cls,
        patch("rlm.clients.anthropic.anthropic.AsyncAnthropic"),
    ):
        mock_sync_client = mock_sync_cls.return_value
        mock_sync_client.messages.create.return_value = _mock_anthropic_response("ok")

        client = AnthropicClient(api_key="test-key", model_name="claude-3-5-sonnet")
        _ = client.completion("Hello")

        usage = client.get_usage_summary().model_usage_summaries["claude-3-5-sonnet"]
        assert usage.cache_creation_input_tokens == 7
        assert usage.cache_read_input_tokens == 3


def test_get_estimated_cost_with_cache_aware_billing() -> None:
    """RF-093: Verify per-model cost estimation accounts for prompt caching pricing."""
    with (
        patch("rlm.clients.anthropic.anthropic.Anthropic") as mock_sync_cls,
        patch("rlm.clients.anthropic.anthropic.AsyncAnthropic"),
    ):
        mock_sync_client = mock_sync_cls.return_value
        mock_sync_client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(text="ok")],
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=500,
                cache_creation_input_tokens=200,
                cache_read_input_tokens=300,
            ),
        )

        client = AnthropicClient(api_key="test-key", model_name="claude-3-5-sonnet")
        _ = client.completion("Hello")

        costs = client.get_estimated_cost()
        assert "claude-3-5-sonnet" in costs

        # claude-3-5-sonnet: $3/M input, $15/M output
        # regular input: 1000 - 200 - 300 = 500 tokens at $3/M = $0.0015
        # cache write: 200 tokens at $3 * 1.25/M = $0.00075
        # cache read: 300 tokens at $3 * 0.10/M = $0.00009
        # output: 500 tokens at $15/M = $0.0075
        expected = (
            500 * 3 / 1_000_000
            + 200 * 3 * 1.25 / 1_000_000
            + 300 * 3 * 0.10 / 1_000_000
            + 500 * 15 / 1_000_000
        )
        assert abs(costs["claude-3-5-sonnet"] - expected) < 1e-9


def test_get_estimated_cost_unknown_model_uses_fallback_pricing() -> None:
    """Unknown models should use the most expensive (opus) pricing as fallback."""
    with (
        patch("rlm.clients.anthropic.anthropic.Anthropic") as mock_sync_cls,
        patch("rlm.clients.anthropic.anthropic.AsyncAnthropic"),
    ):
        mock_sync_client = mock_sync_cls.return_value
        mock_sync_client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(text="ok")],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )

        client = AnthropicClient(api_key="test-key", model_name="claude-future-model-2027")
        _ = client.completion("Hello")

        costs = client.get_estimated_cost()
        assert "claude-future-model-2027" in costs

        # Fallback: $15/M input, $75/M output (opus tier)
        expected = 100 * 15 / 1_000_000 + 50 * 75 / 1_000_000
        assert abs(costs["claude-future-model-2027"] - expected) < 1e-9
