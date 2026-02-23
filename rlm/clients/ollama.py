"""Ollama client for local model support.

For parity with community forks (e.g. ddivito33/rlm_ollama_client), compare
model list, options (temperature, etc.), and error handling when upgrading.
"""

import os
from collections import defaultdict
from typing import Any

import requests
from dotenv import load_dotenv

from rlm.clients.base_lm import BaseLM
from rlm.core.retry import retry_with_backoff
from rlm.core.types import ModelUsageSummary, UsageSummary

load_dotenv()

# Default Ollama base URL
DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaClient(BaseLM):
    """
    LM Client for running models with Ollama (local models).

    Ollama runs models locally and provides a simple HTTP API.
    Default endpoint: http://localhost:11434
    """

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or ""
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs

        self.base_url = (base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.model_name = resolved_model_name

        if not self.model_name:
            raise ValueError("Model name is required for Ollama client.")

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def _normalize_prompt(self, prompt: str | list[dict[str, Any]]) -> str:
        """Normalize prompt to string format for Ollama.

        Args:
            prompt: Prompt as string or message list

        Returns:
            Normalized prompt string
        """
        if isinstance(prompt, str):
            return prompt

        messages: list[str] = []
        for msg in prompt:
            role = str(msg.get("role", "user"))
            content = str(msg.get("content", ""))
            if role == "system":
                messages.append(f"System: {content}")
            elif role == "user":
                messages.append(f"User: {content}")
            elif role == "assistant":
                messages.append(f"Assistant: {content}")
        return "\n".join(messages)

    def _make_completion_request(self, prompt: str, model: str | None = None) -> dict[str, Any]:
        """Make a completion request to Ollama API.

        Args:
            prompt: Prompt string
            model: Model name (optional, uses self.model_name if not provided)

        Returns:
            Response dictionary from Ollama API
        """
        model_name = model or self.model_name
        if not model_name:
            raise ValueError("Model name is required for Ollama client.")

        url = f"{self.base_url}/api/generate"
        payload: dict[str, str | bool] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }

        response = requests.post(url, json=payload, timeout=self.timeout or 300)
        response.raise_for_status()
        return response.json()

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        """
        Synchronous completion call with retry/resilience.

        Args:
            prompt: Prompt as string or message list
            model: Model name (optional)

        Returns:
            Response text from the model
        """
        normalized_prompt = self._normalize_prompt(prompt)
        model_name = model or self.model_name
        if not model_name:
            raise ValueError("Model name is required for Ollama client.")

        def _make_request() -> dict[str, Any]:
            return self._make_completion_request(normalized_prompt, model_name)

        try:
            response = retry_with_backoff(
                _make_request,
                max_attempts=3,
                initial_delay=1.0,
                max_delay=10.0,
                backoff_factor=2.0,
                retryable_exceptions=(
                    ConnectionError,
                    TimeoutError,
                    OSError,
                    requests.RequestException,
                ),
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama API request failed: {e}") from e

        # Extract response
        response_text = response.get("response", "")
        if not response_text:
            raise ValueError("Empty response from Ollama API")

        # Track usage (Ollama provides token counts in response)
        prompt_eval_count = int(response.get("prompt_eval_count", 0) or 0)
        eval_count = int(response.get("eval_count", 0) or 0)
        total_count = prompt_eval_count + eval_count

        # Update usage tracking
        self.model_call_counts[model_name] += 1
        self.model_input_tokens[model_name] += prompt_eval_count
        self.model_output_tokens[model_name] += eval_count
        self.model_total_tokens[model_name] += total_count

        return response_text

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        """
        Asynchronous completion call.

        Args:
            prompt: Prompt as string or message list
            model: Model name (optional)

        Returns:
            Response text from the model
        """
        # For now, use synchronous implementation
        # Ollama's async support can be added later if needed
        return self.completion(prompt, model)

    def get_usage_summary(self) -> UsageSummary:
        """Get cost summary for all model calls.

        Returns:
            UsageSummary with aggregated usage across all calls
        """
        model_usage_summaries: dict[str, ModelUsageSummary] = {}

        for model_name in self.model_call_counts:
            model_usage_summaries[model_name] = ModelUsageSummary(
                total_calls=self.model_call_counts[model_name],
                total_input_tokens=self.model_input_tokens[model_name],
                total_output_tokens=self.model_output_tokens[model_name],
            )

        return UsageSummary(model_usage_summaries=model_usage_summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        """Get the last cost summary of the model.

        Returns:
            ModelUsageSummary for the last call
        """
        model_name = self.model_name or "unknown"
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.model_input_tokens.get(model_name, 0),
            total_output_tokens=self.model_output_tokens.get(model_name, 0),
        )
