from collections import defaultdict
from typing import Any, Protocol, cast

import anthropic

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

AnthropicMessage = dict[str, object]
AnthropicMessageList = list[AnthropicMessage]

# Per-million-token pricing (USD) for Anthropic models.
# Cache write = 1.25× input price; cache read = 0.1× input price.
# Prices current as of 2026-03.  Update when new models are released.
_ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    # (input $/M tokens, output $/M tokens)
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-3-7-sonnet-20250219": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-sonnet-20240620": (3.0, 15.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.80, 4.0),
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-sonnet-20240229": (3.0, 15.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
}

# Multipliers relative to the base input price per the Anthropic prompt caching docs.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.10


class AnthropicMessagesClient(Protocol):
    def create(self, *args: Any, **kwargs: Any) -> anthropic.types.Message: ...


class AsyncAnthropicMessagesClient(Protocol):
    async def create(self, *args: Any, **kwargs: Any) -> anthropic.types.Message: ...


class AnthropicClientProtocol(Protocol):
    @property
    def messages(self) -> AnthropicMessagesClient: ...


class AsyncAnthropicClientProtocol(Protocol):
    @property
    def messages(self) -> AsyncAnthropicMessagesClient: ...


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
        self.enable_prompt_cache = bool(kwargs.pop("enable_prompt_cache", True))
        self.kwargs = kwargs
        if not api_key:
            raise ValueError("Anthropic API key is required.")
        if timeout is not None:
            self.client: AnthropicClientProtocol = anthropic.Anthropic(
                api_key=api_key, timeout=timeout
            )
            self.async_client: AsyncAnthropicClientProtocol = anthropic.AsyncAnthropic(
                api_key=api_key, timeout=timeout
            )
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
        self.model_cache_creation_input_tokens: dict[str, int] = defaultdict(int)
        self.model_cache_read_input_tokens: dict[str, int] = defaultdict(int)

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
        create_kwargs.update(self.kwargs)
        response = self.client.messages.create(**create_kwargs)
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
        create_kwargs.update(self.kwargs)
        response = await self.async_client.messages.create(**create_kwargs)
        self._track_cost(response, model)
        return self._extract_text_response(response)

    def _prepare_messages(
        self, prompt: str | list[dict[str, Any]]
    ) -> tuple[AnthropicMessageList, str | AnthropicMessageList | None]:
        """Prepare messages and extract system prompt for Anthropic API."""
        system: str | AnthropicMessageList | None = None
        messages: AnthropicMessageList

        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = []
            for msg in prompt:
                if msg.get("role") == "system":
                    system_content = msg.get("content")
                    if isinstance(system_content, str):
                        system = system_content
                    elif isinstance(system_content, list):
                        system = self._cacheable_content(cast(list[object], system_content))
                else:
                    messages.append(cast(AnthropicMessage, dict(msg)))

        if not self.enable_prompt_cache:
            return messages, system

        cacheable_system = self._cacheable_content(system)
        cacheable_messages = self._cacheable_messages(messages)
        return cacheable_messages, cacheable_system

    def _cacheable_messages(self, messages: AnthropicMessageList) -> AnthropicMessageList:
        cacheable_messages: AnthropicMessageList = []
        cached_context = False

        for message in messages:
            role = message.get("role")
            if role == "user" and not cached_context:
                cacheable_messages.append(
                    {
                        **message,
                        "content": self._cacheable_content(message.get("content")),
                    }
                )
                cached_context = True
                continue
            cacheable_messages.append(message)

        return cacheable_messages

    def _cacheable_content(self, content: object) -> AnthropicMessageList | None:
        if content is None:
            return None
        if isinstance(content, str):
            return [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if isinstance(content, list):
            content_blocks = cast(list[object], content)
            if not content_blocks:
                return []

            if not all(isinstance(block, dict) for block in content_blocks):
                return cast(AnthropicMessageList, content_blocks)

            cacheable_blocks: AnthropicMessageList = []
            typed_blocks = [cast(AnthropicMessage, block) for block in content_blocks]
            for index, block in enumerate(typed_blocks):
                if index == len(typed_blocks) - 1:
                    cacheable_blocks.append(
                        {
                            **block,
                            "cache_control": {"type": "ephemeral"},
                        }
                    )
                else:
                    cacheable_blocks.append(dict(block))
            return cacheable_blocks
        return None

    def _extract_text_response(self, response: anthropic.types.Message) -> str:
        for block in cast(list[object], response.content):
            text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                return text
        raise ValueError("Anthropic response did not include a text block.")

    def _track_cost(self, response: anthropic.types.Message, model: str) -> None:
        self.model_call_counts[model] += 1
        self.model_input_tokens[model] += response.usage.input_tokens
        self.model_output_tokens[model] += response.usage.output_tokens
        self.model_total_tokens[model] += response.usage.input_tokens + response.usage.output_tokens
        cache_creation_tokens = int(getattr(response.usage, "cache_creation_input_tokens", 0) or 0)
        cache_read_tokens = int(getattr(response.usage, "cache_read_input_tokens", 0) or 0)
        self.model_cache_creation_input_tokens[model] += cache_creation_tokens
        self.model_cache_read_input_tokens[model] += cache_read_tokens

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
                cache_creation_input_tokens=self.model_cache_creation_input_tokens[model],
                cache_read_input_tokens=self.model_cache_read_input_tokens[model],
            )
        return UsageSummary(model_usage_summaries=model_summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.last_prompt_tokens,
            total_output_tokens=self.last_completion_tokens,
        )

    def get_estimated_cost(self) -> dict[str, float]:
        """Return estimated USD cost per model, accounting for prompt caching.

        Uses ``_ANTHROPIC_PRICING`` for known models and falls back to the most
        expensive tier (opus) for unknown model names so that cost is never
        under-reported.
        """
        fallback_pricing = (15.0, 75.0)  # opus tier
        costs: dict[str, float] = {}
        for model in self.model_call_counts:
            input_price, output_price = _ANTHROPIC_PRICING.get(model, fallback_pricing)
            input_tokens = self.model_input_tokens[model]
            output_tokens = self.model_output_tokens[model]
            cache_write_tokens = self.model_cache_creation_input_tokens[model]
            cache_read_tokens = self.model_cache_read_input_tokens[model]

            # Regular input tokens (excluding cached portions)
            regular_input = max(input_tokens - cache_write_tokens - cache_read_tokens, 0)

            cost = (
                regular_input * input_price / 1_000_000
                + cache_write_tokens * input_price * _CACHE_WRITE_MULTIPLIER / 1_000_000
                + cache_read_tokens * input_price * _CACHE_READ_MULTIPLIER / 1_000_000
                + output_tokens * output_price / 1_000_000
            )
            costs[model] = cost
        return costs
