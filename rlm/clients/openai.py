import json
import os
from collections import defaultdict
from collections.abc import Callable
from typing import Any, cast

import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

load_dotenv()

# Load API keys from environment variables
DEFAULT_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_VERCEL_API_KEY = os.getenv("AI_GATEWAY_API_KEY")
DEFAULT_PRIME_INTELLECT_BASE_URL = "https://api.pinference.ai/api/v1/"


class OpenAIClient(BaseLM):
    """
    LM Client for running models with the OpenAI API. Works with vLLM as well.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or "gpt-4o-mini"
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs

        resolved_api_key = self._resolve_api_key(api_key=api_key, base_url=base_url)
        self._validate_hosted_api_key(api_key=resolved_api_key, base_url=base_url)

        # For vLLM, set base_url to local vLLM server address.
        self.client = openai.OpenAI(
            api_key=resolved_api_key, base_url=base_url, timeout=timeout or openai.NOT_GIVEN
        )
        self.async_client = openai.AsyncOpenAI(
            api_key=resolved_api_key, base_url=base_url, timeout=timeout or openai.NOT_GIVEN
        )
        self.model_name = resolved_model_name
        self.prefix_cache_enabled = bool(self.kwargs.get("prefix_cache_enabled", False))
        self._prefix_messages_cache: dict[str, list[ChatCompletionMessageParam]] = {}

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def _resolve_api_key(self, api_key: str | None, base_url: str | None) -> str | None:
        if api_key is not None:
            return api_key
        if base_url == "https://openrouter.ai/api/v1":
            return DEFAULT_OPENROUTER_API_KEY
        if base_url == "https://ai-gateway.vercel.sh/v1":
            return DEFAULT_VERCEL_API_KEY
        return DEFAULT_OPENAI_API_KEY

    def _validate_hosted_api_key(self, api_key: str | None, base_url: str | None) -> None:
        hosted_base_urls: set[str | None] = {
            None,
            "https://api.openai.com/v1",
            "https://openrouter.ai/api/v1",
            "https://ai-gateway.vercel.sh/v1",
        }
        if api_key is None and base_url in hosted_base_urls:
            raise ValueError(
                "API key is required for hosted OpenAI-compatible endpoints. "
                "Set api_key explicitly or configure environment credentials."
            )

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        messages = self._normalize_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for OpenAI client.")

        extra_body: dict[str, Any] = {}
        if self.client.base_url == DEFAULT_PRIME_INTELLECT_BASE_URL:
            extra_body["usage"] = {"include": True}

        response = self.client.chat.completions.create(
            model=model, messages=messages, extra_body=extra_body
        )
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI response did not include message content.")
        return content

    def stream_completion(
        self,
        prompt: str | list[dict[str, Any]],
        on_chunk: Callable[[str], None],
        model: str | None = None,
    ) -> str:
        messages = self._normalize_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for OpenAI client.")

        self.model_call_counts[model] += 1
        final_text_parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0

        stream = cast(Any, self.client.chat.completions).create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        for chunk in stream:
            delta_text, chunk_prompt_tokens, chunk_completion_tokens = self._process_stream_chunk(
                chunk
            )
            if delta_text:
                final_text_parts.append(delta_text)
                on_chunk(delta_text)

            prompt_tokens = chunk_prompt_tokens or prompt_tokens
            completion_tokens = chunk_completion_tokens or completion_tokens

        self._record_stream_usage(model, prompt_tokens, completion_tokens)

        return "".join(final_text_parts)

    def _process_stream_chunk(self, chunk: Any) -> tuple[str, int, int]:
        delta_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        if chunk.choices:
            delta_text = chunk.choices[0].delta.content or ""

        usage = getattr(chunk, "usage", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return delta_text, prompt_tokens, completion_tokens

    def _record_stream_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return

        self.model_input_tokens[model] += prompt_tokens
        self.model_output_tokens[model] += completion_tokens
        self.model_total_tokens[model] += prompt_tokens + completion_tokens
        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        messages = self._normalize_messages(prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for OpenAI client.")

        extra_body: dict[str, Any] = {}
        if self.client.base_url == DEFAULT_PRIME_INTELLECT_BASE_URL:
            extra_body["usage"] = {"include": True}

        response = await self.async_client.chat.completions.create(
            model=model, messages=messages, extra_body=extra_body
        )
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI response did not include message content.")
        return content

    def _normalize_messages(
        self, prompt: str | list[dict[str, Any]] | dict[str, Any]
    ) -> list[ChatCompletionMessageParam]:
        if self.prefix_cache_enabled and isinstance(prompt, list):
            cached = self._cached_prefix_messages(prompt)
            if cached is not None:
                return cached
        if isinstance(prompt, str):
            return cast(list[ChatCompletionMessageParam], [{"role": "user", "content": prompt}])
        if isinstance(prompt, list):
            return cast(list[ChatCompletionMessageParam], prompt)
        return [cast(ChatCompletionMessageParam, prompt)]

    def _cached_prefix_messages(
        self, prompt: list[dict[str, Any]]
    ) -> list[ChatCompletionMessageParam] | None:
        """Return messages using a lightweight prefix cache for iterative loops."""
        if len(prompt) <= 1:
            return None

        prefix = prompt[:-1]
        try:
            prefix_key = json.dumps(prefix, sort_keys=True, ensure_ascii=False, default=str)
        except TypeError:
            return None

        cached_prefix = self._prefix_messages_cache.get(prefix_key)
        if cached_prefix is None:
            cached_prefix = cast(list[ChatCompletionMessageParam], list(prefix))
            self._prefix_messages_cache[prefix_key] = cached_prefix
            if len(self._prefix_messages_cache) > 128:
                oldest_key = next(iter(self._prefix_messages_cache))
                del self._prefix_messages_cache[oldest_key]

        return [*cached_prefix, cast(ChatCompletionMessageParam, prompt[-1])]

    def _track_cost(self, response: ChatCompletion, model: str) -> None:
        self.model_call_counts[model] += 1

        usage = getattr(response, "usage", None)
        if usage is None:
            raise ValueError("No usage data received. Tracking tokens not possible.")

        self.model_input_tokens[model] += usage.prompt_tokens
        self.model_output_tokens[model] += usage.completion_tokens
        self.model_total_tokens[model] += usage.total_tokens

        # Track last call for handler to read
        self.last_prompt_tokens = usage.prompt_tokens
        self.last_completion_tokens = usage.completion_tokens

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
