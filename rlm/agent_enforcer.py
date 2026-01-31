"""
RLM Architecture Enforcement for AI Agents

This module provides decorators and utilities to ensure that RLM architecture
is always used for AI agent chats and conversations.
"""

from typing import Any, TypeVar

from rlm.core.rlm_enforcement import RLMEnforcementError
from rlm.core.types_gateway import AgentConfigDict

F = TypeVar("F")

# Re-export for convenience
__all__ = [
    "AgentRLMValidator",
    "create_enforced_agent",
    "enforce_no_direct_llm_calls",
    "require_agent_environment",
    "RLMEnforcementError",
]


class AgentRLMValidator:
    """
    Validator to ensure proper AgentRLM configuration for AI agents.
    """

    @staticmethod
    def validate_agent_config(agent_config: AgentConfigDict) -> None:
        """Validate that an AgentRLM configuration is properly set up."""
        # Check required fields
        if agent_config.get("environment") != "agent":
            raise RLMEnforcementError(
                f"AgentRLM requires environment='agent', got environment='{agent_config.get('environment')}'"
            )

        if not agent_config.get("enable_tools", False):
            raise RLMEnforcementError("AgentRLM requires enable_tools=True for tool integration")

        if not agent_config.get("enable_streaming", False):
            raise RLMEnforcementError(
                "AgentRLM requires enable_streaming=True for real-time responses"
            )

    @staticmethod
    def validate_chat_usage(
        func_name: str, stream: bool | None = None, message: str | None = None
    ) -> None:
        """Validate that chat functions are used properly."""
        if stream is False:
            raise RLMEnforcementError(
                f"{func_name}() requires stream=True for agent chats. "
                "Streaming is mandatory for conversational AI interfaces."
            )


def require_agent_environment(func: F) -> F:
    """
    Decorator to ensure agent functions require the 'agent' environment.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Check if environment is set to 'agent' (flattened conditional)
        if "environment" in kwargs and kwargs["environment"] != "agent":
            raise RLMEnforcementError(
                f"Agent function {func.__name__} requires environment='agent'. "
                f"Got environment='{kwargs['environment']}'"
            )
        return func(*args, **kwargs)

    return wrapper


def create_enforced_agent(
    backend: str = "openai",
    backend_kwargs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """
    Create an AgentRLM instance with guaranteed RLM compliance.

    This function ensures proper configuration for IDE integration:
    - environment='agent' (mandatory)
    - enable_tools=True (mandatory)
    - enable_streaming=True (mandatory)

    Args:
        backend: LM backend name (default: "openai")
        backend_kwargs: Backend configuration dict
        **kwargs: Additional AgentRLM arguments

    Returns:
        Properly configured AgentRLM instance
    """
    # Lazy import to avoid circular dependency
    from rlm.agent_rlm import AgentRLM

    # Enforce mandatory configuration
    kwargs.setdefault("environment", "agent")
    kwargs.setdefault("enable_tools", True)
    kwargs.setdefault("enable_streaming", True)

    # Validate configuration
    agent_config: AgentConfigDict = {
        "backend": backend,
        "backend_kwargs": backend_kwargs or {},
        "environment": kwargs["environment"],
        "enable_tools": kwargs["enable_tools"],
        "enable_streaming": kwargs["enable_streaming"],
    }
    AgentRLMValidator.validate_agent_config(agent_config)

    return AgentRLM(backend=backend, backend_kwargs=backend_kwargs, **kwargs)


def enforce_no_direct_llm_calls() -> None:
    """
    Enable comprehensive LLM call enforcement.

    Integrates with rlm.core.rlm_enforcement for system-level blocking.
    """
    # Import and enable the comprehensive enforcement system
    from rlm.core.rlm_enforcement import enable_rlm_enforcement

    enable_rlm_enforcement()

    print("🔒 RLM Architecture Enforcement: ENABLED")
    print("   Direct LLM calls are now blocked outside RLM context")
    print("   All AI agent interactions must use AgentRLM")
    print("   MCP servers will enforce RLM usage")
