#!/usr/bin/env python3
"""
MCP Integration Example: Using MCP Tools with RLM Agents

This example demonstrates how MCP (Model Context Protocol) tools can be
integrated with RLM agents WITHOUT modifying the MCP servers themselves.
"""

import asyncio
import os

from dotenv import load_dotenv

from rlm import create_enforced_agent

# Load environment variables
load_dotenv()

# Example MCP tool implementations
# These would typically connect to actual MCP servers in Cursor/VS Code


def mcp_browser_navigate(url: str) -> str:
    """MCP Browser tool - navigate to URL."""
    return f"Browser navigated to: {url}"


def mcp_browser_click(selector: str) -> str:
    """MCP Browser tool - click element."""
    return f"Clicked element: {selector}"


def mcp_browser_get_text(selector: str) -> str:
    """MCP Browser tool - get text from element."""
    return f"Text from {selector}: 'Sample extracted text'"


def mcp_code_search(query: str, file_pattern: str = "*.py") -> str:
    """MCP Code Search tool - search codebase."""
    return f"Found matches for '{query}' in {file_pattern} files: [simulated results]"


def mcp_terminal_run(command: str) -> str:
    """MCP Terminal tool - run terminal command."""
    return f"Terminal output: {command} executed successfully"


def mcp_file_read(filepath: str) -> str:
    """MCP File tool - read file contents."""
    try:
        with open(filepath) as f:
            content = f.read()[:500]  # Limit for demo
            return f"File content ({len(content)} chars): {content}..."
    except Exception as e:
        return f"Error reading file {filepath}: {e}"


async def demonstrate_mcp_integration():
    """Demonstrate MCP tool integration with RLM agents."""

    print("🔧 MCP Integration with RLM Agents")
    print("=" * 50)

    # Create RLM agent (enforced configuration)
    agent = create_enforced_agent(
        backend="openai",
        backend_kwargs={
            "model_name": "gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY"),
        },
    )

    # Register MCP tools with the agent
    # NOTE: MCP servers themselves are NOT modified - we just register their functions
    print("📝 Registering MCP tools with RLM agent...")
    agent.register_tool("browser_navigate", mcp_browser_navigate)
    agent.register_tool("browser_click", mcp_browser_click)
    agent.register_tool("browser_get_text", mcp_browser_get_text)
    agent.register_tool("code_search", mcp_code_search)
    agent.register_tool("terminal_run", mcp_terminal_run)
    agent.register_tool("file_read", mcp_file_read)

    print("✅ MCP tools registered successfully")
    print(f"Available tools: {list(agent.agent_context.tools.keys())}")
    print()

    # Example 1: Web automation task
    print("🌐 Example 1: Web Automation with MCP Browser Tools")
    web_task = """
    I need to check the current weather in New York City.
    Please help me navigate to a weather website, search for NYC weather,
    and extract the current temperature.
    """

    print(f"User: {web_task.strip()}")

    async for chunk in agent.chat(web_task, stream=True):
        print(chunk, end="", flush=True)
    print("\n")

    # Example 2: Code analysis task
    print("💻 Example 2: Code Analysis with MCP Code Search")
    code_task = """
    I'm working on the RLM project. Can you help me find all the places
    where error handling occurs in the codebase? Look for try/except blocks
    and error messages.
    """

    print(f"User: {code_task.strip()}")

    async for chunk in agent.chat(code_task, stream=True):
        print(chunk, end="", flush=True)
    print("\n")

    # Example 3: File operations
    print("📄 Example 3: File Operations with MCP File Tools")
    file_task = """
    Let me analyze the main RLM implementation. Please read the rlm/core/rlm.py
    file and summarize the key classes and methods.
    """

    print(f"User: {file_task.strip()}")

    async for chunk in agent.chat(file_task, stream=True):
        print(chunk, end="", flush=True)
    print("\n")

    print("🎉 MCP Integration Demo Complete!")
    print("\nKey Points:")
    print("✅ MCP servers/tools work WITHOUT modification")
    print("✅ RLM agents use proper reasoning architecture")
    print("✅ Tools are registered as agent capabilities")
    print("✅ All agent interactions use enforced RLM patterns")


if __name__ == "__main__":
    asyncio.run(demonstrate_mcp_integration())
