from typing import Any

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class MockLM(BaseLM):
    """Simple mock LM that echoes prompts."""

    def __init__(self) -> None:
        super().__init__(model_name="mock-model")

    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        return f"Mock response to: {prompt[:50]}"

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return self.completion(prompt)

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(
            model_usage_summaries={
                "mock-model": ModelUsageSummary(
                    total_calls=1, total_input_tokens=10, total_output_tokens=10
                )
            }
        )

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(total_calls=1, total_input_tokens=10, total_output_tokens=10)
