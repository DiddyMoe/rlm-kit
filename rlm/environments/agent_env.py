"""
Agent Environment for AI Assistant Integration

This environment extends the local REPL to provide AI agents with:
- Tool execution capabilities
- Enhanced context management
- Streaming output support
- Agent-specific helper functions
"""

from collections.abc import Callable
from typing import Any

from rlm.core.types import REPLResult
from rlm.environments.agent_analysis import ReasoningHelper, TextAnalyzer
from rlm.environments.agent_context import ContextManager
from rlm.environments.agent_tools import ToolExecutor
from rlm.environments.local_repl import LocalREPL


class AgentEnvironment(LocalREPL):
    """
    Enhanced environment for AI agents with tool integration and advanced capabilities.
    """

    def __init__(
        self,
        lm_handler_address: tuple[str, int] | None = None,
        context_payload: dict[str, Any] | list[Any] | str | None = None,
        agent_context: dict[str, Any] | None = None,
        tools: dict[str, Callable[..., Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(lm_handler_address, context_payload, **kwargs)
        self.agent_context: dict[str, Any] = agent_context or {}
        self.tools: dict[str, Callable[..., Any]] = tools or {}
        self.streaming_enabled: bool = kwargs.get("streaming_enabled", False)
        self.output_buffer: list[str] = []

        # Initialize modular components
        self.tool_executor = ToolExecutor(self.tools, self.output_buffer)
        self.context_manager = ContextManager(self.agent_context, self.output_buffer)
        self.text_analyzer = TextAnalyzer(self.globals.get("llm_query", lambda x: ""))
        self.reasoning_helper = ReasoningHelper(self.globals.get("llm_query", lambda x: ""))

        self._setup_agent_globals()

    def _setup_agent_globals(self) -> None:
        """Set up enhanced global functions for AI agents.

        Optimized for local IDE integration - efficient function registration
        with minimal overhead for fast agent environment setup.
        """
        self.setup()

        # Update LLM query references in analyzers after setup
        llm_query_func: Callable[[str], str] = self.globals.get("llm_query", lambda x: "")
        self.text_analyzer.llm_query = llm_query_func
        self.reasoning_helper.llm_query = llm_query_func

        # Build agent functions dict efficiently
        agent_functions: dict[str, Any] = {
            "call_tool": self.tool_executor.call_tool,
            "get_agent_context": self.context_manager.get_agent_context,
            "search_context": self.context_manager.search_context,
            "add_to_context": self.context_manager.add_to_context,
            "analyze_text": self.text_analyzer.analyze_text,
            "extract_entities": self.text_analyzer.extract_entities,
            "stream_output": self._stream_output,
            "get_buffered_output": lambda: "".join(self.output_buffer),
            "reason_step_by_step": self.reasoning_helper.reason_step_by_step,
            "evaluate_options": self.reasoning_helper.evaluate_options,
            "make_decision": self.reasoning_helper.make_decision,
        }

        # Add summarize_context with proper closure
        def summarize_context(keys: list[str] | None = None) -> str:
            context_subset: dict[str, Any] = (
                {k: v for k, v in self.agent_context.items() if k in keys}
                if keys
                else self.agent_context
            )
            return self.text_analyzer.summarize_context(context_subset)

        agent_functions["summarize_context"] = summarize_context
        self.locals.update(agent_functions)

    def _stream_output(self, content: str) -> None:
        """Add content to streaming output buffer."""
        self.output_buffer.append(content)

    def execute_code(self, code: str) -> REPLResult:
        """Execute code with agent enhancements.

        Optimized for local IDE integration - efficient output buffering
        with minimal string concatenation overhead.
        """
        self.output_buffer.clear()
        result: REPLResult = super().execute_code(code)

        if self.output_buffer:
            buffered_output: str = "".join(self.output_buffer)
            result.stdout = f"{result.stdout}\n{buffered_output}"

        return result

    def cleanup(self) -> None:
        """Clean up agent-specific resources."""
        self.output_buffer = []
        super().cleanup()
