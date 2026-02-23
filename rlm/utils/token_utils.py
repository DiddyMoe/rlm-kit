"""
Token counting and model context limits for compaction and context sizing.

Uses tiktoken for OpenAI-style models when available; otherwise estimates
with ~4 characters per token.
"""

import importlib
from typing import Any, cast

# Default context limit when model is unknown (tokens)
DEFAULT_CONTEXT_LIMIT = 128_000

# Characters per token when tokenizer is unavailable (conservative estimate)
CHARS_PER_TOKEN_ESTIMATE = 4

# Model context limits (max input context in tokens).
# Match: key contained in model_name (e.g. "gpt-4o" matches "@openai/gpt-4o").
# Longest matching key wins.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # OpenAI (GPT-5: 272k input, 128k reasoning+output)
    "gpt-5-nano": 272_000,
    "gpt-5": 272_000,
    "gpt-4o-mini": 128_000,
    "gpt-4o-2024": 128_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo-preview": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4-32k": 32_768,
    "gpt-4": 8_192,
    "gpt-3.5-turbo-16k": 16_385,
    "gpt-3.5-turbo": 16_385,
    "o1-mini": 128_000,
    "o1-preview": 128_000,
    "o1": 200_000,
    # Anthropic
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-2.1": 200_000,
    "claude-2": 100_000,
    # Gemini
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-1.5-pro": 1_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-1.0-pro": 30_720,
    # Qwen (Alibaba)
    "qwen3-max": 256_000,
    "qwen3-72b": 128_000,
    "qwen3-32b": 128_000,
    "qwen3-8b": 32_768,
    "qwen3": 128_000,
    # Kimi (Moonshot)
    "kimi-k2.5": 262_000,
    "kimi-k2-0905": 256_000,
    "kimi-k2-thinking": 256_000,
    "kimi-k2": 128_000,
    "kimi": 128_000,
    # GLM (Zhipu)
    "glm-4.6": 200_000,
    "glm-4-9b": 1_000_000,
    "glm-4": 128_000,
    "glm": 128_000,
}


def get_context_limit(model_name: str) -> int:
    """
    Return max context size in tokens for a model.

    Matches when the dict key is contained in model_name (e.g. "gpt-4o" matches
    "@openai/gpt-4o"). Longest matching key wins. Falls back to
    DEFAULT_CONTEXT_LIMIT for unknown models.
    """
    if not model_name or model_name == "unknown":
        return DEFAULT_CONTEXT_LIMIT
    exact = MODEL_CONTEXT_LIMITS.get(model_name)
    if exact is not None:
        return exact
    best = 0
    best_limit = DEFAULT_CONTEXT_LIMIT
    for key, limit in MODEL_CONTEXT_LIMITS.items():
        if key in model_name and len(key) > best:
            best = len(key)
            best_limit = limit
    return best_limit


def _count_tokens_tiktoken(messages: list[dict[str, Any]], model_name: str) -> int | None:
    """Count tokens with tiktoken if available. Returns None on failure."""
    try:
        tiktoken_module = importlib.import_module("tiktoken")
    except ImportError:
        return None

    tiktoken = tiktoken_module
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except Exception:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    return _tokens_for_messages(enc, messages)


def _tokens_for_messages(enc: Any, messages: list[dict[str, Any]]) -> int:
    total = 0
    # Approximate OpenAI message format overhead per message
    tokens_per_message = 3
    tokens_per_name = 1
    for m in messages:
        total += tokens_per_message
        total += _tokens_for_content(enc, m.get("content"))
        if m.get("name"):
            total += tokens_per_name
    return total


def _tokens_for_content(enc: Any, content: Any) -> int:
    if isinstance(content, str):
        return len(enc.encode(content))

    if isinstance(content, list):
        return _tokens_for_content_list(enc, cast(list[Any], content))

    if content is not None and content != "":
        return len(enc.encode(str(content)))

    return 0


def _tokens_for_content_list(enc: Any, content: list[Any]) -> int:
    total = 0
    for part in content:
        if isinstance(part, dict):
            part_dict = cast(dict[str, Any], part)
            if part_dict.get("type") == "text":
                total += len(enc.encode(part_dict.get("text", "") or ""))
    return total


def count_tokens(messages: list[dict[str, Any]], model_name: str) -> int:
    """
    Count tokens in a list of message dicts (role, content).

    Uses tiktoken for OpenAI-style models when the package is available;
    otherwise estimates with character length / CHARS_PER_TOKEN_ESTIMATE.
    """
    if not messages:
        return 0
    if model_name and model_name != "unknown":
        n = _count_tokens_tiktoken(messages, model_name)
        if n is not None:
            return n
    # Fallback: count chars (stringify in case content is not str, e.g. list)
    total_chars = 0
    for m in messages:
        raw = m.get("content", "") or ""
        total_chars += len(raw) if isinstance(raw, str) else len(str(raw))
    return (total_chars + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE
