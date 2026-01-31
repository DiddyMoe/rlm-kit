#!/usr/bin/env python3
"""
RLM CLI Agent Example

This example demonstrates how to create an AI agent that uses the RLM-enforced
CLI interface as its sole means of accessing the repository.

The agent cannot access the codebase directly - all interactions must go through
the secure CLI mediator, ensuring RLM architecture compliance and controlled access.

Based on "Recursive Language Models" (arXiv:2512.24601) - this ensures AI agents
can only access repository context through controlled, recursive mechanisms.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Bootstrap: repo root on path so path_utils and rlm are importable
_root = Path(__file__).resolve().parent
for _ in range(30):
    if (_root / "pyproject.toml").is_file():
        break
    _root = _root.parent
    if _root == _root.parent:
        raise FileNotFoundError("Repo root not found (no pyproject.toml)")
sys.path.insert(0, str(_root))
from path_utils import REPO_ROOT, SCRIPT_DIR  # noqa: E402
from rlm import create_enforced_agent  # noqa: E402


class RepositoryCLITool:
    """
    Tool that provides secure repository access through the RLM CLI interface.

    This tool acts as the bridge between AI agents and the repository,
    ensuring all access goes through proper RLM-enforced channels.
    """

    def __init__(self):
        self.cli_path = SCRIPT_DIR / "rlm_cli_interface.py"

    def _run_cli_command(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a command through the RLM CLI interface.

        This is the secure boundary - all repository access must go through here.
        """
        cmd = [
            sys.executable,
            str(self.cli_path),
            operation,
            "--params",
            json.dumps(params),
            "--rlm-context",
            "rlm_agent",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "CLI timeout",
                "message": "Command execution timed out",
            }
        except Exception as e:
            return {"success": False, "error": "CLI execution error", "message": str(e)}

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            try:
                return json.loads(err)
            except json.JSONDecodeError:
                return {"success": False, "error": "CLI execution failed", "message": err}

        # Stdout may contain a prefix (e.g. banner) then JSON; extract the JSON object
        raw = (proc.stdout or "").strip()
        start = raw.find("{")
        if start == -1:
            return {"success": False, "error": "CLI output", "message": "No JSON in output"}
        try:
            return json.loads(raw[start:])
        except json.JSONDecodeError as e:
            return {"success": False, "error": "CLI output", "message": str(e)}

    def search_code(self, query: str, file_pattern: str = "*.py", max_results: int = 5) -> str:
        """Search for code patterns in the repository."""
        result = self._run_cli_command(
            "search_code",
            {"query": query, "file_pattern": file_pattern, "max_results": max_results},
        )

        if result.get("success"):
            findings = result["result"]
            if not findings:
                return f"No code found matching '{query}'"

            response = f"Found {len(findings)} matches for '{query}':\n\n"
            for finding in findings:
                response += f"📁 {finding['file']} (line {finding['line']}):\n"
                response += f"```\n{finding['context']}\n```\n\n"
            return response
        else:
            return f"Search failed: {result.get('message', 'Unknown error')}"

    def read_file(self, file_path: str, max_lines: int = 50) -> str:
        """Read a file's contents."""
        result = self._run_cli_command(
            "read_file", {"file_path": file_path, "max_lines": max_lines}
        )

        if result.get("success"):
            file_data = result["result"]
            content = file_data["content"]
            if file_data["truncated"]:
                content += f"\n\n[File truncated after {max_lines} lines. Total: {file_data['total_lines']} lines]"

            return f"📁 {file_data['path']}:\n```\n{content}\n```"
        else:
            return f"Failed to read file: {result.get('message', 'Unknown error')}"

    def list_directory(self, dir_path: str = ".", max_depth: int = 2) -> str:
        """List directory contents."""
        result = self._run_cli_command(
            "list_directory", {"dir_path": dir_path, "max_depth": max_depth}
        )

        if result.get("success"):
            return self._format_directory_listing(result["result"])
        else:
            return f"Failed to list directory: {result.get('message', 'Unknown error')}"

    def get_structure(self) -> str:
        """Get repository structure overview."""
        result = self._run_cli_command("get_structure", {})

        if result.get("success"):
            return self._format_directory_listing(result["result"])
        else:
            return f"Failed to get structure: {result.get('message', 'Unknown error')}"

    def analyze_file(self, file_path: str, analysis_type: str = "file_stats") -> str:
        """Analyze a file."""
        result = self._run_cli_command(
            "run_analysis", {"analysis_type": analysis_type, "target": file_path}
        )

        if result.get("success"):
            analysis = result["result"]
            response = f"📊 Analysis of {analysis['path']}:\n\n"

            if analysis_type == "file_stats":
                response += f"- Lines: {analysis['lines']}\n"
                response += f"- Characters: {analysis['characters']}\n"
                response += f"- Functions: {analysis['functions']}\n"
                response += f"- Classes: {analysis['classes']}\n"
                response += f"- Imports: {analysis['imports']}\n"
            elif analysis_type == "import_deps":
                response += f"- Total imports: {analysis['total_imports']}\n"
                if analysis["imports"]:
                    response += "\nImports:\n" + "\n".join(
                        f"  - {imp}" for imp in analysis["imports"]
                    )
            elif analysis_type == "code_structure":
                response += f"- Code blocks: {analysis['code_blocks']}\n"
                response += f"- Functions: {analysis['functions']}\n"
                response += f"- Classes: {analysis['classes']}\n"

            return response
        else:
            return f"Analysis failed: {result.get('message', 'Unknown error')}"

    def _format_directory_listing(self, dir_data: dict[str, Any], indent: int = 0) -> str:
        """Format directory listing for display."""
        prefix = "  " * indent
        if not isinstance(dir_data, dict):
            return f"{prefix}[invalid]"

        if dir_data.get("error"):
            return f"{prefix}[Access denied]"

        if dir_data.get("truncated"):
            return f"{prefix}[Directory truncated]"

        if dir_data.get("type") == "file":
            size_kb = dir_data.get("size", 0) / 1024
            return f"{prefix}📄 {dir_data['name']} ({size_kb:.1f} KB)"

        # Directory: contents may be a list or a wrapper dict {type, contents: [...]}
        raw = dir_data.get("contents", [])
        entries = (
            raw
            if isinstance(raw, list)
            else raw.get("contents", [])
            if isinstance(raw, dict)
            else []
        )
        result = f"{prefix}📁 {dir_data.get('name', 'root')}/\n"
        for item in entries:
            result += self._format_directory_listing(item, indent + 1) + "\n"

        return result.strip()


async def main():
    """Demonstrate the RLM CLI agent."""
    print("🤖 RLM CLI Agent Demo")
    print("=" * 50)
    print("This agent can only access the repository through the secure CLI interface.")
    print("All operations are mediated and RLM-enforced.\n")

    # Create the agent with CLI tool
    agent = create_enforced_agent(backend="openai")
    cli_tool = RepositoryCLITool()

    # Register CLI-based tools
    agent.register_tool("search_code", cli_tool.search_code)
    agent.register_tool("read_file", cli_tool.read_file)
    agent.register_tool("list_directory", cli_tool.list_directory)
    agent.register_tool("get_structure", cli_tool.get_structure)
    agent.register_tool("analyze_file", cli_tool.analyze_file)

    # Example conversation
    queries = [
        "Show me the repository structure",
        "Search for RLM-related code",
        "Read the main README file",
        "Analyze the file statistics of rlm/core/rlm.py",
        "Find all function definitions in the codebase",
    ]

    print("Example queries the agent can handle:")
    for i, query in enumerate(queries, 1):
        print(f"{i}. {query}")

    print("\nTo use this agent interactively:")
    print("```python")
    print("import asyncio")
    print("from rlm import create_enforced_agent")
    print("from examples.rlm_cli_agent import RepositoryCLITool")
    print("")
    print("agent = create_enforced_agent(backend='openai')")
    print("cli_tool = RepositoryCLITool()")
    print("agent.register_tool('search_code', cli_tool.search_code)")
    print("agent.register_tool('read_file', cli_tool.read_file)")
    print("# ... register other tools")
    print("")
    print("async def chat():")
    print("    async for chunk in agent.chat('Your query here', stream=True):")
    print("        print(chunk, end='')")
    print("")
    print("asyncio.run(chat())")
    print("```")

    print("\n🔒 Security Benefits:")
    print("- Agent cannot access codebase directly")
    print("- All operations go through RLM-enforced CLI")
    print("- Controlled, auditable access patterns")
    print("- No direct file system access by AI")
    print("- Complete mediation and logging")


if __name__ == "__main__":
    asyncio.run(main())
