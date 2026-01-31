"""
Cost Calculator for RLM Budget Enforcement

This module provides cost calculation for different LLM providers and models.
Pricing data is based on publicly available pricing as of 2025-01-24.

R5 Compliance: Enables budget enforcement by calculating costs per model call.
"""

# Pricing data (USD per 1M tokens) - Updated 2025-01-24
# Format: (input_price_per_1M, output_price_per_1M)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI Models
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-16k": (3.00, 4.00),
    # Anthropic Models
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-3-7-sonnet-20250219": (3.00, 15.00),
    # Google Gemini Models
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-pro": (0.50, 1.50),
    # Default fallback (conservative estimate)
    "default": (5.00, 15.00),
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for a model call.

    Args:
        model_name: Name of the model
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    # Normalize model name (handle version suffixes, etc.)
    normalized_model = _normalize_model_name(model_name)

    # Get pricing
    if normalized_model in MODEL_PRICING:
        input_price, output_price = MODEL_PRICING[normalized_model]
    else:
        # Fallback to default pricing
        input_price, output_price = MODEL_PRICING["default"]

    # Calculate cost
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost

    return total_cost


def _normalize_model_name(model_name: str) -> str:
    """
    Normalize model name for pricing lookup.

    Handles:
    - Version suffixes (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
    - Case variations
    - Provider prefixes
    """
    if not model_name:
        return "default"

    model_lower = model_name.lower()

    # Handle OpenAI models with version suffixes
    if model_lower.startswith("gpt-4o"):
        return "gpt-4o"
    elif model_lower.startswith("gpt-4-turbo"):
        return "gpt-4-turbo"
    elif model_lower.startswith("gpt-4"):
        return "gpt-4"
    elif model_lower.startswith("gpt-3.5-turbo"):
        if "16k" in model_lower:
            return "gpt-3.5-turbo-16k"
        return "gpt-3.5-turbo"

    # Handle Anthropic models
    if model_lower.startswith("claude-3-5-sonnet"):
        return "claude-3-5-sonnet-20241022"  # Use latest pricing
    elif model_lower.startswith("claude-3-opus"):
        return "claude-3-opus-20240229"
    elif model_lower.startswith("claude-3-sonnet"):
        return "claude-3-sonnet-20240229"
    elif model_lower.startswith("claude-3-haiku"):
        return "claude-3-haiku-20240307"
    elif model_lower.startswith("claude-3-7-sonnet"):
        return "claude-3-7-sonnet-20250219"
    elif model_lower.startswith("claude"):
        # Fallback for other Claude models
        return "claude-3-5-sonnet-20241022"

    # Handle Gemini models
    if model_lower.startswith("gemini-1.5-pro"):
        return "gemini-1.5-pro"
    elif model_lower.startswith("gemini-1.5-flash"):
        return "gemini-1.5-flash"
    elif model_lower.startswith("gemini-pro"):
        return "gemini-pro"
    elif model_lower.startswith("gemini"):
        return "gemini-1.5-pro"  # Fallback

    # Check if exact match exists
    if model_lower in MODEL_PRICING:
        return model_lower

    # Return original (will use default pricing)
    return model_lower


def calculate_usage_cost(usage_summary) -> float:
    """
    Calculate total cost from a UsageSummary.

    Args:
        usage_summary: UsageSummary object with model usage data

    Returns:
        Total cost in USD
    """
    total_cost = 0.0

    for model_name, model_usage in usage_summary.model_usage_summaries.items():
        cost = calculate_cost(
            model_name,
            model_usage.total_input_tokens,
            model_usage.total_output_tokens,
        )
        total_cost += cost

    return total_cost
