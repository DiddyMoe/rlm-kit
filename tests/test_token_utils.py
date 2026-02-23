"""Tests for rlm.utils.token_utils — model context limits and token counting."""

from rlm.utils.token_utils import (
    CHARS_PER_TOKEN_ESTIMATE,
    DEFAULT_CONTEXT_LIMIT,
    count_tokens,
    get_context_limit,
)


class TestGetContextLimit:
    def test_exact_match(self) -> None:
        assert get_context_limit("gpt-4o") == 128_000

    def test_containment_match(self) -> None:
        # "gpt-4o" is contained in "@openai/gpt-4o"
        assert get_context_limit("@openai/gpt-4o") == 128_000

    def test_longest_key_wins(self) -> None:
        # "gpt-4o-mini" (11 chars) should beat "gpt-4o" (6 chars)
        assert get_context_limit("gpt-4o-mini") == 128_000

    def test_unknown_model_returns_default(self) -> None:
        assert get_context_limit("unknown") == DEFAULT_CONTEXT_LIMIT

    def test_empty_string_returns_default(self) -> None:
        assert get_context_limit("") == DEFAULT_CONTEXT_LIMIT

    def test_no_match_returns_default(self) -> None:
        assert get_context_limit("totally-made-up-model-xyz") == DEFAULT_CONTEXT_LIMIT

    def test_anthropic_model(self) -> None:
        assert get_context_limit("claude-3-5-sonnet") == 200_000

    def test_gemini_model(self) -> None:
        assert get_context_limit("gemini-2.5-pro") == 1_000_000

    def test_gpt5(self) -> None:
        assert get_context_limit("gpt-5") == 272_000


class TestCountTokens:
    def test_empty_messages_returns_zero(self) -> None:
        assert count_tokens([], "gpt-4o") == 0

    def test_fallback_char_estimate(self) -> None:
        # Force fallback by using unknown model (no tiktoken match)
        messages = [{"role": "user", "content": "hello world"}]
        expected = (len("hello world") + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE
        assert count_tokens(messages, "unknown") == expected

    def test_multiple_messages_accumulate(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi there!"},
        ]
        total_chars = len("You are helpful.") + len("Hi there!")
        expected = (total_chars + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE
        assert count_tokens(messages, "unknown") == expected

    def test_none_content_treated_as_empty(self) -> None:
        messages: list[dict[str, str | None]] = [{"role": "user", "content": None}]
        assert count_tokens(messages, "unknown") == 0

    def test_returns_positive_for_non_empty(self) -> None:
        messages = [{"role": "user", "content": "x"}]
        assert count_tokens(messages, "unknown") > 0
