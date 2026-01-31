"""
MCP Tools for RLM Architecture Enforcement

This module provides MCP tools that can validate RLM architecture usage
and enforce proper RLM patterns for AI agent interactions.

Based on the academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601),
these tools ensure that all AI agent interactions use proper RLM architecture.
"""

from .llm_interceptor import LLMInterceptorTool
from .rlm_validator import RLMValidatorTool

__all__ = ["RLMValidatorTool", "LLMInterceptorTool"]
