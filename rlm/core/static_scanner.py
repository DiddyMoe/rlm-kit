"""
Static Scanner for RLM Architecture Enforcement

This module provides static analysis tools to detect direct model calls and other
violations of RLM-only architecture. Used in CI/CD pipelines to prevent merges
that introduce direct LLM usage.

Based on the academic paper "Recursive Language Models" (https://arxiv.org/abs/2512.24601),
direct model calls cannot handle arbitrarily long contexts and suffer from context rot.
"""

import ast
import os
import re
from pathlib import Path


class RLMStaticScanner:
    """
    Static analysis scanner that detects violations of RLM-only architecture.

    Scans Python code for patterns that indicate direct model usage outside
    the canonical RLM interface.
    """

    def __init__(self):
        # Direct model API imports that are forbidden outside RLM gateway
        self._forbidden_imports = {
            # Cloud providers
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
            "torch",
            "tensorflow",
            "jax",
            # Local model runtimes
            "vllm",
            "llama_cpp",
            "ctransformers",
            "sentence_transformers",
            "accelerate",
            "peft",
            "bitsandbytes",
            "autoawq",
            "gptq",
            # Additional LLM libraries
            "langchain",
            "llamaindex",
            "crewai",
            "autogen",
            "camel",
            "metagpt",
        }

        # HTTP endpoints that indicate direct model API calls
        self._model_endpoints = {
            # Cloud APIs
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
            "localhost:11434",  # Ollama
            "localhost:1234",  # LM Studio
            "localhost:5001",  # Text generation webui
            "localhost:7860",  # Gradio
            "127.0.0.1:8000",
            "127.0.0.1:5000",
            "127.0.0.1:11434",
            "127.0.0.1:1234",
            "127.0.0.1:5001",
            "127.0.0.1:7860",
            # Common model API patterns
            "api.deepseek.com",
            "api.groq.com",
            "api.mistral.ai",
            "api.cohere.ai",
            "api.fireworks.ai",
        }

        # Subprocess calls that might invoke local models
        self._model_binaries = {
            # Python interpreters (could run model scripts)
            "python",
            "python3",
            "python3.8",
            "python3.9",
            "python3.10",
            "python3.11",
            "python3.12",
            # Local model servers
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
            "exllama",
            "autoawq",
            "gptq",
            # Model conversion tools
            "convert",
            "transformers-cli",
            # GPU acceleration tools
            "nvidia-smi",
            "nvcc",
        }

        # Native library bindings (FFI, ctypes, etc.)
        self._native_bindings = {
            "ctypes",
            "cffi",
            "llama_cpp",
            "ctransformers",
            "torch._C",
            "tensorflow.python",
            "jax._src",
        }

        # Direct API call patterns (regex)
        self._direct_api_patterns = [
            r"\bopenai\.chat\.completions\.create\b",
            r"\banthropic\.messages\.create\b",
            r"\bgoogle\.generativeai\.GenerativeModel\b",
            r"\bclient\.chat_completion\b",
            r"\bclient\.completion\b",
            r"\bclient\.acompletion\b",
            r"\.chat_completion\s*\(",
            r"\.completion\s*\(",
            r"\.acompletion\s*\(",
            r"\blitellm\.completion\b",
            r"\bportkeyai\.completion\b",
            r"\bhuggingface_hub\.InferenceApi\b",
            r"\btransformers\.pipeline\b",
            r"\btransformers\.AutoModelForCausalLM\b",
        ]

        # Dependency patterns that indicate model usage
        self._model_dependency_patterns = [
            r"pip install.*openai",
            r"pip install.*anthropic",
            r"pip install.*google-generativeai",
            r"pip install.*transformers",
            r"pip install.*torch",
            r"pip install.*tensorflow",
            r"pip install.*vllm",
            r"from.*openai import",
            r"from.*anthropic import",
            r"from.*google.generativeai import",
            r"import.*transformers",
            r"import.*torch",
            r"import.*tensorflow",
        ]

    def scan_file(self, filepath: str) -> list[dict[str, str]]:
        """
        Scan a single Python file for RLM violations.

        Args:
            filepath: Path to the Python file to scan

        Returns:
            List of violation dictionaries with keys: 'type', 'line', 'message', 'severity'
        """
        violations = []

        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return [
                {
                    "type": "file_error",
                    "line": "1",
                    "message": f"Could not read file {filepath}: {e}",
                    "severity": "error",
                }
            ]

        # File-level architectural checks
        violations.extend(self._scan_file_architecture(filepath, content))

        # Parse the AST for structural analysis
        try:
            tree = ast.parse(content, filepath)
            violations.extend(self._scan_ast(tree, filepath))
        except SyntaxError as e:
            violations.append(
                {
                    "type": "syntax_error",
                    "line": str(e.lineno or 1),
                    "message": f"Syntax error: {e}",
                    "severity": "error",
                }
            )

        # Scan for string patterns
        violations.extend(self._scan_content(content, filepath))

        return violations

    def _scan_file_architecture(self, filepath: str, content: str) -> list[dict[str, str]]:
        """
        Perform file-level architectural checks to ensure RLM-only compliance.
        """
        violations = []

        # Check for AI agent files that don't use RLM (but allow in examples/tests)
        if self._is_ai_agent_file(filepath) and not filepath.startswith(("examples/", "tests/")):
            if not self._uses_rlm_architecture(content):
                violations.append(
                    {
                        "type": "non_rlm_agent",
                        "line": "1",
                        "message": f"AI agent file '{filepath}' does not use RLM architecture. "
                        f"All AI agents must use AgentRLM with environment='agent'. "
                        f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                        "severity": "critical",
                    }
                )

        # Check for model client files outside RLM gateway (allow in tests)
        if self._is_model_client_file(filepath) and not filepath.startswith("tests/"):
            if not self._is_within_rlm_gateway(filepath):
                violations.append(
                    {
                        "type": "forbidden_model_client",
                        "line": "1",
                        "message": f"Model client file '{filepath}' exists outside RLM gateway. "
                        f"Model clients must only exist within rlm/clients/ directory. "
                        f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                        "severity": "critical",
                    }
                )

        # Only check for direct model usage in production code (not tests/examples)
        if not self._is_allowed_model_usage(filepath):
            # Only flag clear violations in production code
            if "from openai import" in content and "rlm/" not in filepath:
                violations.append(
                    {
                        "type": "direct_import_violation",
                        "line": "1",
                        "message": f"Direct model import found in production file '{filepath}'. "
                        f"Model libraries must only be used within RLM gateway. "
                        f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                        "severity": "critical",
                    }
                )

        return violations

    def _is_ai_agent_file(self, filepath: str) -> bool:
        """Check if a file appears to be an AI agent implementation."""
        indicators = [
            "agent",
            "chat",
            "conversation",
            "assistant",
            "interactive",
            "dialogue",
        ]
        filename = filepath.lower()
        return any(indicator in filename for indicator in indicators) and filepath.endswith(".py")

    def _uses_rlm_architecture(self, content: str) -> bool:
        """Check if content uses proper RLM architecture."""
        rlm_indicators = [
            "from rlm import AgentRLM",
            "AgentRLM(",
            "create_enforced_agent",
            "environment=",
            "enable_tools=",
            "enable_streaming=",
            "rlm.chat(",
            "rlm.completion(",
            "from rlm import",
        ]
        return any(indicator in content for indicator in rlm_indicators)

    def _is_model_client_file(self, filepath: str) -> bool:
        """Check if a file appears to be a model client implementation."""
        indicators = [
            "client",
            "model",
            "api",
            "openai",
            "anthropic",
            "gemini",
        ]
        filename = filepath.lower()
        return any(indicator in filename for indicator in indicators) and filepath.endswith(".py")

    def _is_within_rlm_gateway(self, filepath: str) -> bool:
        """Check if a file is within the allowed RLM gateway directories."""
        allowed_paths = [
            "rlm/clients/",
            "rlm/core/",
            "rlm/environments/",
            "rlm/mcp_tools/",
            "rlm/agent",  # Allow agent files
            "rlm/agent_",  # Allow agent files
        ]
        return any(allowed_path in filepath for allowed_path in allowed_paths)

    def _is_allowed_model_usage(self, filepath: str) -> bool:
        """
        Check if model usage is allowed in this file.

        Model usage is allowed in:
        1. RLM gateway directories (rlm/clients/, rlm/core/, etc.)
        2. Test files (they test client functionality)
        3. Examples (they demonstrate usage patterns)
        4. MCP integration validation code
        """
        # Allow in RLM gateway
        if self._is_within_rlm_gateway(filepath):
            return True

        # Allow in all test files (they need to test clients)
        if filepath.startswith("tests/"):
            return True

        # Allow in all example files (they demonstrate usage)
        if filepath.startswith("examples/"):
            return True

        # Allow MCP integration validation
        if "mcp_integration" in filepath:
            return True

        return False

    def _scan_ast(self, tree: ast.AST, filepath: str) -> list[dict[str, str]]:
        """Scan AST for structural violations."""
        violations = []

        class RLMVisitor(ast.NodeVisitor):
            def __init__(self, scanner, filepath):
                self.scanner = scanner
                self.filepath = filepath

            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name in self.scanner._forbidden_imports:
                        # Allow imports within RLM client modules (legitimate gateway components)
                        if "rlm/clients/" not in self.filepath:
                            violations.append(
                                {
                                    "type": "forbidden_import",
                                    "line": str(node.lineno),
                                    "message": f"Direct import of model library '{alias.name}' detected. "
                                    f"All model usage must go through RLM interface. "
                                    f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                                    "severity": "critical",
                                }
                            )
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                if node.module and node.module in self.scanner._forbidden_imports:
                    # Allow imports within RLM client modules (legitimate gateway components)
                    if "rlm/clients/" not in self.filepath:
                        violations.append(
                            {
                                "type": "forbidden_import",
                                "line": str(node.lineno),
                                "message": f"Direct import from model library '{node.module}' detected. "
                                f"All model usage must go through RLM interface.",
                                "severity": "critical",
                            }
                        )
                self.generic_visit(node)

            def visit_Call(self, node):
                # Check for subprocess calls with model binaries
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in ["run", "call", "Popen"]
                ):
                    violations.extend(self._check_subprocess_call(node))

                # Check for requests/urllib calls to model endpoints
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in [
                        "requests",
                        "urllib",
                        "httpx",
                    ]:
                        violations.extend(self._check_http_call(node))

                self.generic_visit(node)

            def _check_subprocess_call(self, node):
                local_violations = []
                if node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.List):
                        # Check list of command arguments
                        for arg in first_arg.elts:
                            # Handle both ast.Str (deprecated) and ast.Constant (Python 3.8+)
                            arg_value = None
                            if hasattr(arg, "s"):  # ast.Str
                                arg_value = arg.s
                            elif hasattr(arg, "value"):  # ast.Constant
                                arg_value = arg.value

                            if arg_value and arg_value in self.scanner._model_binaries:
                                # Allow python/python3 in RLM environment contexts
                                if (
                                    arg_value in ["python", "python3"]
                                    and "rlm/environments/" in self.filepath
                                ):
                                    continue
                                local_violations.append(
                                    {
                                        "type": "subprocess_model_call",
                                        "line": str(node.lineno),
                                        "message": f"Subprocess call to model binary '{arg_value}' detected. "
                                        f"Local model execution must go through RLM environment.",
                                        "severity": "critical",
                                    }
                                )
                    elif hasattr(first_arg, "s") or hasattr(first_arg, "value"):
                        # Check string command - handle both ast.Str and ast.Constant
                        if hasattr(first_arg, "s"):  # ast.Str
                            cmd = first_arg.s
                        elif hasattr(first_arg, "value"):  # ast.Constant in Python 3.8+
                            cmd = str(first_arg.value)
                        else:
                            cmd = str(first_arg)

                        for binary in self.scanner._model_binaries:
                            if binary in cmd:
                                # Allow python/python3 in RLM environment contexts
                                if (
                                    binary in ["python", "python3"]
                                    and "rlm/environments/" in self.filepath
                                ):
                                    continue
                                local_violations.append(
                                    {
                                        "type": "subprocess_model_call",
                                        "line": str(node.lineno),
                                        "message": f"Subprocess command contains model binary '{binary}'. "
                                        f"Local model execution must go through RLM environment.",
                                        "severity": "critical",
                                    }
                                )
                return local_violations

            def _check_http_call(self, node):
                local_violations = []
                for arg in node.args:
                    # Handle both ast.Str (deprecated) and ast.Constant (Python 3.8+)
                    arg_value = None
                    if hasattr(arg, "s"):  # ast.Str
                        arg_value = arg.s
                    elif hasattr(arg, "value"):  # ast.Constant
                        arg_value = arg.value

                    if arg_value:
                        url = str(arg_value)
                        for endpoint in self.scanner._model_endpoints:
                            if endpoint in url:
                                local_violations.append(
                                    {
                                        "type": "direct_http_call",
                                        "line": str(node.lineno),
                                        "message": f"Direct HTTP call to model endpoint '{endpoint}' detected. "
                                        f"All model API calls must go through RLM gateway.",
                                        "severity": "critical",
                                    }
                                )
                return local_violations

        visitor = RLMVisitor(self, filepath)
        visitor.visit(tree)
        return violations

    def _scan_content(self, content: str, filepath: str) -> list[dict[str, str]]:
        """Scan file content for string patterns."""
        violations = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for native library loading
            for binding in self._native_bindings:
                if (
                    f"ctypes.{binding}" in line
                    or f"cffi.{binding}" in line
                    or f"import {binding}" in line
                ):
                    violations.append(
                        {
                            "type": "native_binding",
                            "line": str(i),
                            "message": f"Native binding to model runtime '{binding}' detected. "
                            f"All model usage must go through RLM interface. "
                            f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                            "severity": "critical",
                        }
                    )

            # Check for direct model API patterns (allow legitimate RLM gateway usage)
            if not self._is_allowed_model_usage(filepath):
                # Check regex patterns - but allow in RLM core files
                if not self._is_within_rlm_gateway(filepath):
                    for pattern in self._direct_api_patterns:
                        if re.search(pattern, line):
                            violations.append(
                                {
                                    "type": "direct_api_call",
                                    "line": str(i),
                                    "message": f"Direct model API call pattern '{pattern}' detected in '{filepath}'. "
                                    f"All model calls must use RLM interface. "
                                    f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                                    "severity": "critical",
                                }
                            )

                # Check for model dependency patterns
                for dep_pattern in self._model_dependency_patterns:
                    if re.search(dep_pattern, line, re.IGNORECASE):
                        violations.append(
                            {
                                "type": "model_dependency",
                                "line": str(i),
                                "message": f"Model dependency pattern '{dep_pattern}' detected. "
                                f"Model libraries must only be used within RLM gateway modules. "
                                f"ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                                "severity": "critical",
                            }
                        )

                # Check for hardcoded API keys (security risk)
                api_key_patterns = [
                    r"sk-[a-zA-Z0-9]{48}",  # OpenAI
                    r"sk-ant-[a-zA-Z0-9_-]{95,}",  # Anthropic
                    r"AIza[0-9A-Za-z_-]{35}",  # Google AI
                ]
                for key_pattern in api_key_patterns:
                    if re.search(key_pattern, line):
                        violations.append(
                            {
                                "type": "hardcoded_api_key",
                                "line": str(i),
                                "message": "Potential hardcoded API key detected. "
                                "Use environment variables or secure key management. "
                                "Never commit API keys to version control.",
                                "severity": "critical",
                            }
                        )

                # Check for insecure model server configurations
                insecure_patterns = [
                    r"localhost:\d+",  # Local servers without context
                    r"127\.0\.0\.1:\d+",
                    r"0\.0\.0\.0:\d+",  # Exposed to all interfaces
                ]
                for pattern in insecure_patterns:
                    if re.search(pattern, line) and "rlm/environments/" not in filepath:
                        # Allow in environment files but warn
                        violations.append(
                            {
                                "type": "insecure_server_config",
                                "line": str(i),
                                "message": "Local model server configuration detected outside RLM environment. "
                                "Local model servers must be contained within RLM architecture. "
                                "ACADEMIC PAPER: https://arxiv.org/abs/2512.24601",
                                "severity": "warning",
                            }
                        )

        return violations

    def scan_directory(
        self, directory: str, exclude_patterns: list[str] = None
    ) -> tuple[dict[str, list[dict[str, str]]], int]:
        """
        Scan an entire directory for RLM violations.

        Args:
            directory: Directory path to scan
            exclude_patterns: List of glob patterns to exclude

        Returns:
            Tuple of (results_dict, files_scanned_count)
            results_dict: Dictionary mapping file paths to lists of violations
            files_scanned_count: Total number of files actually scanned
        """
        if exclude_patterns is None:
            exclude_patterns = [
                "__pycache__",
                "*.pyc",
                ".git",
                "node_modules",
                "build",
                "dist",
                ".venv",
                "venv",
                "env",
                ".env",
                "virtualenv",
                ".next",
                ".nuxt",
                "target",
                "out",
            ]

        results = {}
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            # Apply exclusions
            dirs[:] = [
                d
                for d in dirs
                if not any(Path(root, d).match(pattern) for pattern in exclude_patterns)
            ]

            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)

                    # Skip virtual environments and build artifacts
                    if any(
                        pattern in filepath
                        for pattern in [
                            ".venv",
                            "venv",
                            "env",
                            "__pycache__",
                            "node_modules",
                            "build",
                            "dist",
                        ]
                    ):
                        continue

                    violations = self.scan_file(filepath)
                    files_scanned += 1

                    if violations:
                        results[filepath] = violations

        return results, files_scanned

    def has_critical_violations(self, scan_results: dict[str, list[dict[str, str]]]) -> bool:
        """
        Check if scan results contain any critical violations that should block CI.

        Args:
            scan_results: Results from scan_directory()

        Returns:
            True if critical violations exist, False otherwise
        """
        for file_violations in scan_results.values():
            for violation in file_violations:
                if violation["severity"] == "critical":
                    return True
        return False

    def print_report(self, scan_results: dict[str, list[dict[str, str]]], files_scanned: int):
        """Print a human-readable report of scan results."""
        total_violations = sum(len(violations) for violations in scan_results.values())
        critical_count = sum(
            1
            for violations in scan_results.values()
            for v in violations
            if v["severity"] == "critical"
        )

        print("🔍 RLM Architecture Static Scan Report")
        print("=" * 50)
        print(f"Files scanned: {files_scanned}")
        print(f"Files with violations: {len(scan_results)}")
        print(f"Total violations: {total_violations}")
        print(f"Critical violations: {critical_count}")
        print()

        if critical_count > 0:
            print("🚫 CRITICAL VIOLATIONS (BLOCK CI):")
            print("-" * 40)
            for filepath, violations in scan_results.items():
                critical = [v for v in violations if v["severity"] == "critical"]
                if critical:
                    print(f"📁 {filepath}:")
                    for v in critical:
                        print(f"  Line {v['line']}: {v['message']}")
                    print()
        else:
            print("✅ No critical violations found!")


def main():
    """Command-line interface for the static scanner."""
    import argparse

    parser = argparse.ArgumentParser(description="RLM Architecture Static Scanner")
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument("--exclude", action="append", help="Exclude patterns")
    parser.add_argument(
        "--ci", action="store_true", help="Exit with error code on critical violations"
    )

    args = parser.parse_args()

    scanner = RLMStaticScanner()
    results, files_scanned = scanner.scan_directory(args.directory, args.exclude)

    scanner.print_report(results, files_scanned)

    if args.ci and scanner.has_critical_violations(results):
        print("\n❌ CRITICAL VIOLATIONS DETECTED - BLOCKING CI")
        exit(1)
    elif not scanner.has_critical_violations(results):
        print("\n✅ SCAN PASSED - NO CRITICAL VIOLATIONS")
    else:
        print("\n⚠️  NON-CRITICAL VIOLATIONS FOUND - REVIEW REQUIRED")


if __name__ == "__main__":
    main()
