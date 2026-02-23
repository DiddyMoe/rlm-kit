import os
from collections import defaultdict
from typing import Any, cast

import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

load_dotenv()

# Load API key from environment variable
DEFAULT_AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")


class AzureOpenAIClient(BaseLM):
    """
    LM Client for running models with the Azure OpenAI API.
    """

    def _resolve_api_key(self, api_key: str | None) -> str:
        resolved = api_key or DEFAULT_AZURE_OPENAI_API_KEY
        if resolved is None:
            raise ValueError(
                "API key is required for Azure OpenAI client. "
                "Set it via argument or AZURE_OPENAI_API_KEY environment variable."
            )
        return resolved

    def _resolve_azure_endpoint(self, azure_endpoint: str | None) -> str:
        resolved = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        if resolved is None:
            raise ValueError(
                "azure_endpoint is required for Azure OpenAI client. "
                "Set it via argument or AZURE_OPENAI_ENDPOINT environment variable."
            )
        return resolved

    def _resolve_api_version(self, api_version: str | None) -> str:
        return api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

    def _resolve_azure_deployment(self, azure_deployment: str | None) -> str | None:
        return azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        azure_endpoint: str | None = None,
        api_version: str | None = None,
        azure_deployment: str | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_model_name = model_name or "gpt-4o"
        super().__init__(model_name=resolved_model_name, timeout=timeout)
        self.kwargs = kwargs

        resolved_api_key = self._resolve_api_key(api_key)
        resolved_azure_endpoint = self._resolve_azure_endpoint(azure_endpoint)
        resolved_api_version = self._resolve_api_version(api_version)
        resolved_azure_deployment = self._resolve_azure_deployment(azure_deployment)

        self.client = openai.AzureOpenAI(
            api_key=resolved_api_key,
            azure_endpoint=resolved_azure_endpoint,
            api_version=resolved_api_version,
            azure_deployment=resolved_azure_deployment,
            timeout=timeout or openai.NOT_GIVEN,
        )
        self.async_client = openai.AsyncAzureOpenAI(
            api_key=resolved_api_key,
            azure_endpoint=resolved_azure_endpoint,
            api_version=resolved_api_version,
            azure_deployment=resolved_azure_deployment,
            timeout=timeout or openai.NOT_GIVEN,
        )
        self.model_name = resolved_model_name
        self.azure_deployment = resolved_azure_deployment

        # Per-model usage tracking
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        if isinstance(prompt, str):
            messages: list[ChatCompletionMessageParam] = cast(
                list[ChatCompletionMessageParam], [{"role": "user", "content": prompt}]
            )
        else:
            messages = cast(list[ChatCompletionMessageParam], prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Azure OpenAI client.")

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
        )
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Azure OpenAI response did not include message content.")
        return content

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        if isinstance(prompt, str):
            messages: list[ChatCompletionMessageParam] = cast(
                list[ChatCompletionMessageParam], [{"role": "user", "content": prompt}]
            )
        else:
            messages = cast(list[ChatCompletionMessageParam], prompt)

        model = model or self.model_name
        if not model:
            raise ValueError("Model name is required for Azure OpenAI client.")

        response = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
        )
        self._track_cost(response, model)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Azure OpenAI response did not include message content.")
        return content

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
