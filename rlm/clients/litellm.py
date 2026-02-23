from collections import defaultdict
from typing import Any, cast

import litellm

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class LiteLLMClient(BaseLM):
    """
    LM Client for running models with LiteLLM.
    LiteLLM provides a unified interface to 100+ LLM providers.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or "gpt-4o-mini"
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs
        self.model_name = resolved_model_name
        self.api_key = api_key
        self.api_base = api_base

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        messages = self._normalize_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for LiteLLM client.")

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout

        litellm_module = cast(Any, litellm)
        response = litellm_module.completion(**kwargs)
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LiteLLM response did not include message content.")
        return str(content)

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        messages = self._normalize_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for LiteLLM client.")

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout

        litellm_module = cast(Any, litellm)
        response = await litellm_module.acompletion(**kwargs)
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LiteLLM response did not include message content.")
        return str(content)

    def _normalize_messages(self, prompt: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt}]
        return prompt

    def _track_cost(self, response: Any, model: str) -> None:
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)

        self.model_call_counts[model] += 1
        self.model_input_tokens[model] += prompt_tokens
        self.model_output_tokens[model] += completion_tokens
        self.model_total_tokens[model] += total_tokens

        # Track last call for handler to read
        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens

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
