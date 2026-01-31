"""Tool execution module for AgentEnvironment."""

from collections.abc import Callable
from typing import Any


class ToolExecutor:
    """Handles tool execution for agent environments."""

    def __init__(self, tools: dict[str, Callable[..., Any]], output_buffer: list[str]) -> None:
        """Initialize tool executor."""
        self.tools: dict[str, Callable[..., Any]] = tools
        self.output_buffer: list[str] = output_buffer

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a registered tool."""
        if tool_name not in self.tools:
            raise ValueError(
                f"Tool '{tool_name}' not registered. Available tools: {list(self.tools.keys())}"
            )
        try:
            tool_func: Callable[..., Any] = self.tools[tool_name]
            result: Any = tool_func(**kwargs)
            self.output_buffer.append(f"[TOOL CALL] {tool_name}({kwargs}) -> {result}\n")
            return result
        except Exception as e:
            error_msg: str = f"Tool '{tool_name}' failed: {str(e)}"
            self.output_buffer.append(f"[TOOL ERROR] {error_msg}\n")
            raise
