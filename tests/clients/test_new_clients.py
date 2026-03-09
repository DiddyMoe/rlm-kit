from __future__ import annotations

from unittest.mock import patch

import pytest


class TestNewClientValidation:
    def test_groq_client_requires_api_key(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.groq import GroqClient

        with patch("rlm.clients.groq.DEFAULT_GROQ_API_KEY", None):
            with pytest.raises(ValueError, match="Groq API key is required"):
                GroqClient(api_key=None, model_name="llama-3.3-70b-versatile")

    def test_cerebras_client_requires_api_key(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.cerebras import CerebrasClient

        with patch("rlm.clients.cerebras.DEFAULT_CEREBRAS_API_KEY", None):
            with pytest.raises(ValueError, match="Cerebras API key is required"):
                CerebrasClient(api_key=None, model_name="llama-3.1-8b")

    def test_groq_client_uses_openai_compatible_defaults(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.groq import DEFAULT_GROQ_BASE_URL, GroqClient

        client = GroqClient(api_key="test-key")

        assert client.model_name == "llama-3.3-70b-versatile"
        assert str(client.client.base_url).rstrip("/") == DEFAULT_GROQ_BASE_URL.rstrip("/")

    def test_cerebras_client_uses_openai_compatible_defaults(self) -> None:
        pytest.importorskip("openai")
        from rlm.clients.cerebras import DEFAULT_CEREBRAS_BASE_URL, CerebrasClient

        client = CerebrasClient(api_key="test-key")

        assert client.model_name == "llama-3.1-8b"
        assert str(client.client.base_url).rstrip("/") == DEFAULT_CEREBRAS_BASE_URL.rstrip("/")
