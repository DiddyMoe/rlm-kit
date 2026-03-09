from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


def _openai_like_response(text: str, prompt_tokens: int = 2, completion_tokens: int = 3) -> Any:
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


class _FakeOpenAIAsyncCompletions:
    def __init__(self, response: Any) -> None:
        self.create = AsyncMock(return_value=response)


class _FakeOpenAIAsyncChat:
    def __init__(self, response: Any) -> None:
        self.completions = _FakeOpenAIAsyncCompletions(response)


class _FakeOpenAIAsyncClient:
    def __init__(self, response: Any) -> None:
        self.chat = _FakeOpenAIAsyncChat(response)


class _FakeAnthropicAsyncMessages:
    def __init__(self, response: Any) -> None:
        self.create = AsyncMock(return_value=response)


class _FakeAnthropicAsyncClient:
    def __init__(self, response: Any) -> None:
        self.messages = _FakeAnthropicAsyncMessages(response)


class TestClientAcompletion:
    def test_openai_client_acompletion(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.openai import OpenAIClient

        client = OpenAIClient(api_key="test-key", model_name="gpt-4o-mini")
        client.async_client = _FakeOpenAIAsyncClient(_openai_like_response("openai-async"))

        result = asyncio.run(client.acompletion("hello"))

        assert result == "openai-async"
        assert client.get_last_usage().total_output_tokens == 3

    def test_azure_client_acompletion(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(
            api_key="test-key",
            model_name="gpt-4o",
            azure_endpoint="https://example.openai.azure.com",
        )
        client.async_client = _FakeOpenAIAsyncClient(_openai_like_response("azure-async"))

        result = asyncio.run(client.acompletion("hello"))

        assert result == "azure-async"
        assert client.get_last_usage().total_input_tokens == 2

    def test_anthropic_client_acompletion(self) -> None:
        pytest.importorskip("anthropic")
        from rlm.clients.anthropic import AnthropicClient

        usage = SimpleNamespace(
            input_tokens=5,
            output_tokens=7,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        response = SimpleNamespace(content=[SimpleNamespace(text="anthropic-async")], usage=usage)

        client = AnthropicClient(api_key="test-key", model_name="claude-sonnet-4-20250514")
        client.async_client = _FakeAnthropicAsyncClient(response)

        result = asyncio.run(client.acompletion("hello"))

        assert result == "anthropic-async"
        assert client.get_last_usage().total_output_tokens == 7

    def test_litellm_client_acompletion(self) -> None:
        pytest.importorskip("litellm")
        from rlm.clients.litellm import LiteLLMClient

        response = _openai_like_response("litellm-async")

        with patch("rlm.clients.litellm.litellm") as litellm_module:
            litellm_module.acompletion = AsyncMock(return_value=response)
            client = LiteLLMClient(model_name="openai/gpt-4o-mini", api_key="test-key")

            result = asyncio.run(client.acompletion("hello"))

            assert result == "litellm-async"
            assert client.get_last_usage().total_input_tokens == 2

    def test_ollama_client_acompletion(self) -> None:
        from rlm.clients.ollama import OllamaClient

        client = OllamaClient(model_name="llama3.2")
        with patch.object(client, "completion", return_value="ollama-async") as completion_mock:
            result = asyncio.run(client.acompletion("hello"))

        assert result == "ollama-async"
        completion_mock.assert_called_once_with("hello", None)

    def test_groq_client_acompletion(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.groq import GroqClient

        client = GroqClient(api_key="test-key")
        client.async_client = _FakeOpenAIAsyncClient(_openai_like_response("groq-async"))

        result = asyncio.run(client.acompletion("hello"))

        assert result == "groq-async"

    def test_cerebras_client_acompletion(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.cerebras import CerebrasClient

        client = CerebrasClient(api_key="test-key")
        client.async_client = _FakeOpenAIAsyncClient(_openai_like_response("cerebras-async"))

        result = asyncio.run(client.acompletion("hello"))

        assert result == "cerebras-async"
