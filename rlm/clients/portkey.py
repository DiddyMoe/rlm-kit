from collections import defaultdict
from typing import Any, cast

from portkey_ai import AsyncPortkey, Portkey
from portkey_ai.api_resources.types.chat_complete_type import ChatCompletions

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class PortkeyClient(BaseLM):
    """
    LM Client for running models with the Portkey API.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        base_url: str | None = "https://api.portkey.ai/v1",
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or ""
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs
        if not api_key:
            raise ValueError("Portkey API key is required.")
        portkey_kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url}
        if timeout is not None:
            portkey_kwargs["timeout"] = timeout
        self.client = Portkey(**portkey_kwargs)
        self.async_client = AsyncPortkey(**portkey_kwargs)
        self.model_name = resolved_model_name
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        if isinstance(prompt, str):
            messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Portkey client.")

        response = cast(Any, self.client.chat.completions).create(
            model=model,
            messages=messages,
        )
        self._track_cost(response, model)
        content = self._extract_content(response)
        if not content:
            raise ValueError("Portkey response did not include message content.")
        return content

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        if isinstance(prompt, str):
            messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Portkey client.")

        response = await cast(Any, self.async_client.chat.completions).create(
            model=model, messages=messages
        )
        self._track_cost(response, model)
        content = self._extract_content(response)
        if not content:
            raise ValueError("Portkey response did not include message content.")
        return content

    def _extract_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        return str(content)

    def _track_cost(self, response: ChatCompletions | Any, model: str) -> None:
        self.model_call_counts[model] += 1

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)

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
