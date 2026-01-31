"""
LLM Interceptor MCP Tool

This MCP tool provides runtime interception and blocking of direct LLM calls
that bypass RLM architecture, ensuring all AI agent interactions use proper RLMs.

Based on the academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601),
direct LLM calls cannot handle the long contexts and recursive reasoning required for AI agents.
"""

import importlib
import inspect
import threading
from collections.abc import Callable
from typing import Any

from rlm.core.rlm_enforcement import RLMEnforcementError


class LLMInterceptorTool:
    """
    MCP Tool for intercepting and blocking direct LLM calls.

    This tool monitors all LLM API calls and ensures they only occur within
    proper RLM contexts, as mandated by the academic paper.
    """

    def __init__(self):
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

        self._intercepted_calls: list[dict[str, Any]] = []
        self._enforcement_enabled = True
        self._lock = threading.Lock()

    def enable_interception(self):
        """Enable LLM call interception and enforcement."""
        self._enforcement_enabled = True

    def disable_interception(self):
        """Disable LLM call interception (for debugging only)."""
        self._enforcement_enabled = False

    def intercept_llm_calls(self) -> dict[str, Any]:
        """
        Activate LLM call interception for the current session.

        Returns:
            Status of interception activation
        """
        try:
            self._apply_interceptors()
            return {
                "status": "success",
                "message": "LLM call interception activated",
                "blocked_modules": list(self._blocked_modules),
                "academic_paper_reference": "https://arxiv.org/abs/2512.24601",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to activate interception: {str(e)}",
                "error": str(e),
            }

    def get_intercepted_calls(self) -> list[dict[str, Any]]:
        """
        Get a list of all intercepted LLM calls.

        Returns:
            List of intercepted call records
        """
        with self._lock:
            return self._intercepted_calls.copy()

    def validate_call_context(self, func_name: str, *args, **kwargs) -> dict[str, Any]:
        """
        Validate that an LLM call is occurring in proper RLM context.

        Args:
            func_name: Name of the function being called
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Validation result
        """
        if not self._enforcement_enabled:
            return {"allowed": True, "reason": "enforcement_disabled"}

        # Check thread-local RLM context
        if self._is_in_rlm_context():
            return {"allowed": True, "reason": "in_rlm_context"}

        # Log the blocked call
        call_record = {
            "function": func_name,
            "args": str(args)[:200] + "..." if len(str(args)) > 200 else str(args),
            "kwargs": str(kwargs)[:200] + "..." if len(str(kwargs)) > 200 else str(kwargs),
            "call_stack": self._get_call_stack(),
            "timestamp": self._get_timestamp(),
            "reason": "direct_llm_call_outside_rlm",
        }

        with self._lock:
            self._intercepted_calls.append(call_record)

        return {
            "allowed": False,
            "reason": "direct_llm_call_blocked",
            "error_message": self._generate_blocked_call_error(func_name),
            "call_record": call_record,
        }

    def _is_in_rlm_context(self) -> bool:
        """Check if we're currently in an allowed RLM context."""
        frame = inspect.currentframe()
        try:
            found_rlm_context = False
            while frame:
                frame_locals = frame.f_locals

                # Check for AgentRLM instances
                if any("AgentRLM" in str(obj) for obj in frame_locals.values()):
                    found_rlm_context = True
                    break

                # Check for RLM core components
                if any("rlm.core" in str(obj) for obj in frame_locals.values()):
                    found_rlm_context = True
                    break

                # Check for LMHandler context
                if any("lm_handler" in str(obj) for obj in frame_locals.values()):
                    found_rlm_context = True
                    break

                # Check function names for RLM patterns
                if any("rlm" in name.lower() for name in frame_locals.keys()):
                    found_rlm_context = True
                    break

                frame = frame.f_back

            return found_rlm_context

        finally:
            del frame

    def _get_call_stack(self) -> list[str]:
        """Get a simplified call stack for debugging."""
        stack = []
        frame = inspect.currentframe()
        try:
            while frame and len(stack) < 5:  # Limit stack depth
                filename = frame.f_code.co_filename
                function = frame.f_code.co_name
                line = frame.f_lineno
                stack.append(f"{filename}:{line} in {function}")
                frame = frame.f_back
        finally:
            del frame

        return stack

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        import datetime

        return datetime.datetime.now().isoformat()

    def _generate_blocked_call_error(self, func_name: str) -> str:
        """Generate a detailed error message for blocked calls."""
        return (
            f"🚫 DIRECT LLM CALL BLOCKED: {func_name}\n\n"
            f"CRITICAL SECURITY VIOLATION: Direct LLM API calls are forbidden for AI agent interactions.\n\n"
            f"WHY THIS CALL IS BLOCKED:\n"
            f"- Direct LLM calls cannot handle arbitrarily long contexts (RLM paper limitation)\n"
            f"- Direct calls suffer from context rot degradation\n"
            f"- Direct calls lack recursive reasoning capabilities\n"
            f"- Direct calls cannot integrate tools properly\n\n"
            f"MANDATORY SOLUTION: Use AgentRLM architecture:\n"
            f"```python\n"
            f"from rlm import AgentRLM\n"
            f"agent = AgentRLM(\n"
            f"    backend='openai',  # or 'anthropic', 'gemini'\n"
            f"    environment='agent',  # MANDATORY: Enables recursive reasoning\n"
            f"    enable_tools=True,    # MANDATORY: Enables tool integration\n"
            f"    enable_streaming=True # MANDATORY: Enables real-time responses\n"
            f")\n"
            f"async for chunk in agent.chat(message, stream=True):\n"
            f"    print(chunk, end='')\n"
            f"```\n\n"
            f"ACADEMIC PAPER EVIDENCE: https://arxiv.org/abs/2512.24601\n"
            f"'RLMs successfully handle inputs up to two orders of magnitude beyond model context windows'\n\n"
            f"For complete examples, see: examples/agent_example.py\n"
            f"For documentation, see: docs/content/reference/agents.md\n\n"
            f"This enforcement protects against context rot and ensures advanced reasoning capabilities."
        )

    def _apply_interceptors(self):
        """Apply interceptors to all known LLM libraries."""
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
                if not hasattr(attr, "_rlm_intercepted"):
                    original_func = attr
                    intercepted_func = self._create_interceptor(
                        original_func, f"{module_name}.{attr_name}"
                    )
                    intercepted_func._rlm_original = original_func
                    intercepted_func._rlm_intercepted = True
                    setattr(module, attr_name, intercepted_func)

    def _create_interceptor(self, original_func: Callable, func_name: str) -> Callable:
        """Create an interceptor function for LLM calls."""

        def interceptor(*args, **kwargs):
            validation = self.validate_call_context(func_name, *args, **kwargs)
            if not validation["allowed"]:
                raise RLMEnforcementError(validation["error_message"])

            return original_func(*args, **kwargs)

        return interceptor

    def clear_intercepted_calls(self):
        """Clear the list of intercepted calls."""
        with self._lock:
            self._intercepted_calls.clear()

    def get_interception_stats(self) -> dict[str, Any]:
        """
        Get statistics about intercepted calls.

        Returns:
            Statistics about interception activity
        """
        with self._lock:
            total_calls = len(self._intercepted_calls)
            blocked_calls = len(
                [
                    call
                    for call in self._intercepted_calls
                    if call["reason"] == "direct_llm_call_blocked"
                ]
            )

            return {
                "total_intercepted_calls": total_calls,
                "blocked_calls": blocked_calls,
                "allowed_calls": total_calls - blocked_calls,
                "enforcement_enabled": self._enforcement_enabled,
                "blocked_modules": list(self._blocked_modules),
            }
