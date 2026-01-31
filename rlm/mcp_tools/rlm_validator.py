"""
RLM Validator MCP Tool

This MCP tool validates that code and configurations use proper RLM architecture
for AI agent interactions, based on the academic paper requirements.

The academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601)
demonstrates that RLMs are essential for handling arbitrarily long contexts.
"""

import re
from typing import Any


class RLMValidatorTool:
    """
    MCP Tool for validating RLM architecture usage in code.

    This tool analyzes code to ensure it follows proper RLM patterns
    for AI agent interactions as mandated by the academic paper.
    """

    def __init__(self):
        self.forbidden_patterns = [
            # Direct LLM API calls
            r"openai\.ChatCompletion\.create",
            r"anthropic\.messages\.create",
            r"google\.generativeai\.GenerativeModel",
            r"client\.completion\s*\(",
            r"client\.acompletion\s*\(",
            r"\.completion\s*\(",
            r"\.acompletion\s*\(",
            # Direct LLM client instantiation without RLM context
            r"openai\.OpenAI\s*\(",
            r"anthropic\.Anthropic\s*\(",
            r"google\.generativeai\.configure",
        ]

        self.required_rlm_patterns = [
            r"from rlm import AgentRLM",
            r"rlm\.AgentRLM",
            r'environment\s*=\s*[\'""]agent[\'""]',
            r"enable_tools\s*=\s*True",
            r"enable_streaming\s*=\s*True",
        ]

    def validate_code_for_rlm_compliance(self, code: str) -> dict[str, Any]:
        """
        Validate code for RLM architecture compliance.

        Args:
            code: The code to validate

        Returns:
            Validation result with compliance status and issues
        """
        issues = []
        is_compliant = True

        # Check for forbidden direct LLM calls
        for pattern in self.forbidden_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                issues.append(
                    {
                        "type": "forbidden_direct_llm_call",
                        "pattern": pattern,
                        "matches": matches,
                        "severity": "critical",
                        "message": f"🚫 FORBIDDEN: Direct LLM API call detected: {pattern}",
                        "solution": "Use AgentRLM instead: agent = AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)",
                    }
                )
                is_compliant = False

        # Check for required RLM patterns in AI agent code
        has_agent_code = self._detect_ai_agent_code(code)
        if has_agent_code:
            rlm_compliance = self._check_rlm_compliance(code)
            if not rlm_compliance["compliant"]:
                issues.extend(rlm_compliance["issues"])
                is_compliant = False

        # Additional validation for chat interfaces
        if self._contains_chat_interface(code):
            chat_validation = self._validate_chat_interface(code)
            if not chat_validation["compliant"]:
                issues.extend(chat_validation["issues"])
                is_compliant = False

        return {
            "compliant": is_compliant,
            "issues": issues,
            "recommendations": self._generate_recommendations(issues),
            "academic_paper_reference": "https://arxiv.org/abs/2512.24601",
        }

    def _detect_ai_agent_code(self, code: str) -> bool:
        """Detect if code contains AI agent functionality."""
        agent_indicators = [
            "agent",
            "chat",
            "conversation",
            "dialogue",
            "assistant",
            "reasoning",
            "analysis",
            "interactive",
            "tool",
            "llm",
        ]

        code_lower = code.lower()
        return any(indicator in code_lower for indicator in agent_indicators)

    def _check_rlm_compliance(self, code: str) -> dict[str, Any]:
        """Check if AI agent code complies with RLM requirements."""
        issues = []

        # Must import AgentRLM
        if not re.search(r"from rlm import AgentRLM", code):
            issues.append(
                {
                    "type": "missing_agentrlm_import",
                    "severity": "critical",
                    "message": "🚫 MISSING: Must import AgentRLM for AI agent code",
                    "solution": "Add: from rlm import AgentRLM",
                }
            )

        # Must use environment='agent'
        if not re.search(r'environment\s*=\s*[\'""]agent[\'""]', code):
            issues.append(
                {
                    "type": "missing_agent_environment",
                    "severity": "critical",
                    "message": "🚫 MISSING: Must use environment='agent' for AI agents",
                    "solution": "Add: environment='agent' (required for recursive reasoning)",
                }
            )

        # Must enable tools
        if not re.search(r"enable_tools\s*=\s*True", code):
            issues.append(
                {
                    "type": "missing_tools_enabled",
                    "severity": "critical",
                    "message": "🚫 MISSING: Must set enable_tools=True for AI agents",
                    "solution": "Add: enable_tools=True (required for tool integration)",
                }
            )

        # Must enable streaming
        if not re.search(r"enable_streaming\s*=\s*True", code):
            issues.append(
                {
                    "type": "missing_streaming_enabled",
                    "severity": "critical",
                    "message": "🚫 MISSING: Must set enable_streaming=True for AI agents",
                    "solution": "Add: enable_streaming=True (required for real-time responses)",
                }
            )

        return {"compliant": len(issues) == 0, "issues": issues}

    def _contains_chat_interface(self, code: str) -> bool:
        """Check if code contains chat interface functionality."""
        chat_indicators = [
            "chat",
            "conversation",
            "dialogue",
            "message",
            "stream",
            "async for",
            "chat_completion",
            "streaming",
        ]

        code_lower = code.lower()
        return any(indicator in code_lower for indicator in chat_indicators)

    def _validate_chat_interface(self, code: str) -> dict[str, Any]:
        """Validate chat interface implementation."""
        issues = []

        # Must use agent.chat() with stream=True
        if not re.search(r"agent\.chat\s*\([^)]*stream\s*=\s*True", code):
            issues.append(
                {
                    "type": "invalid_chat_usage",
                    "severity": "critical",
                    "message": "🚫 INVALID: Chat interfaces must use agent.chat(message, stream=True)",
                    "solution": "Use: async for chunk in agent.chat(message, stream=True): print(chunk, end='')",
                }
            )

        return {"compliant": len(issues) == 0, "issues": issues}

    def _generate_recommendations(self, issues: list[dict[str, Any]]) -> list[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []

        if any(issue["type"] == "forbidden_direct_llm_call" for issue in issues):
            recommendations.append(
                "Replace direct LLM calls with AgentRLM architecture for proper long-context processing"
            )

        if any(
            issue["type"]
            in [
                "missing_agentrlm_import",
                "missing_agent_environment",
                "missing_tools_enabled",
                "missing_streaming_enabled",
            ]
            for issue in issues
        ):
            recommendations.append(
                "Use the mandatory AgentRLM configuration: AgentRLM(backend='openai', environment='agent', enable_tools=True, enable_streaming=True)"
            )

        if any(issue["type"] == "invalid_chat_usage" for issue in issues):
            recommendations.append(
                "Implement chat interfaces using: async for chunk in agent.chat(message, stream=True)"
            )

        return recommendations

    def validate_file_for_rlm_compliance(self, file_path: str, file_content: str) -> dict[str, Any]:
        """
        Validate a file for RLM compliance.

        Args:
            file_path: Path to the file
            file_content: Content of the file

        Returns:
            Validation result
        """
        result = self.validate_code_for_rlm_compliance(file_content)
        result["file_path"] = file_path

        # Add file-specific recommendations
        if file_path.endswith((".py", ".ipynb", ".ts", ".js")):
            result["file_type"] = "code"
        else:
            result["file_type"] = "other"

        return result
