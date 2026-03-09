from typing import Any

from rlm.utils.rlm_utils import filter_sensitive_keys


class TestFilterSensitiveKeys:
    def test_filters_api_key_patterns(self) -> None:
        raw: dict[str, Any] = {
            "api_key": "secret",
            "openai_api_key": "secret",
            "myApiKey": "secret",
            "timeout": 30,
        }

        filtered = filter_sensitive_keys(raw)

        assert "api_key" not in filtered
        assert "openai_api_key" not in filtered
        assert "myApiKey" not in filtered
        assert filtered["timeout"] == 30

    def test_keeps_non_sensitive_keys(self) -> None:
        raw: dict[str, Any] = {
            "model": "gpt-4o",
            "base_url": "https://example.com",
            "token_budget": 5000,
            "apiVersion": "v1",
        }

        filtered = filter_sensitive_keys(raw)

        assert filtered == raw
