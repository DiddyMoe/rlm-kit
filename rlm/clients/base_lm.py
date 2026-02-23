from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, cast

from rlm.core.types import ModelUsageSummary, UsageSummary


class BaseLM(ABC):
    """
    Base class for all language model routers / clients. When the RLM makes sub-calls, it currently
    does so in a model-agnostic way, so this class provides a base interface for all language models.
    """

    def __init__(self, model_name: str, timeout: float | None = None, **kwargs: Any) -> None:
        self.model_name = model_name
        self.timeout = timeout
        self.kwargs = kwargs

    @abstractmethod
    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_usage_summary(self) -> UsageSummary:
        """Get cost summary for all model calls."""
        raise NotImplementedError

    @abstractmethod
    def get_last_usage(self) -> ModelUsageSummary:
        """Get the last cost summary of the model."""
        raise NotImplementedError

    def stream_completion(
        self,
        prompt: str | list[dict[str, Any]],
        on_chunk: Callable[[str], None],
        model: str | None = None,
    ) -> str:
        """Stream completion text chunks when supported, else fall back to one-shot.

        Subclasses can override for provider-native streaming behavior.
        """
        if model is None:
            response = self.completion(prompt)
        else:
            try:
                completion_fn = cast(Any, self.completion)
                response = completion_fn(prompt, model=model)
            except TypeError:
                response = self.completion(prompt)
        if response:
            on_chunk(response)
        return response

    def get_total_tokens(self) -> int:
        """Get cumulative input+output tokens across all models tracked by this client."""
        summary = self.get_usage_summary()
        return sum(
            model_summary.total_input_tokens + model_summary.total_output_tokens
            for model_summary in summary.model_usage_summaries.values()
        )
