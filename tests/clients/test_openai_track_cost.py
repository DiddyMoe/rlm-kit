"""Regression tests for OpenAI client usage tracking type compatibility."""

from typing import Any, cast
from unittest.mock import patch

from openai.types.chat import ChatCompletion

from rlm.clients.openai import OpenAIClient


def test_track_cost_accepts_chat_completion_instance() -> None:
    with (
        patch("rlm.clients.openai.openai.OpenAI"),
        patch("rlm.clients.openai.openai.AsyncOpenAI"),
    ):
        client = OpenAIClient(api_key="test-key", model_name="gpt-4o")

    response = ChatCompletion.model_validate(
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 123,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "ok"},
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
        }
    )

    assert isinstance(response, ChatCompletion)

    cast(Any, client)._track_cost(response, "gpt-4o")

    assert client.model_call_counts["gpt-4o"] == 1
    assert client.model_input_tokens["gpt-4o"] == 9
    assert client.model_output_tokens["gpt-4o"] == 4
