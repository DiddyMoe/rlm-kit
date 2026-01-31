"""Shared enforcement utilities and error messages for RLM architecture enforcement."""

from typing import Any


class EnforcementMessages:
    """Centralized error messages for RLM enforcement."""

    ACADEMIC_PAPER_REF = "https://arxiv.org/abs/2512.24601"

    @staticmethod
    def agent_environment_required(environment: str) -> str:
        """Error message for missing agent environment."""
        return (
            f"🚨 CRITICAL SECURITY VIOLATION: AI agents MUST use environment='agent'.\n\n"
            f"ACADEMIC PAPER EVIDENCE: {EnforcementMessages.ACADEMIC_PAPER_REF} - "
            f"RLMs handle contexts 2+ orders of magnitude beyond model limits\n\n"
            f"DETECTED: environment='{environment}' (INVALID)\n\n"
            f"WHY REQUIRED: The 'agent' environment provides tool integration, advanced reasoning "
            f"capabilities, conversation state management, and access to the RLM architecture "
            f"that handles arbitrarily long contexts. Direct LLM calls suffer from context rot.\n\n"
            f"SOLUTION: Always use environment='agent' for AI agents:\n"
            f"```python\n"
            f"agent = AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)\n"
            f"```\n\n"
            f"This requirement is MANDATORY and enforced at runtime to prevent context rot degradation."
        )

    @staticmethod
    def tools_required(enable_tools: bool) -> str:
        """Error message for missing tools."""
        return (
            f"🚨 CRITICAL SECURITY VIOLATION: AI agents MUST enable tools (enable_tools=True).\n\n"
            f"ACADEMIC PAPER EVIDENCE: {EnforcementMessages.ACADEMIC_PAPER_REF} - "
            f"RLMs provide tool integration during reasoning\n\n"
            f"DETECTED: enable_tools={enable_tools} (INVALID)\n\n"
            f"WHY REQUIRED: Tools are essential for agent functionality, enabling external "
            f"actions, data retrieval, computation, and interaction with the environment. "
            f"The academic paper demonstrates that RLMs with tool integration dramatically outperform direct LLMs.\n\n"
            f"SOLUTION: Always set enable_tools=True for AI agents:\n"
            f"```python\n"
            f"agent = AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)\n"
            f"```\n\n"
            f"This requirement is MANDATORY and enforced at runtime for proper tool integration."
        )

    @staticmethod
    def streaming_required(enable_streaming: bool) -> str:
        """Error message for missing streaming."""
        return (
            f"🚨 CRITICAL SECURITY VIOLATION: AI agents MUST enable streaming (enable_streaming=True).\n\n"
            f"ACADEMIC PAPER EVIDENCE: {EnforcementMessages.ACADEMIC_PAPER_REF} - "
            f"RLMs enable real-time conversational responses\n\n"
            f"DETECTED: enable_streaming={enable_streaming} (INVALID)\n\n"
            f"WHY REQUIRED: Streaming enables real-time conversational responses essential "
            f"for interactive AI agents. Non-streaming responses break the conversational "
            f"flow and user experience. The academic paper shows RLMs excel at conversational AI.\n\n"
            f"SOLUTION: Always set enable_streaming=True for AI agents:\n"
            f"```python\n"
            f"agent = AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)\n"
            f"```\n\n"
            f"This requirement is MANDATORY and enforced at runtime for conversational AI functionality."
        )

    @staticmethod
    def direct_llm_call_blocked(func_name: str) -> str:
        """Error message for blocked direct LLM calls."""
        return (
            f"🚫 DIRECT LLM CALL BLOCKED: {func_name}\n\n"
            f"CRITICAL SECURITY VIOLATION: Direct LLM API calls are forbidden outside RLM architecture.\n\n"
            f"REASON: RLM (Recursive Language Models) architecture must be used for all AI agent interactions "
            f"to enable proper recursive reasoning, tool integration, and long-context processing.\n\n"
            f"SOLUTION: Use AgentRLM for conversational AI:\n"
            f"```python\n"
            f"from rlm import AgentRLM\n"
            f"agent = AgentRLM(\n"
            f"    backend='openai',  # or anthropic, gemini, litellm\n"
            f"    environment='agent',  # MANDATORY\n"
            f"    enable_tools=True,    # MANDATORY\n"
            f"    enable_streaming=True # MANDATORY\n"
            f")\n"
            f"async for chunk in agent.chat('your message', stream=True):\n"
            f"    print(chunk, end='')\n"
            f"```\n\n"
            f"For more examples, see: examples/agent_example.py\n"
            f"For documentation, see: docs/content/reference/agents.md\n\n"
            f"This enforcement protects against context rot, ensures proper tool integration, "
            f"and enables the advanced reasoning capabilities required for modern AI agents."
        )


def extract_agent_config(agent: Any) -> dict[str, Any]:
    """Extract configuration from AgentRLM instance or dict.

    Args:
        agent: AgentRLM instance or configuration dict

    Returns:
        Configuration dictionary
    """
    from rlm.agent_rlm import AgentRLM

    if isinstance(agent, AgentRLM):
        return {
            "environment": agent.environment,
            "enable_tools": agent.enable_tools,
            "enable_streaming": agent.enable_streaming,
            "backend": getattr(agent, "backend", None),
            "backend_kwargs": getattr(agent, "backend_kwargs", {}),
        }
    elif isinstance(agent, dict):
        return agent
    else:
        raise TypeError(f"Agent must be AgentRLM instance or dict, got {type(agent)}")
