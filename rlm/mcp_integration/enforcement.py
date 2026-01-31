"""RLM enforcement logic for MCP integration."""

import json
import re
from typing import Any

from rlm.core.rlm_enforcement import RLMEnforcementError, get_agent_chat_enforcer, get_mcp_enforcer
from rlm.mcp_integration.injection import inject_rlm_requirements
from rlm.mcp_integration.validation import (
    is_ai_agent_request,
    validate_request_structure,
    validate_response_structure,
)


class MCPServerRLMIntegration:
    """
    MCP Server Integration for RLM Enforcement

    This class provides methods that MCP servers can call to enforce
    RLM architecture usage for AI agent interactions.
    """

    def __init__(self) -> None:
        self.mcp_enforcer = get_mcp_enforcer()
        self.agent_chat_enforcer = get_agent_chat_enforcer()

    def validate_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate an MCP request for RLM compliance.

        Based on the RLM academic paper, this ensures that all AI agent interactions
        use proper RLM architecture to handle long contexts and prevent context rot.

        Args:
            request_data: The MCP request data

        Returns:
            Validated request data (may be modified to include RLM requirements)

        Raises:
            RLMEnforcementError: If the request violates RLM requirements
        """
        # Validate with MCP enforcer
        validated_request = validate_request_structure(request_data)

        # Comprehensive validation for AI agent requests
        if is_ai_agent_request(request_data):
            validated_request = self._enforce_comprehensive_rlm_usage(validated_request)

        return validated_request

    def _enforce_comprehensive_rlm_usage(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enforce comprehensive RLM usage for AI agent requests.

        This method ensures that all AI agent interactions use proper RLM architecture
        as mandated by the academic paper for handling long contexts and recursive reasoning.
        """
        # Check for direct LLM API calls (forbidden)
        if self._contains_direct_llm_calls(request_data):
            raise RLMEnforcementError(
                "🚫 DIRECT LLM CALL DETECTED IN MCP REQUEST\n\n"
                "CRITICAL SECURITY VIOLATION: Direct LLM API calls are forbidden for AI agent interactions.\n\n"
                "WHY THIS IS BLOCKED:\n"
                "- Direct LLM calls cannot handle arbitrarily long contexts (RLM paper shows 2+ orders of magnitude limitation)\n"
                "- Direct calls suffer from context rot degradation\n"
                "- Direct calls lack recursive reasoning capabilities\n"
                "- Direct calls cannot integrate tools properly\n\n"
                "MANDATORY SOLUTION: Use AgentRLM architecture:\n"
                "```python\n"
                "from rlm import AgentRLM\n"
                "agent = AgentRLM(\n"
                "    backend='openai',  # or 'anthropic', 'gemini'\n"
                "    environment='agent',  # MANDATORY\n"
                "    enable_tools=True,    # MANDATORY\n"
                "    enable_streaming=True # MANDATORY\n"
                ")\n"
                "async for chunk in agent.chat(message, stream=True):\n"
                "    print(chunk, end='')\n"
                "```\n\n"
                "See examples/agent_example.py and docs/content/reference/agents.md for complete documentation."
            )

        # Ensure RLM context is present
        if not self._has_rlm_context(request_data):
            request_data = inject_rlm_requirements(request_data)

        # Validate RLM configuration if present
        if self._has_rlm_context(request_data):
            self._validate_rlm_configuration(request_data)

        return request_data

    def _contains_direct_llm_calls(self, request_data: dict[str, Any]) -> bool:
        """Check if the request contains direct LLM API calls that bypass RLM architecture."""
        request_str = json.dumps(request_data).lower()

        # Direct LLM API call patterns (forbidden)
        direct_llm_patterns = [
            r"openai\.chat\.completions\.create",
            r"anthropic\.messages\.create",
            r"google\.generativeai\.generative_model",
            r"client\.completion\s*\(",
            r"client\.acompletion\s*\(",
            r"\.completion\s*\(",
            r"\.acompletion\s*\(",
            r"litellm\.completion",
            r"portkeyai\.completion",
        ]

        return any(re.search(pattern, request_str) for pattern in direct_llm_patterns)

    def _has_rlm_context(self, request_data: dict[str, Any]) -> bool:
        """
        Check if the request has proper RLM context and configuration.

        Optimized: Flattened conditionals with early returns.
        """
        request_str = json.dumps(request_data).lower()

        # Required RLM indicators
        rlm_indicators = [
            "agentrlm",
            "rlm(",
            "environment=",
            "enable_tools=",
            "enable_streaming=",
            "from rlm import",
        ]

        has_rlm = any(indicator in request_str for indicator in rlm_indicators)
        if not has_rlm:
            return False

        # Additional check for proper configuration (flattened)
        has_agent_env = "environment" in request_str and "agent" in request_str
        if not has_agent_env:
            return False

        has_tools = "enable_tools" in request_str and "true" in request_str
        if not has_tools:
            return False

        has_streaming = "enable_streaming" in request_str and "true" in request_str
        return has_streaming

    def _validate_rlm_configuration(self, request_data: dict[str, Any]) -> None:
        """Validate that RLM configuration meets the requirements from the academic paper."""
        request_str = json.dumps(request_data).lower()

        # Check for mandatory RLM parameters
        required_params = {
            "environment": "agent",
            "enable_tools": "true",
            "enable_streaming": "true",
        }

        missing_params = []
        for param, expected_value in required_params.items():
            if (
                f"{param}={expected_value}" not in request_str
                and f"{param} = {expected_value}" not in request_str
            ):
                missing_params.append(f"{param}={expected_value}")

        if missing_params:
            raise RLMEnforcementError(
                f"🚫 INVALID RLM CONFIGURATION IN MCP REQUEST\n\n"
                f"Missing required RLM parameters: {', '.join(missing_params)}\n\n"
                f"MANDATORY RLM CONFIGURATION (based on academic paper requirements):\n"
                f"```python\n"
                f"agent = AgentRLM(\n"
                f"    backend='openai',  # or 'anthropic', 'gemini'\n"
                f"    environment='agent',  # REQUIRED for recursive reasoning\n"
                f"    enable_tools=True,    # REQUIRED for tool integration\n"
                f"    enable_streaming=True # REQUIRED for real-time responses\n"
                f")\n"
                f"```\n\n"
                f"The RLM paper demonstrates that these parameters are essential for:\n"
                f"- Handling contexts 2+ orders of magnitude beyond model limits\n"
                f"- Enabling recursive reasoning and self-calls\n"
                f"- Preventing context rot degradation\n"
                f"- Maintaining conversation state and tool integration"
            )

    def validate_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate an MCP response for RLM compliance.

        Args:
            response_data: The MCP response data

        Returns:
            Validated response data

        Raises:
            RLMEnforcementError: If the response violates RLM requirements
        """
        return validate_response_structure(response_data)

    def enforce_rlm_for_chat_completion(self, messages: list, **kwargs) -> list:
        """
        Enforce RLM usage for chat completion requests.

        Based on the RLM academic paper, this ensures that all conversational AI
        interactions use proper RLM architecture for long-context processing.

        Args:
            messages: List of chat messages
            **kwargs: Additional request parameters

        Returns:
            Modified messages with RLM requirements injected
        """
        from rlm.mcp_integration.injection import enforce_rlm_for_chat_completion as _enforce

        return _enforce(messages, **kwargs)
