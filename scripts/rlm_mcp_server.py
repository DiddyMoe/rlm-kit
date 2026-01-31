#!/usr/bin/env python3
"""
RLM MCP Server for Built-in AI Agent Chat Integration

This MCP server provides RLM-mediated repository access tools for built-in AI agent chats
(like Cursor AI Agent, Github Copilot chat). It acts as a bridge between AI chat interfaces
and the secure RLM CLI, enabling safe repository interaction.

Based on "Recursive Language Models" (arXiv:2512.24601) - ensuring AI agents can access
repository context through controlled, recursive mechanisms while maintaining security.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Bootstrap: repo root on path so path_utils and rlm are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT, SCRIPT_DIR  # noqa: E402
from rlm import create_enforced_agent
from rlm.core.rlm_enforcement import RLMContext

# Import MCP SDK
try:
    from mcp import Tool
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp")
    sys.exit(1)


class RLMMCPServer:
    """MCP Server that provides RLM-mediated repository access tools."""

    def __init__(self):
        self.cli_path = SCRIPT_DIR / "rlm_cli_interface.py"
        self.agent = None
        self._setup_rlm_agent()

    def _setup_rlm_agent(self):
        """Create RLM agent with CLI tools for repository access."""
        try:
            # Set RLM context for CLI operations
            RLMContext.set_context("mcp_server")

            # Create RLM agent
            self.agent = create_enforced_agent(backend="openai")

            # Create CLI tool wrapper
            cli_tool = RepositoryCLITool()

            # Register CLI-based tools
            self.agent.register_tool("search_code", cli_tool.search_code)
            self.agent.register_tool("read_file", cli_tool.read_file)
            self.agent.register_tool("list_directory", cli_tool.list_directory)
            self.agent.register_tool("analyze_file", cli_tool.analyze_file)
            self.agent.register_tool("get_structure", cli_tool.get_structure)

        except Exception as e:
            print(f"Failed to setup RLM agent: {e}")
            self.agent = None

    async def search_code(
        self, query: str, file_pattern: str = "*.py", max_results: int = 5
    ) -> str:
        """Search for code patterns in the repository using RLM mediation."""
        if not self.agent:
            return "RLM agent not available"

        try:
            # Use RLM agent to mediate the search
            prompt = f"Search for '{query}' in {file_pattern} files (max {max_results} results)"
            response = ""
            async for chunk in self.agent.chat(prompt, stream=True):
                response += chunk
            return response

        except Exception as e:
            return f"Search failed: {e}"

    async def read_file(self, file_path: str, max_lines: int = 50) -> str:
        """Read a file using RLM-mediated access."""
        if not self.agent:
            return "RLM agent not available"

        try:
            prompt = f"Read the file '{file_path}' (limit to {max_lines} lines)"
            response = ""
            async for chunk in self.agent.chat(prompt, stream=True):
                response += chunk
            return response

        except Exception as e:
            return f"File read failed: {e}"

    async def list_directory(self, dir_path: str = ".", max_depth: int = 2) -> str:
        """List directory contents using RLM mediation."""
        if not self.agent:
            return "RLM agent not available"

        try:
            prompt = f"List the contents of directory '{dir_path}' (depth {max_depth})"
            response = ""
            async for chunk in self.agent.chat(prompt, stream=True):
                response += chunk
            return response

        except Exception as e:
            return f"Directory listing failed: {e}"

    async def analyze_codebase(self, analysis_type: str = "overview") -> str:
        """Provide codebase analysis using RLM mediation."""
        if not self.agent:
            return "RLM agent not available"

        try:
            prompts = {
                "overview": "Provide an overview of this codebase structure and main components",
                "architecture": "Analyze the architecture and design patterns used in this codebase",
                "dependencies": "Analyze the import dependencies and module structure",
                "functionality": "Explain the main functionality and purpose of this codebase",
            }

            prompt = prompts.get(analysis_type, "Provide an analysis of this codebase")
            response = ""
            async for chunk in self.agent.chat(prompt, stream=True):
                response += chunk
            return response

        except Exception as e:
            return f"Analysis failed: {e}"

    async def get_structure(self) -> str:
        """Get repository structure overview using RLM mediation."""
        if not self.agent:
            return "RLM agent not available"
        try:
            prompt = "Get the repository structure overview"
            response = ""
            async for chunk in self.agent.chat(prompt, stream=True):
                response += chunk
            return response
        except Exception as e:
            return f"Structure failed: {e}"


class RepositoryCLITool:
    """Tool that provides secure repository access through the RLM CLI interface."""

    def __init__(self):
        self.cli_path = SCRIPT_DIR / "rlm_cli_interface.py"

    def _run_cli_command(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a command through the RLM CLI interface."""
        cmd = [sys.executable, str(self.cli_path), operation, "--params", json.dumps(params)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)

            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                error_output = result.stderr.strip()
                try:
                    return json.loads(error_output)
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "CLI execution failed",
                        "message": error_output,
                    }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "CLI timeout",
                "message": "Command execution timed out",
            }
        except Exception as e:
            return {"success": False, "error": "CLI execution error", "message": str(e)}

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

        if dir_data.get("error"):
            return f"{prefix}[Access denied]"

        if dir_data.get("truncated"):
            return f"{prefix}[Directory truncated]"

        if dir_data["type"] == "file":
            size_kb = dir_data.get("size", 0) / 1024
            return f"{prefix}📄 {dir_data['name']} ({size_kb:.1f} KB)"

        # Directory
        result = f"{prefix}📁 {dir_data.get('name', 'root')}/\n"
        for item in dir_data.get("contents", []):
            result += self._format_directory_listing(item, indent + 1) + "\n"

        return result.strip()


# MCP Server Implementation
server = Server("rlm-mcp-server")
rlm_server = RLMMCPServer()


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available RLM-mediated repository tools."""
    return [
        Tool(
            name="search_code",
            description="Search for code patterns in the repository using RLM mediation",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern (e.g., '*.py')",
                        "default": "*.py",
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Maximum results",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="read_file",
            description="Read a file's contents using RLM-mediated access",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file"},
                    "max_lines": {
                        "type": "number",
                        "description": "Maximum lines to read",
                        "default": 50,
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="list_directory",
            description="List directory contents using RLM mediation",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Directory path", "default": "."},
                    "max_depth": {"type": "number", "description": "Maximum depth", "default": 2},
                },
            },
        ),
        Tool(
            name="analyze_codebase",
            description="Analyze the codebase using RLM mediation",
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "enum": ["overview", "architecture", "dependencies", "functionality"],
                        "description": "Type of analysis",
                        "default": "overview",
                    }
                },
            },
        ),
        Tool(
            name="get_structure",
            description="Get repository structure overview using RLM mediation",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls through RLM mediation."""

    try:
        if name == "search_code":
            result = await rlm_server.search_code(**arguments)
        elif name == "read_file":
            result = await rlm_server.read_file(**arguments)
        elif name == "list_directory":
            result = await rlm_server.list_directory(**arguments)
        elif name == "analyze_codebase":
            result = await rlm_server.analyze_codebase(**arguments)
        elif name == "get_structure":
            result = await rlm_server.get_structure()
        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return [TextContent(type="text", text=f"Tool execution failed: {e}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
