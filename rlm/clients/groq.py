import os
from typing import Any

from rlm.clients.openai import OpenAIClient

DEFAULT_GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqClient(OpenAIClient):
    """OpenAI-compatible client wrapper for Groq-hosted models."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_api_key = api_key or DEFAULT_GROQ_API_KEY
        if resolved_api_key is None:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY env var or pass api_key.")

        super().__init__(
            api_key=resolved_api_key,
            model_name=model_name or "llama-3.3-70b-versatile",
            base_url=base_url or DEFAULT_GROQ_BASE_URL,
            timeout=timeout,
            **kwargs,
        )
