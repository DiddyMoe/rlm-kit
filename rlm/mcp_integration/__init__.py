"""
MCP Server Integration for RLM Architecture Enforcement

This module provides integration points for MCP servers (Cursor, VS Code extensions)
to enforce RLM architecture usage for all AI agent interactions.

Based on the academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601),
RLMs are critical for handling arbitrarily long contexts (up to 2+ orders of magnitude
beyond model context windows) and preventing context rot degradation.

MCP servers can import this module to validate and enforce RLM usage.
"""

import os
from typing import Any

from rlm.mcp_integration.enforcement import MCPServerRLMIntegration
from rlm.mcp_integration.injection import enforce_rlm_for_chat_completion

# Global integration instance
_mcp_integration = MCPServerRLMIntegration()


def validate_mcp_request(request_data: dict[str, Any]) -> dict[str, Any]:
    """
    Global function for MCP servers to validate requests.

    Args:
        request_data: MCP request data

    Returns:
        Validated request data

    Raises:
        RLMEnforcementError: If validation fails
    """
    return _mcp_integration.validate_request(request_data)


def validate_mcp_response(response_data: dict[str, Any]) -> dict[str, Any]:
    """
    Global function for MCP servers to validate responses.

    Args:
        response_data: MCP response data

    Returns:
        Validated response data

    Raises:
        RLMEnforcementError: If validation fails
    """
    return _mcp_integration.validate_response(response_data)


__all__ = [
    "MCPServerRLMIntegration",
    "validate_mcp_request",
    "validate_mcp_response",
    "enforce_rlm_for_chat_completion",
]

# Environment variable to enable/disable MCP enforcement
MCP_RLM_ENFORCEMENT_ENABLED = os.getenv("MCP_RLM_ENFORCEMENT_ENABLED", "true").lower() == "true"

if MCP_RLM_ENFORCEMENT_ENABLED:
    print("🔒 MCP RLM Integration: ENABLED")
    print("   MCP servers will enforce RLM architecture usage")
else:
    print("⚠️  MCP RLM Integration: DISABLED")
    print("   Set MCP_RLM_ENFORCEMENT_ENABLED=true to enable")
