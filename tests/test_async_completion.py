from __future__ import annotations

import asyncio
from typing import Any

from rlm.clients.base_lm import BaseLM
from rlm.core.lm_handler import LMHandler
from rlm.core.types import ModelUsageSummary, UsageSummary


class AsyncMockLM(BaseLM):
    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        return f"sync:{prompt}"

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return f"async:{prompt}"

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(
            model_usage_summaries={
                self.model_name: ModelUsageSummary(
                    total_calls=1,
                    total_input_tokens=0,
                    total_output_tokens=0,
                )
            }
        )

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=0,
            total_output_tokens=0,
        )


class TestAsyncCompletion:
    def test_lm_handler_async_completion(self) -> None:
        lm = AsyncMockLM("mock")
        handler = LMHandler(lm)

        output = asyncio.run(handler.acompletion("hello"))
        assert output == "sync:hello"
