"""
MCP Server Integration for RLM Architecture Enforcement

DEPRECATED: This module has been split into rlm.mcp_integration package.
Import from rlm.mcp_integration instead for better organization.

This file is kept for backward compatibility but re-exports from the new modules.
"""

# Re-export from new modular structure for backward compatibility
from rlm.mcp_integration import (
    MCPServerRLMIntegration,
    enforce_rlm_for_chat_completion,
    validate_mcp_request,
    validate_mcp_response,
)

__all__ = [
    "MCPServerRLMIntegration",
    "validate_mcp_request",
    "validate_mcp_response",
    "enforce_rlm_for_chat_completion",
]
