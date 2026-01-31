"""TypedDict definitions for gateway and agent interfaces."""

from typing import TypedDict


class AgentConfigDict(TypedDict, total=False):
    """Type definition for agent configuration."""

    backend: str
    backend_kwargs: dict[str, object]
    environment: str
    enable_tools: bool
    enable_streaming: bool


class ConversationContextDict(TypedDict, total=False):
    """Type definition for conversation context."""

    current_message: str
    conversation_history: list[dict[str, object]]
    available_tools: list[str]
    context_data: dict[str, object]
    additional_context: object


class ToolResultDict(TypedDict, total=False):
    """Type definition for tool execution results."""

    success: bool
    error: str
    content: str
    label: str
    warning: str


class SessionConfigDict(TypedDict, total=False):
    """Type definition for session configuration."""

    max_depth: int
    max_iterations: int
    max_tool_calls: int
    timeout_ms: int
    max_output_bytes: int


class BudgetDict(TypedDict, total=False):
    """Type definition for budget constraints."""

    max_depth: int
    max_iterations: int
    max_tool_calls: int
    max_output_bytes: int


class ConstraintsDict(TypedDict, total=False):
    """Type definition for execution constraints."""

    allowed_roots: list[str]
    max_span_size: int
