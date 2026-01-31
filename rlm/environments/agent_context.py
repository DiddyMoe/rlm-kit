"""Context management module for AgentEnvironment."""

import json
from typing import Any


class ContextManager:
    """Manages context data for agent environments."""

    def __init__(self, agent_context: dict[str, Any], output_buffer: list[str]) -> None:
        """Initialize context manager."""
        self.agent_context: dict[str, Any] = agent_context
        self.output_buffer: list[str] = output_buffer

    def get_agent_context(self) -> dict[str, Any]:
        """Get the full agent context."""
        return self.agent_context

    def search_context(self, query: str, context_key: str | None = None) -> list[str]:
        """Search through context data for relevant information."""
        results: list[str] = []
        context_data: dict[str, Any] = (
            self.agent_context[context_key]
            if context_key and context_key in self.agent_context
            else self.agent_context
        )
        query_lower: str = query.lower()
        for key, value in context_data.items():
            if isinstance(value, str) and query_lower in value.lower():
                results.append(f"{key}: {value}")
            elif isinstance(value, (list, dict)):
                value_str: str = json.dumps(value, indent=2)
                if query_lower in value_str.lower():
                    results.append(f"{key}: {value_str}")
        return results

    def add_to_context(self, key: str, value: Any) -> None:
        """Add information to the agent context."""
        self.agent_context[key] = value
        self.output_buffer.append(f"[CONTEXT ADDED] {key}: {value}\n")
