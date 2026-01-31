"""
RLM Architecture Enforcement System

This module provides comprehensive enforcement of RLM architecture usage.
It intercepts all LLM API calls and ensures they only occur within proper RLM contexts.

Key Components:
- LLM Call Interceptor: Blocks direct LLM calls outside RLM context
- RLM Context Validator: Validates proper RLM usage patterns
- MCP Server Integration: Forces RLM usage in MCP server responses
- Agent Chat Enforcer: Ensures conversational AI uses RLM architecture
"""

import functools
import importlib
import inspect
import socket
import subprocess
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

from rlm.core.enforcement_common import EnforcementMessages


# Lazy import to avoid circular dependency
def _get_agent_rlm_class():
    """Lazy import AgentRLM to avoid circular imports."""
    from rlm.agent_rlm import AgentRLM

    return AgentRLM


F = TypeVar("F", bound=Callable[..., Any])


class RLMEnforcementError(Exception):
    """Raised when RLM architecture enforcement is violated."""

    pass


class RLMContext:
    """Thread-local context for tracking RLM usage."""

    _local = threading.local()

    @classmethod
    def get_current_context(cls) -> str | None:
        """Get the current RLM context for this thread."""
        return getattr(cls._local, "context", None)

    @classmethod
    @contextmanager
    def set_context(cls, context: str):
        """Set the RLM context for the current thread."""
        old_context = getattr(cls._local, "context", None)
        cls._local.context = context
        try:
            yield
        finally:
            cls._local.context = old_context

    @classmethod
    def is_in_rlm_context(cls) -> bool:
        """Check if we're currently in an allowed RLM context."""
        context = cls.get_current_context()
        return context in ["agent_rlm", "lm_handler", "rlm_core"]


class NetworkCallBlocker:
    """
    Blocks direct network calls to model APIs.

    Implements deny-by-default network access, allowing only RLM-authorized
    connections. Based on the principle that direct model API calls bypass
    RLM's context handling and violate the academic paper requirements.
    """

    def __init__(self):
        self._blocked_endpoints = {
            "api.openai.com",
            "api.anthropic.com",
            "generativelanguage.googleapis.com",
            "api.portkey.ai",
            "api.together.xyz",
            "api.replicate.com",
            "huggingface.co",
            "api-inference.huggingface.co",
            # Local model servers
            "localhost:8000",
            "localhost:5000",
            "127.0.0.1:8000",
            "127.0.0.1:5000",
        }
        self._allowed_endpoints = set()  # RLM gateway endpoints would go here
        self._enforcement_enabled = True
        self._original_socket_connect = None

    def enable_enforcement(self):
        """Enable network call blocking."""
        if self._enforcement_enabled and self._original_socket_connect is None:
            self._original_socket_connect = socket.socket.connect
            socket.socket.connect = self._blocked_connect

    def disable_enforcement(self):
        """Disable network call blocking."""
        if self._original_socket_connect is not None:
            socket.socket.connect = self._original_socket_connect
            self._original_socket_connect = None

    def _blocked_connect(self, sock, address):
        """Blocked socket connect that prevents model API calls."""
        host, port = address[0], address[1]

        # Check if this is a blocked endpoint
        for blocked in self._blocked_endpoints:
            if blocked in f"{host}:{port}":
                raise RLMEnforcementError(
                    f"🚫 NETWORK BLOCKED: Direct connection to model endpoint '{host}:{port}' forbidden.\n\n"
                    f"ACADEMIC PAPER EVIDENCE: https://arxiv.org/abs/2512.24601 - Direct API calls cannot handle "
                    f"long contexts and suffer from context rot.\n\n"
                    f"SOLUTION: All model calls must go through RLM interface:\n"
                    f"```python\n"
                    f"from rlm import RLM\n"
                    f"rlm = RLM(backend='openai')\n"
                    f"result = rlm.completion('your prompt')\n"
                    f"```"
                )

        # Allow non-blocked connections
        return self._original_socket_connect(sock, address)


class ProcessExecutionBlocker:
    """
    Blocks subprocess execution of model binaries and scripts.

    Prevents local model execution outside RLM environments. Local models
    cannot benefit from RLM's recursive context handling and violate
    the architecture requirements.
    """

    def __init__(self):
        self._blocked_binaries = {
            "ollama",
            "llama",
            "gpt4all",
            "lmstudio",
            "text-generation-webui",
            "koboldcpp",
            "oobabooga",
            "vllm",
            "ctransformers",
            "llama-cpp-python",
            "python",
            "python3",  # Could run model scripts
        }
        self._allowed_commands = set()  # Safe commands would go here
        self._enforcement_enabled = True
        self._original_subprocess_run = None
        self._original_subprocess_call = None
        self._original_subprocess_popen = None

    def enable_enforcement(self):
        """Enable subprocess blocking."""
        if not self._enforcement_enabled:
            return

        # Monkey patch subprocess functions (flattened)
        import subprocess

        if self._original_subprocess_run is None:
            self._original_subprocess_run = subprocess.run
            subprocess.run = self._blocked_run
        if self._original_subprocess_call is None:
            self._original_subprocess_call = subprocess.call
            subprocess.call = self._blocked_call
        if self._original_subprocess_popen is None:
            self._original_subprocess_popen = subprocess.Popen
            subprocess.Popen = self._blocked_popen

    def disable_enforcement(self):
        """Disable subprocess blocking."""
        if self._original_subprocess_run is not None:
            subprocess.run = self._original_subprocess_run
            self._original_subprocess_run = None
        if self._original_subprocess_call is not None:
            subprocess.call = self._original_subprocess_call
            self._original_subprocess_call = None
        if self._original_subprocess_popen is not None:
            subprocess.Popen = self._original_subprocess_popen
            self._original_subprocess_popen = None

    def _check_command_blocked(self, args):
        """Check if a command contains blocked binaries."""
        if isinstance(args, str):
            command_str = args
        elif isinstance(args, list):
            command_str = " ".join(str(arg) for arg in args)
        else:
            return False

        for binary in self._blocked_binaries:
            if binary in command_str.lower():
                return binary
        return False

    def _blocked_run(self, *args, **kwargs):
        """Blocked subprocess.run."""
        blocked_binary = self._check_command_blocked(args[0] if args else kwargs.get("args"))
        if blocked_binary:
            raise RLMEnforcementError(
                f"🚫 PROCESS BLOCKED: Subprocess execution of '{blocked_binary}' forbidden.\n\n"
                f"ACADEMIC PAPER EVIDENCE: https://arxiv.org/abs/2512.24601 - Local model execution "
                f"cannot benefit from RLM's recursive context handling.\n\n"
                f"SOLUTION: Use RLM with appropriate environment:\n"
                f"```python\n"
                f"from rlm import RLM\n"
                f"rlm = RLM(backend='openai', environment='local')\n"
                f"result = rlm.completion('your prompt')\n"
                f"```"
            )
        return self._original_subprocess_run(*args, **kwargs)

    def _blocked_call(self, *args, **kwargs):
        """Blocked subprocess.call."""
        blocked_binary = self._check_command_blocked(args[0] if args else kwargs.get("args"))
        if blocked_binary:
            raise RLMEnforcementError(
                f"🚫 PROCESS BLOCKED: Subprocess call to '{blocked_binary}' forbidden.\n"
                f"Use RLM environment instead."
            )
        return self._original_subprocess_call(*args, **kwargs)

    def _blocked_popen(self, *args, **kwargs):
        """Blocked subprocess.Popen."""
        blocked_binary = self._check_command_blocked(args[0] if args else kwargs.get("args"))
        if blocked_binary:
            raise RLMEnforcementError(
                f"🚫 PROCESS BLOCKED: Subprocess Popen of '{blocked_binary}' forbidden.\n"
                f"Use RLM environment instead."
            )
        return self._original_subprocess_popen(*args, **kwargs)


class LLMCallInterceptor:
    """
    Intercepts and validates all LLM API calls to ensure RLM architecture usage.

    This interceptor monitors all calls to LLM completion methods and blocks
    them unless they occur within proper RLM contexts.
    """

    def __init__(self):
        self._original_methods: dict[str, Callable] = {}
        self._blocked_modules: set[str] = {
            "openai",
            "anthropic",
            "google.generativeai",
            "google.genai",
            "litellm",
            "portkeyai",
            "azure.ai.inference",
            "azure.ai.ml",
            "together",
            "replicate",
            "huggingface_hub",
            "transformers",
        }
        self._blocked_functions: set[str] = {
            "completion",
            "acompletion",
            "chat_completion",
            "achat_completion",
            "generate_content",
            "generate_text",
            "create_completion",
            "create_chat_completion",
        }
        self._enforcement_enabled = True

    def enable_enforcement(self):
        """Enable LLM call interception and enforcement."""
        self._enforcement_enabled = True
        self._apply_interceptors()

    def disable_enforcement(self):
        """Disable LLM call interception (for debugging only)."""
        self._enforcement_enabled = False
        self._remove_interceptors()

    def _validate_call_context(self, func_name: str, *args, **kwargs) -> bool:
        """
        Validate that an LLM call is occurring in proper RLM context.

        Based on the academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601),
        direct LLM calls cannot handle long contexts and suffer from context rot.

        Returns True if the call is allowed, False otherwise.
        """
        if not self._enforcement_enabled:
            return True

        # Check thread-local RLM context
        if RLMContext.is_in_rlm_context():
            return True

        # Check call stack for RLM context with enhanced validation
        frame = inspect.currentframe()
        if frame is None:
            return False

        return self._check_frame_stack_for_rlm_context(frame)

    def _check_frame_stack_for_rlm_context(self, frame: Any) -> bool:
        """Check frame stack for RLM context indicators."""
        stack_depth = 0
        max_stack_depth = 20
        AgentRLM = _get_agent_rlm_class()

        while frame and stack_depth < max_stack_depth:
            if self._frame_has_rlm_context(frame, AgentRLM):
                return True
            frame = frame.f_back
            stack_depth += 1

        return False

    def _frame_has_rlm_context(self, frame: Any, AgentRLM: type) -> bool:
        """Check if a frame has RLM context indicators."""
        frame_locals = frame.f_locals
        frame_info = frame.f_code

        # Check for AgentRLM instances (most reliable indicator)
        if any(isinstance(obj, AgentRLM) for obj in frame_locals.values()):
            return True

        # Check for RLM core components or LMHandler context
        frame_str = str(frame_locals)
        if "rlm.core" in frame_str or "lm_handler" in frame_str:
            return True

        # Check for RLM-related function names
        if any("rlm" in name.lower() for name in frame_locals.keys()):
            return True

        # Check for RLM-related file paths
        if "rlm" in frame_info.co_filename.lower():
            return True

        # Check for proper agent environment context
        if "agent" in frame_str.lower() and "environment" in frame_str.lower():
            return True

        return False

    def _create_interceptor(self, original_func: Callable, func_name: str) -> Callable:
        """Create an interceptor function for LLM calls."""

        @functools.wraps(original_func)
        def interceptor(*args, **kwargs):
            if not self._validate_call_context(func_name, *args, **kwargs):
                raise RLMEnforcementError(EnforcementMessages.direct_llm_call_blocked(func_name))

            return original_func(*args, **kwargs)

        return interceptor

    def _apply_interceptors(self):
        """Apply interceptors to all known LLM libraries."""

        # Intercept rlm.clients.BaseLM methods first
        try:
            from rlm.clients.base_lm import BaseLM

            if hasattr(BaseLM, "completion"):
                self._original_methods["BaseLM.completion"] = BaseLM.completion
                BaseLM.completion = self._create_interceptor(BaseLM.completion, "BaseLM.completion")

            if hasattr(BaseLM, "acompletion"):
                self._original_methods["BaseLM.acompletion"] = BaseLM.acompletion
                BaseLM.acompletion = self._create_interceptor(
                    BaseLM.acompletion, "BaseLM.acompletion"
                )
        except ImportError:
            pass

        # Intercept common LLM libraries
        for module_name in self._blocked_modules:
            try:
                module = importlib.import_module(module_name)
                self._intercept_module_methods(module, module_name)
            except ImportError:
                continue

    def _intercept_module_methods(self, module, module_name: str):
        """Intercept methods in a specific module."""
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if callable(attr) and any(
                func in attr_name.lower() for func in self._blocked_functions
            ):
                if f"{module_name}.{attr_name}" not in self._original_methods:
                    self._original_methods[f"{module_name}.{attr_name}"] = attr
                    setattr(
                        module,
                        attr_name,
                        self._create_interceptor(attr, f"{module_name}.{attr_name}"),
                    )

    def _remove_interceptors(self):
        """Remove all interceptors and restore original methods."""
        for method_path, original_func in self._original_methods.items():
            module_name, attr_name = method_path.rsplit(".", 1)
            try:
                module = importlib.import_module(module_name)
                setattr(module, attr_name, original_func)
            except (ImportError, AttributeError):
                continue

        self._original_methods.clear()


class MCPRLMEnforcer:
    """
    MCP Server Integration for RLM Enforcement

    Ensures that MCP servers (Cursor, VS Code extensions) use RLM architecture
    for all AI agent interactions.
    """

    def __init__(self):
        self._enforcement_enabled = True

    def enable_enforcement(self):
        """Enable MCP RLM enforcement."""
        self._enforcement_enabled = True

    def disable_enforcement(self):
        """Disable MCP RLM enforcement."""
        self._enforcement_enabled = False

    def validate_mcp_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and enforce RLM usage for MCP requests.

        This function is called by MCP servers to validate that AI agent
        interactions use proper RLM architecture.
        """
        if not self._enforcement_enabled:
            return request_data

        # Check if this is an AI agent/chat request
        if self._is_ai_agent_request(request_data):
            self._enforce_rlm_for_request(request_data)

        return request_data

    def _is_ai_agent_request(self, request_data: dict[str, Any]) -> bool:
        """Check if a request involves AI agent functionality."""
        # Check for chat-related keywords
        chat_indicators = ["chat", "conversation", "dialogue", "agent", "assistant"]

        request_str = str(request_data).lower()
        return any(indicator in request_str for indicator in chat_indicators)

    def _enforce_rlm_for_request(self, request_data: dict[str, Any]):
        """Enforce RLM usage for AI agent requests."""
        # This would be called by MCP servers to validate requests
        # For now, we'll validate the request structure

        if "messages" in request_data:
            # This looks like a chat completion request
            self._validate_chat_request(request_data)

    def _validate_chat_request(self, request_data: dict[str, Any]):
        """Validate that chat requests use proper RLM patterns."""
        messages = request_data.get("messages", [])

        # Check if messages contain RLM usage instructions
        has_rlm_instruction = any(
            "rlm" in str(msg.get("content", "")).lower()
            and "agentrlm" in str(msg.get("content", "")).lower()
            for msg in messages
        )

        if not has_rlm_instruction:
            raise RLMEnforcementError(
                "MCP AI Agent Request Validation Failed: "
                "All AI agent interactions must use RLM architecture. "
                "Include AgentRLM usage instructions in your request."
            )


class AgentChatEnforcer:
    """
    Enforces RLM usage for conversational AI agents.

    This component ensures that chat interfaces (Github Copilot, Cursor AI Agent)
    use proper RLM architecture and cannot make direct LLM calls.
    """

    def __init__(self):
        self._enforcement_enabled = True
        self._blocked_chat_interfaces = {
            "github.copilot.chat",
            "cursor.ai.agent",
            "vscode.chat",
            "jetbrains.ai.chat",
        }

    def enable_enforcement(self):
        """Enable agent chat enforcement."""
        self._enforcement_enabled = True

    def disable_enforcement(self):
        """Disable agent chat enforcement."""
        self._enforcement_enabled = False

    def validate_chat_request(self, interface: str, request: dict[str, Any]) -> dict[str, Any]:
        """
        Validate chat requests from various interfaces.

        Args:
            interface: The chat interface making the request (e.g., 'github.copilot.chat')
            request: The chat request data

        Returns:
            Validated request data

        Raises:
            RLMEnforcementError: If the request violates RLM requirements
        """
        if not self._enforcement_enabled:
            return request

        if interface in self._blocked_chat_interfaces:
            self._enforce_rlm_for_chat(interface, request)

        return request

    def _enforce_rlm_for_chat(self, interface: str, request: dict[str, Any]):
        """Enforce RLM usage for chat interfaces."""
        # Check if the request already includes RLM context
        if self._has_rlm_context(request):
            return

        # Inject RLM requirements into the request
        self._inject_rlm_requirements(interface, request)

    def _has_rlm_context(self, request: dict[str, Any]) -> bool:
        """Check if a request already has proper RLM context."""
        request_str = str(request).lower()
        return (
            "agentrlm" in request_str
            and "environment" in request_str
            and "enable_tools" in request_str
            and "enable_streaming" in request_str
        )

    def _inject_rlm_requirements(self, interface: str, request: dict[str, Any]):
        """Inject RLM architecture requirements into a chat request."""
        rlm_instruction = (
            "\n\n--- RLM ARCHITECTURE REQUIREMENT ---\n"
            "CRITICAL: This is an RLM (Recursive Language Models) project.\n"
            "For ANY AI agent chat or conversation, you MUST use AgentRLM:\n\n"
            "```python\n"
            "from rlm import AgentRLM\n"
            "agent = AgentRLM(\n"
            "    backend='openai',  # or anthropic, gemini, etc.\n"
            "    environment='agent',  # MANDATORY\n"
            "    enable_tools=True,    # MANDATORY\n"
            "    enable_streaming=True # MANDATORY\n"
            ")\n"
            "async for chunk in agent.chat(message, stream=True):\n"
            "    print(chunk, end='')\n"
            "```\n\n"
            "NEVER use direct LLM API calls. Always use RLM architecture for conversations.\n"
            "See examples/agent_example.py for complete examples.\n"
            "--- END RLM REQUIREMENT ---\n"
        )

        # Inject into the request based on its structure (flattened)
        if "messages" in request:
            # Chat completion format
            messages = request["messages"]
            if not messages or not isinstance(messages[-1], dict):
                return
            last_message = messages[-1]
            if "content" in last_message:
                last_message["content"] += rlm_instruction
            return

        if "prompt" in request:
            # Single prompt format
            request["prompt"] += rlm_instruction
            return

        if "input" in request:
            # Alternative input format
            request["input"] += rlm_instruction
            return


# Global enforcement instances
_llm_interceptor = LLMCallInterceptor()
_network_blocker = NetworkCallBlocker()
_process_blocker = ProcessExecutionBlocker()
_mcp_enforcer = MCPRLMEnforcer()
_agent_chat_enforcer = AgentChatEnforcer()


def enable_rlm_enforcement():
    """Enable all RLM enforcement mechanisms."""
    _llm_interceptor.enable_enforcement()
    _network_blocker.enable_enforcement()
    _process_blocker.enable_enforcement()
    _mcp_enforcer.enable_enforcement()
    _agent_chat_enforcer.enable_enforcement()


def disable_rlm_enforcement():
    """Disable all RLM enforcement mechanisms (for debugging only)."""
    _llm_interceptor.disable_enforcement()
    _network_blocker.disable_enforcement()
    _process_blocker.disable_enforcement()
    _mcp_enforcer.disable_enforcement()
    _agent_chat_enforcer.disable_enforcement()


def get_llm_interceptor() -> LLMCallInterceptor:
    """Get the global LLM interceptor instance."""
    return _llm_interceptor


def get_network_blocker() -> NetworkCallBlocker:
    """Get the global network blocker instance."""
    return _network_blocker


def get_process_blocker() -> ProcessExecutionBlocker:
    """Get the global process blocker instance."""
    return _process_blocker


def get_mcp_enforcer() -> MCPRLMEnforcer:
    """Get the global MCP enforcer instance."""
    return _mcp_enforcer


def get_agent_chat_enforcer() -> AgentChatEnforcer:
    """Get the global agent chat enforcer instance."""
    return _agent_chat_enforcer


# Enforcement is enabled explicitly via enable_rlm_enforcement() call
# Auto-enablement removed to prevent issues during module loading
