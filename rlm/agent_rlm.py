"""
AgentRLM: Conversational AI Agent Interface for Recursive Language Models

This module extends the core RLM functionality to support conversational AI agents
that can use RLMs for complex reasoning over long contexts while maintaining
conversation state and tool integration capabilities.
"""

import json
import re
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any, TypedDict

from rlm.agent_enforcer import AgentRLMValidator
from rlm.core.types_gateway import AgentConfigDict, ConversationContextDict
from rlm.logger import RLMLogger

# Optimize: Compile regex pattern once at module level (reused across all instances)
_SENTENCE_PATTERN = re.compile(r"([.!?]\s+)")


def _get_rlm_class() -> type:
    """Lazy import RLM to avoid circular imports."""
    from rlm.core.rlm import RLM

    return RLM


class MessageDict(TypedDict, total=False):
    """Type definition for conversation messages."""

    role: str
    content: str
    timestamp: float
    metadata: dict[str, Any]


class AgentContext:
    """Represents the context for an AI agent conversation.

    Optimized for local IDE integration:
    - Bounded conversation history to prevent memory growth
    - Efficient data structures for fast lookups
    - Memory-conscious context storage
    """

    def __init__(self, agent_id: str | None = None, max_history_size: int = 100) -> None:
        """Initialize agent context.

        Args:
            agent_id: Optional agent ID (auto-generated if None)
            max_history_size: Maximum conversation history entries (default: 100 for local IDE)
        """
        self.agent_id: str = agent_id or str(uuid.uuid4())
        self.conversation_history: list[MessageDict] = []
        self.context_data: dict[str, Any] = {}
        self.tools: dict[str, Callable[..., Any]] = {}
        self.metadata: dict[str, Any] = {}
        self.max_history_size: int = max_history_size

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a message to the conversation history.

        Optimized for local IDE: automatic history trimming to prevent memory growth.
        """
        message: MessageDict = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        self.conversation_history.append(message)

        # Optimize: Trim history if exceeds max size (memory-conscious)
        if len(self.conversation_history) > self.max_history_size:
            # Keep most recent messages (remove oldest)
            self.conversation_history = self.conversation_history[-self.max_history_size :]

    def add_context(self, key: str, data: Any) -> None:
        """Add context data that can be accessed during reasoning."""
        self.context_data[key] = data

    def register_tool(self, name: str, tool_func: Callable[..., Any]) -> None:
        """Register a tool that can be called during reasoning."""
        self.tools[name] = tool_func

    def get_recent_history(self, limit: int = 10) -> list[MessageDict]:
        """Get recent conversation history."""
        return self.conversation_history[-limit:] if limit > 0 else self.conversation_history

    def to_dict(self) -> dict[str, Any]:
        """Serialize context for persistence."""
        return {
            "agent_id": self.agent_id,
            "conversation_history": self.conversation_history,
            "context_data": self.context_data,
            "tools": list(self.tools.keys()),
            "metadata": self.metadata,
        }


class AgentRLM:
    """
    Conversational AI Agent interface for RLMs.

    Extends RLM functionality to support:
    - Real-time streaming responses
    - Conversation state persistence
    - Tool integration during reasoning
    - Multi-turn dialogue with context awareness
    """

    def __init__(
        self,
        backend: str = "openai",
        backend_kwargs: dict[str, Any] | None = None,
        environment: str = "agent",
        environment_kwargs: dict[str, Any] | None = None,
        max_depth: int = 1,
        max_iterations: int = 30,
        logger: RLMLogger | None = None,
        verbose: bool = False,
        agent_context: AgentContext | None = None,
        enable_tools: bool = True,
        enable_streaming: bool = True,
        max_tokens: int | None = None,
        max_cost: float | None = None,
    ) -> None:
        self.backend: str = backend
        self.backend_kwargs: dict[str, Any] = backend_kwargs or {}
        self.environment: str = environment
        self.environment_kwargs: dict[str, Any] = environment_kwargs or {}
        if max_depth != 1:
            raise ValueError(
                f"max_depth={max_depth} is not supported. Only max_depth=1 is currently implemented."
            )
        self.max_depth: int = 1
        self.max_iterations: int = max_iterations
        self.logger: RLMLogger | None = logger
        self.verbose: bool = verbose
        self.max_tokens: int | None = max_tokens
        self.max_cost: float | None = max_cost
        self.agent_context: AgentContext = agent_context or AgentContext()
        self.enable_tools: bool = enable_tools
        self.enable_streaming: bool = enable_streaming

        agent_config: AgentConfigDict = {
            "backend": backend,
            "backend_kwargs": backend_kwargs or {},
            "environment": environment,
            "enable_tools": enable_tools,
            "enable_streaming": enable_streaming,
        }
        AgentRLMValidator.validate_agent_config(agent_config)

        # Initialize RLM instance once for reuse (optimized for local IDE integration)
        # Uses persistent=False for clean state per conversation, but reuses RLM instance
        # for efficiency in local development environments
        RLM = _get_rlm_class()
        self.rlm = RLM(
            backend=backend,
            backend_kwargs=backend_kwargs,
            environment=environment,
            environment_kwargs=environment_kwargs,
            max_depth=max_depth,
            max_iterations=max_iterations,
            logger=logger,
            verbose=verbose,
            persistent=False,
            max_tokens=max_tokens,
            max_cost=max_cost,
        )
        # Cache system prompt and track when it needs rebuilding
        self._cached_tools_hash: int = hash(tuple(sorted(self.agent_context.tools.keys())))
        self._cached_context_count: int = len(self.agent_context.context_data)
        self.agent_system_prompt: str = self._build_agent_system_prompt()
        self.rlm.system_prompt = self.agent_system_prompt

    def _build_agent_system_prompt(self) -> str:
        """Build enhanced system prompt for AI agents using efficient string building."""
        tools_list: list[str] = list(self.agent_context.tools.keys())

        # Build context summary using list join pattern
        context_summary_parts: list[str] = [
            str(len(self.agent_context.conversation_history)),
            " messages, ",
            str(len(self.agent_context.context_data)),
            " context items",
        ]
        context_summary = "".join(context_summary_parts)

        # Build prompt using list join pattern (efficient)
        prompt_parts: list[str] = [
            "You are an AI assistant with access to Recursive Language Model (RLM) capabilities for complex reasoning over long contexts.\n\n",
            "Your capabilities:\n",
            "1. **RLM Reasoning**: You can use `rlm_reason()` to perform complex analysis over large contexts\n",
            "2. **Tool Integration**: You can call external tools using `call_tool(tool_name, **kwargs)`\n",
            "3. **Context Access**: You can access conversation history and stored context data\n",
            "4. **Streaming Responses**: Your responses can be streamed in real-time\n\n",
            "Available tools: ",
            str(tools_list),
            "\n\n",
            "Conversation context: ",
            context_summary,
            "\n\n",
            "When solving complex problems:\n",
            "1. Break down the task into manageable steps\n",
            "2. Use RLM reasoning for analysis of large contexts\n",
            "3. Call appropriate tools when needed\n",
            "4. Maintain conversation coherence across turns\n",
            "5. Provide clear, actionable responses\n\n",
            "Use FINAL(answer) when you have completed your response.",
        ]
        return "".join(prompt_parts)

    async def chat(
        self,
        message: str,
        context: str | dict[str, Any] | list[Any] | None = None,
        tools: dict[str, Callable[..., Any]] | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Main chat interface for AI agents.

        Args:
            message: The user's message
            context: Additional context data for reasoning
            tools: Additional tools to register for this conversation
            stream: Whether to stream the response

        Yields:
            Response chunks if streaming, or final response
        """
        AgentRLMValidator.validate_chat_usage("chat", stream=stream)
        self.agent_context.add_message("user", message)

        if tools:
            for name, tool_func in tools.items():
                self.agent_context.register_tool(name, tool_func)

        if context is not None:
            context_key = f"context_{len(self.agent_context.context_data)}"
            self.agent_context.add_context(context_key, context)

        conversation_context: dict[str, Any] = self._prepare_conversation_context(message, context)
        # Update system prompt only if tools or context changed (cached internally)
        self.agent_system_prompt = self._build_agent_system_prompt()
        self.rlm.system_prompt = self.agent_system_prompt

        try:
            result: dict[str, Any] = await self._execute_agent_reasoning(
                conversation_context, self.agent_system_prompt, stream=stream
            )
            self.agent_context.add_message("assistant", result["final_answer"])

            if stream:
                for chunk in result["chunks"]:
                    yield chunk
            else:
                yield result["final_answer"]
        except Exception as e:
            error_msg: str = f"I encountered an error during reasoning: {str(e)}"
            self.agent_context.add_message("assistant", error_msg, {"error": True})
            yield error_msg

    async def _execute_agent_reasoning(
        self, context: dict[str, Any], system_prompt: str, stream: bool = True
    ) -> dict[str, Any]:
        """Execute RLM reasoning with agent-specific enhancements.

        Optimized for local IDE integration - uses efficient completion path
        with minimal overhead for fast local development environments.
        """
        reasoning_prompt: str = self._create_reasoning_prompt(context)
        result = self.rlm.completion(reasoning_prompt)

        if stream:
            chunks = self._create_streaming_chunks(result.response)
        else:
            chunks = []

        return {
            "final_answer": result.response,
            "chunks": chunks,
            "usage": result.usage_summary,
            "execution_time": result.execution_time,
        }

    def _prepare_conversation_context(
        self, message: str, additional_context: Any = None
    ) -> ConversationContextDict:
        """Prepare conversation context for RLM reasoning."""
        context: dict[str, Any] = {
            "current_message": message,
            "conversation_history": self.agent_context.get_recent_history(5),
            "available_tools": list(self.agent_context.tools.keys()),
            "context_data": self.agent_context.context_data.copy(),
        }
        if additional_context:
            context["additional_context"] = additional_context
        return context

    def _create_reasoning_prompt(self, context: ConversationContextDict) -> str:
        """Create a comprehensive reasoning prompt for the RLM.

        Optimized for efficiency - builds prompt with minimal allocations.
        """
        prompt_parts: list[str] = [f"User Message: {context['current_message']}"]

        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            history_lines: list[str] = [
                f"{msg['role']}: {msg['content']}" for msg in conversation_history
            ]
            prompt_parts.append(f"Recent Conversation:\n{chr(10).join(history_lines)}")

        context_data = context.get("context_data", {})
        if context_data:
            context_lines: list[str] = []
            for key, value in context_data.items():
                if isinstance(value, (dict, list)):
                    value_str: str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)
                context_lines.append(f"{key}: {value_str}")
            prompt_parts.append(f"Available Context:\n{chr(10).join(context_lines)}")

        additional_context = context.get("additional_context")
        if additional_context:
            if isinstance(additional_context, (dict, list)):
                additional_text: str = json.dumps(additional_context, indent=2)
            else:
                additional_text = str(additional_context)
            prompt_parts.append(f"Additional Context:\n{additional_text}")

        available_tools = context.get("available_tools", [])
        if available_tools:
            tools_lines: list[str] = [
                f"- {tool}: Available for use with call_tool('{tool}', **kwargs)"
                for tool in available_tools
            ]
            prompt_parts.append(f"Available Tools:\n{chr(10).join(tools_lines)}")

        return f"{chr(10)}{chr(10)}".join(prompt_parts)

    def _create_streaming_chunks(self, text: str, chunk_size: int = 50) -> list[str]:
        """
        Create streaming chunks from text with sentence-aware chunking.

        Optimized for local IDE integration:
        - Sentence-aware chunking for natural streaming
        - Efficient regex compilation (module-level constant, reused)
        - Minimal allocations in hot path
        - Falls back to word boundaries for very short sentences
        """
        if not text:
            return []

        # Optimize: Use module-level compiled pattern (reused across all instances)
        sentences = _SENTENCE_PATTERN.split(text)

        # Recombine sentences with their punctuation (optimized list building)
        combined_sentences: list[str] = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i + 1])
            else:
                combined_sentences.append(sentences[i])

        chunks: list[str] = []
        current_chunk: str = ""

        for sentence in combined_sentences:
            # If sentence fits in current chunk, add it
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
            else:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk)
                # If sentence is longer than chunk_size, split by words
                if len(sentence) > chunk_size:
                    words = sentence.split()
                    for word in words:
                        word_with_space = f"{word} "
                        if len(current_chunk) + len(word_with_space) <= chunk_size:
                            current_chunk += word_with_space
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.rstrip())
                            current_chunk = word_with_space
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.rstrip())

        return chunks if chunks else [text]

    def add_context(self, key: str, data: Any) -> None:
        """Add context data for future conversations.

        Note: This will invalidate the cached system prompt on next chat call.
        """
        self.agent_context.add_context(key, data)
        # Invalidate prompt cache (will rebuild on next chat)
        self._cached_context_count = -1

    def register_tool(self, name: str, tool_func: Callable[..., Any]) -> None:
        """Register a tool for use during reasoning.

        Note: This will invalidate the cached system prompt on next chat call.
        """
        self.agent_context.register_tool(name, tool_func)
        # Invalidate prompt cache (will rebuild on next chat)
        self._cached_tools_hash = -1

    def get_conversation_history(self) -> list[MessageDict]:
        """Get the full conversation history."""
        return self.agent_context.conversation_history

    def save_context(self, filepath: str) -> None:
        """Save agent context to file."""
        with open(filepath, "w") as f:
            json.dump(self.agent_context.to_dict(), f, indent=2)

    def load_context(self, filepath: str) -> None:
        """Load agent context from file."""
        with open(filepath) as f:
            data: dict[str, Any] = json.load(f)
            self.agent_context = AgentContext(data["agent_id"])
            self.agent_context.conversation_history = data["conversation_history"]
            self.agent_context.context_data = data["context_data"]
            self.agent_context.metadata = data["metadata"]

    async def __aenter__(self) -> "AgentRLM":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        pass
