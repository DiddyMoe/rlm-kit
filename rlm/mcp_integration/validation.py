"""Request and response validation for MCP integration."""

import json
from typing import Any

from rlm.core.rlm_enforcement import RLMEnforcementError, get_agent_chat_enforcer, get_mcp_enforcer


def is_ai_agent_request(request_data: dict[str, Any]) -> bool:
    """
    Determine if a request involves AI agent functionality that requires RLM architecture.

    Based on the RLM paper, any conversational AI interaction must use RLMs
    to handle long contexts and enable recursive reasoning.
    """
    request_str = json.dumps(request_data).lower()

    # Check for explicit AI agent indicators
    agent_indicators = [
        "agent",
        "chat",
        "conversation",
        "dialogue",
        "assistant",
        "reasoning",
        "analysis",
        "interactive",
        "tool",
        "function",
    ]

    # Check for LLM-related patterns that should use RLM
    llm_patterns = [
        "completion",
        "chat_completion",
        "generate",
        "prompt",
        "openai",
        "anthropic",
        "claude",
        "gpt",
        "llm",
    ]

    # Check for interface-specific patterns
    interface_patterns = [
        "github.copilot",
        "cursor.ai",
        "vscode.chat",
        "jetbrains.ai",
        "ai.agent",
        "copilot.chat",
    ]

    has_agent_context = any(indicator in request_str for indicator in agent_indicators)
    has_llm_context = any(pattern in request_str for pattern in llm_patterns)
    has_interface_context = any(pattern in request_str for pattern in interface_patterns)

    return has_agent_context or has_llm_context or has_interface_context


def detect_interface(request_data: dict[str, Any]) -> str | None:
    """
    Detect which chat interface is making the request.

    Args:
        request_data: The request data

    Returns:
        Interface identifier or None if not detected
    """
    request_str = json.dumps(request_data).lower()

    interface_map: dict[str, str] = {
        "github.copilot": "github.copilot.chat",
        "copilot": "github.copilot.chat",
        "cursor.ai": "cursor.ai.agent",
        "cursor": "cursor.ai.agent",
        "vscode.chat": "vscode.chat",
    }

    for key, interface in interface_map.items():
        if key in request_str:
            return interface

    return None


def validate_request_structure(request_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate MCP request structure and apply basic validation.

    Args:
        request_data: The MCP request data

    Returns:
        Validated request data

    Raises:
        RLMEnforcementError: If validation fails
    """
    # Validate with MCP enforcer
    mcp_enforcer = get_mcp_enforcer()
    validated_request = mcp_enforcer.validate_mcp_request(request_data)

    # Additional validation for chat interfaces
    interface = detect_interface(request_data)
    if interface:
        agent_chat_enforcer = get_agent_chat_enforcer()
        validated_request = agent_chat_enforcer.validate_chat_request(interface, validated_request)

    return validated_request


def validate_response_structure(response_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate MCP response structure.

    Args:
        response_data: The MCP response data

    Returns:
        Validated response data

    Raises:
        RLMEnforcementError: If validation fails
    """
    response_str = json.dumps(response_data).lower()

    # Check for direct LLM API calls in the response
    direct_llm_indicators = [
        "openai.chat.completions.create",
        "anthropic.messages.create",
        "client.completion(",
        "client.acompletion(",
        ".completion(",
        ".acompletion(",
    ]

    if any(indicator in response_str for indicator in direct_llm_indicators):
        # Check if it's within proper RLM context
        rlm_indicators = ["agentrlm", "rlm(", "environment="]
        has_rlm_context = any(indicator in response_str for indicator in rlm_indicators)

        if not has_rlm_context:
            raise RLMEnforcementError(
                "🚫 MCP Response Validation Failed: Direct LLM API calls detected outside RLM context.\n\n"
                "MCP server responses must use AgentRLM for all AI agent interactions. "
                "Direct LLM calls are forbidden and will be blocked at runtime.\n\n"
                "Use: agent = AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)"
            )

    return response_data
