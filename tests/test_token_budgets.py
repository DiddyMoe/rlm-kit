from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

from rlm.clients.base_lm import BaseLM
from rlm.core.comms_utils import LMRequest, send_lm_request
from rlm.core.lm_handler import LMHandler
from rlm.core.types import ModelUsageSummary, UsageSummary


class BudgetMockLM(BaseLM):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name=model_name)
        self._input_tokens: defaultdict[str, int] = defaultdict(int)
        self._output_tokens: defaultdict[str, int] = defaultdict(int)
        self._last_input_tokens = 0
        self._last_output_tokens = 0

    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        prompt_text = str(prompt)
        output = f"ok:{self.model_name}"
        input_tokens = max(1, len(prompt_text) // 4)
        output_tokens = max(1, len(output) // 4)
        self._input_tokens[self.model_name] += input_tokens
        self._output_tokens[self.model_name] += output_tokens
        self._last_input_tokens = input_tokens
        self._last_output_tokens = output_tokens
        return output

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return self.completion(prompt)

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(
            model_usage_summaries={
                self.model_name: ModelUsageSummary(
                    total_calls=1,
                    total_input_tokens=self._input_tokens[self.model_name],
                    total_output_tokens=self._output_tokens[self.model_name],
                )
            }
        )

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self._last_input_tokens,
            total_output_tokens=self._last_output_tokens,
        )


class TestTokenBudgets:
    def test_root_budget_enforced_on_direct_completion(self) -> None:
        root_client = BudgetMockLM("root-model")
        handler = LMHandler(root_client, max_root_tokens=2)

        with pytest.raises(RuntimeError, match="Token budget exceeded for root calls"):
            handler.completion("x" * 64)

    def test_sub_budget_enforced_for_socket_requests(self) -> None:
        root_client = BudgetMockLM("root-model")
        sub_client = BudgetMockLM("sub-model")

        with LMHandler(root_client, other_backend_client=sub_client, max_sub_tokens=2) as handler:
            response = send_lm_request(
                handler.address,
                LMRequest(prompt="x" * 64, depth=1),
            )

            assert response.success is False
            assert response.error is not None
            assert "Token budget exceeded for sub calls" in response.error
