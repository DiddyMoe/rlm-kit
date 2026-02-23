from unittest.mock import patch

import pytest


def test_openai_client_requires_api_key_for_hosted_endpoints() -> None:
    pytest.importorskip("openai")
    from rlm.clients.openai import OpenAIClient

    with patch("rlm.clients.openai.DEFAULT_OPENAI_API_KEY", None):
        with patch("rlm.clients.openai.DEFAULT_OPENROUTER_API_KEY", None):
            with patch("rlm.clients.openai.DEFAULT_VERCEL_API_KEY", None):
                with pytest.raises(ValueError, match="API key is required"):
                    OpenAIClient(api_key=None, model_name="gpt-4.1")


def test_anthropic_client_requires_api_key() -> None:
    pytest.importorskip("anthropic")
    from rlm.clients.anthropic import AnthropicClient

    with pytest.raises(ValueError, match="Anthropic API key is required"):
        AnthropicClient(api_key="", model_name="claude-3-5-sonnet")


def test_azure_openai_client_requires_api_key() -> None:
    pytest.importorskip("openai")
    from rlm.clients.azure_openai import AzureOpenAIClient

    with patch("rlm.clients.azure_openai.DEFAULT_AZURE_OPENAI_API_KEY", None):
        with pytest.raises(ValueError, match="API key is required"):
            AzureOpenAIClient(api_key=None, azure_endpoint="https://example.openai.azure.com")


def test_portkey_client_requires_api_key() -> None:
    pytest.importorskip("portkey_ai")
    from rlm.clients.portkey import PortkeyClient

    with pytest.raises(ValueError, match="Portkey API key is required"):
        PortkeyClient(api_key="", model_name="@openai/gpt-5")


def test_litellm_client_allows_missing_api_key_for_generic_providers() -> None:
    pytest.importorskip("litellm")
    from rlm.clients.litellm import LiteLLMClient

    client = LiteLLMClient(model_name="mock-provider/model", api_key=None)
    assert client.api_key is None


def test_ollama_client_does_not_require_api_key() -> None:
    from rlm.clients.ollama import OllamaClient

    client = OllamaClient(model_name="llama3.2")
    assert client.model_name == "llama3.2"


def test_gemini_client_requires_api_key() -> None:
    pytest.importorskip("google.genai")
    from rlm.clients.gemini import GeminiClient

    with patch("rlm.clients.gemini.DEFAULT_GEMINI_API_KEY", None):
        with pytest.raises(ValueError, match="Gemini API key is required"):
            GeminiClient(api_key=None, model_name="gemini-2.5-flash")
