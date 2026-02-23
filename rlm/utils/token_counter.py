"""Token counting utilities for RLM token efficiency optimization."""

from typing import Any


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a string.

    Uses simple heuristic: ~4 characters per token (approximate for English text).
    For more accurate counting, use tiktoken or similar libraries.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Rough estimate: 4 characters per token (varies by language/model)
    return len(text) // 4


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """
    Estimate token count for a message dict.

    Args:
        message: Message dict with 'role' and 'content' keys

    Returns:
        Estimated token count
    """
    content = message.get("content", "")
    if isinstance(content, str):
        # Add ~2 tokens for role formatting
        return estimate_tokens(content) + 2
    return 2  # Minimal tokens for empty message


def estimate_prompt_tokens(prompt: str | list[dict[str, Any]]) -> int:
    """
    Estimate token count for a prompt (string or message list).

    Args:
        prompt: String prompt or list of message dicts

    Returns:
        Estimated token count
    """
    if isinstance(prompt, str):
        return estimate_tokens(prompt)
    return sum(estimate_message_tokens(msg) for msg in prompt)


def format_token_summary(
    total_tokens: int, input_tokens: int | None = None, output_tokens: int | None = None
) -> str:
    """
    Format token usage summary for display.

    Args:
        total_tokens: Total tokens used
        input_tokens: Input tokens (optional)
        output_tokens: Output tokens (optional)

    Returns:
        Formatted summary string
    """
    parts: list[str] = [f"Total: {total_tokens:,} tokens"]
    if input_tokens is not None:
        parts.append(f"Input: {input_tokens:,}")
    if output_tokens is not None:
        parts.append(f"Output: {output_tokens:,}")
    return " | ".join(parts)
