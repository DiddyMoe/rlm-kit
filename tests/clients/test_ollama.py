"""Tests for the Ollama client."""

from unittest.mock import patch

from rlm.clients.ollama import OllamaClient
from rlm.core.types import UsageSummary


class TestOllamaClientUnit:
    """Unit tests for OllamaClient usage tracking."""

    def test_get_usage_summary_after_completion(self) -> None:
        """Usage summary should expose tracked totals using ModelUsageSummary fields."""
        with patch("rlm.clients.ollama.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "response": "hello",
                "prompt_eval_count": 11,
                "eval_count": 7,
            }

            client = OllamaClient(model_name="llama3")
            result = client.completion("Hi")
            summary = client.get_usage_summary()

            assert result == "hello"
            assert isinstance(summary, UsageSummary)
            usage = summary.model_usage_summaries["llama3"]
            assert usage.total_calls > 0
            assert usage.total_input_tokens > 0
            assert usage.total_output_tokens > 0
