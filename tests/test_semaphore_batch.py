"""Tests for semaphore-bounded batched concurrency in LMHandler (RF-089)."""

import asyncio
from typing import Any
from unittest.mock import Mock

from rlm.core.comms_utils import LMRequest
from rlm.core.lm_handler import MAX_CONCURRENT_BATCH, LMRequestHandler
from rlm.core.types import ModelUsageSummary, UsageSummary


class TestMaxConcurrentBatchConstant:
    def test_value(self) -> None:
        assert MAX_CONCURRENT_BATCH == 16


class TestBatchedSemaphoreConcurrency:
    """Verify `handle_batched()` limits concurrency to `MAX_CONCURRENT_BATCH`."""

    def _make_mock_handler(self, client: Any) -> Mock:
        handler = Mock()
        handler.get_client.return_value = client
        handler.get_budget_error.return_value = None
        return handler

    def _make_mock_client(self, delay: float = 0.0) -> Mock:
        """Create a mock client that tracks max concurrent calls."""
        client = Mock()
        client.model_name = "test-model"
        client.get_last_usage.return_value = ModelUsageSummary(
            total_calls=1, total_input_tokens=5, total_output_tokens=5
        )
        client.get_usage_summary.return_value = UsageSummary(
            model_usage_summaries={
                "test-model": ModelUsageSummary(
                    total_calls=1, total_input_tokens=5, total_output_tokens=5
                )
            }
        )

        concurrent = {"current": 0, "max": 0}

        async def mock_acompletion(prompt: str | list[dict[str, Any]]) -> str:
            concurrent["current"] += 1
            if concurrent["current"] > concurrent["max"]:
                concurrent["max"] = concurrent["current"]
            if delay > 0:
                await asyncio.sleep(delay)
            concurrent["current"] -= 1
            return f"response-{prompt}"

        client.acompletion = mock_acompletion
        client._concurrent_tracker = concurrent
        return client

    def test_batched_respects_semaphore_limit(self) -> None:
        """With 32 prompts and a small delay, max concurrency should be <= 16."""
        client = self._make_mock_client(delay=0.01)
        handler = self._make_mock_handler(client)
        request_handler = LMRequestHandler.__new__(LMRequestHandler)

        request = LMRequest(
            prompt="",
            prompts=[f"prompt-{i}" for i in range(32)],
            model=None,
            depth=0,
        )

        response = request_handler.handle_batched(request, handler)

        assert response.error is None
        assert client._concurrent_tracker["max"] <= MAX_CONCURRENT_BATCH

    def test_batched_completes_all_prompts(self) -> None:
        """All prompts should get responses regardless of semaphore."""
        client = self._make_mock_client(delay=0.0)
        handler = self._make_mock_handler(client)
        request_handler = LMRequestHandler.__new__(LMRequestHandler)

        num_prompts = 50
        request = LMRequest(
            prompt="",
            prompts=[f"prompt-{i}" for i in range(num_prompts)],
            model=None,
            depth=0,
        )

        response = request_handler.handle_batched(request, handler)

        assert response.error is None
        assert response.chat_completions is not None
        assert len(response.chat_completions) == num_prompts

    def test_batched_missing_prompts(self) -> None:
        """Batched request with no prompts returns error."""
        handler = Mock()
        request_handler = LMRequestHandler.__new__(LMRequestHandler)

        request = LMRequest(
            prompt="",
            prompts=None,
            model=None,
            depth=0,
        )

        response = request_handler.handle_batched(request, handler)

        assert response.error is not None
        assert "Missing" in response.error
