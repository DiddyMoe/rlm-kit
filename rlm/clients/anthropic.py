from collections import defaultdict
from typing import Any, cast

import anthropic

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class AnthropicClient(BaseLM):
    """
    LM Client for running models with the Anthropic API.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        max_tokens: int = 32768,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or "claude-3-5-sonnet"
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs
        if not api_key:
            raise ValueError("Anthropic API key is required.")
        if timeout is not None:
            self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
            self.async_client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.async_client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model_name = resolved_model_name
        self.max_tokens = max_tokens

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        messages, system = self._prepare_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Anthropic client.")

        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system is not None:
            create_kwargs["system"] = system
        response = cast(anthropic.types.Message, self.client.messages.create(**create_kwargs))
        self._track_cost(response, model)
        return self._extract_text_response(response)

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        messages, system = self._prepare_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Anthropic client.")

        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system is not None:
            create_kwargs["system"] = system
        response = cast(
            anthropic.types.Message,
            await self.async_client.messages.create(**create_kwargs),
        )
        self._track_cost(response, model)
        return self._extract_text_response(response)

    def _prepare_messages(
        self, prompt: str | list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Prepare messages and extract system prompt for Anthropic API."""
        system = None
        messages: list[dict[str, Any]]

        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = []
            for msg in prompt:
                if msg.get("role") == "system":
                    system = msg.get("content")
                else:
                    messages.append(msg)

        return messages, system

    def _extract_text_response(self, response: Any) -> str:
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                return text
        raise ValueError("Anthropic response did not include a text block.")

    def _track_cost(self, response: anthropic.types.Message, model: str):
        self.model_call_counts[model] += 1
        self.model_input_tokens[model] += response.usage.input_tokens
        self.model_output_tokens[model] += response.usage.output_tokens
        self.model_total_tokens[model] += response.usage.input_tokens + response.usage.output_tokens

        # Track last call for handler to read
        self.last_prompt_tokens = response.usage.input_tokens
        self.last_completion_tokens = response.usage.output_tokens

    def get_usage_summary(self) -> UsageSummary:
        model_summaries: dict[str, ModelUsageSummary] = {}
        for model in self.model_call_counts:
            model_summaries[model] = ModelUsageSummary(
                total_calls=self.model_call_counts[model],
                total_input_tokens=self.model_input_tokens[model],
                total_output_tokens=self.model_output_tokens[model],
            )
        return UsageSummary(model_usage_summaries=model_summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.last_prompt_tokens,
            total_output_tokens=self.last_completion_tokens,
        )
