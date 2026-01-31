#!/usr/bin/env python3
"""
AgentRLM Example: Conversational AI Agent with RLM Capabilities

This example demonstrates how AI agents can use RLMs for complex reasoning
over long contexts while maintaining conversation state and tool integration.
"""

import asyncio
import os

from dotenv import load_dotenv

from rlm import AgentRLM, create_enforced_agent

# Load environment variables
load_dotenv()


# Example tools that agents can use
def search_web(query: str) -> str:
    """Simulated web search tool."""
    return f"Web search results for '{query}': [Simulated results showing relevant information about {query}]"


def calculate_math(expression: str) -> float | str:
    """Simple math calculation tool."""
    try:
        # Safe evaluation for demonstration
        allowed_names = {"__builtins__": {}}
        result = eval(expression, allowed_names)
        return result
    except Exception as e:
        return f"Error calculating {expression}: {e}"


def read_file(filepath: str) -> str:
    """Read file contents."""
    try:
        with open(filepath) as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {filepath}: {e}"


def browser_automation(action: str, **kwargs) -> str:
    """Example MCP browser automation tool."""
    # This would integrate with Cursor's MCP browser tools
    return f"Browser automation: {action} with {kwargs}"


def code_search(query: str, file_pattern: str = "*.py") -> str:
    """Example code search tool."""
    # This could integrate with IDE search capabilities
    return f"Searching for '{query}' in {file_pattern} files"


async def main():
    """Demonstrate AgentRLM capabilities."""

    # Initialize AgentRLM (RECOMMENDED: Use create_enforced_agent for guaranteed compliance)
    agent = create_enforced_agent(
        backend="openai",
        backend_kwargs={
            "model_name": "gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY"),
        },
    )

    # Alternative: Manual initialization (but create_enforced_agent is safer)
    # agent = AgentRLM(
    #     backend="openai",
    #     backend_kwargs={
    #         "model_name": "gpt-4",
    #         "api_key": os.getenv("OPENAI_API_KEY"),
    #     },
    #     environment="agent",  # Use agent environment
    #     verbose=True,
    #     enable_tools=True,
    #     enable_streaming=True
    # )

    # Register tools (including MCP integrations)
    # Note: MCP tools can be registered without modifying the MCP servers themselves
    agent.register_tool("search_web", search_web)
    agent.register_tool("calculate", calculate_math)
    agent.register_tool("read_file", read_file)
    agent.register_tool("browser_automation", browser_automation)  # MCP browser tool
    agent.register_tool("code_search", code_search)  # IDE search tool

    # Add some context data
    agent.add_context(
        "user_profile",
        {
            "name": "Alex",
            "interests": ["AI", "programming", "research"],
            "expertise": ["machine learning", "natural language processing"],
        },
    )

    agent.add_context(
        "current_project",
        {
            "name": "RLM Research",
            "description": "Implementing Recursive Language Models for long-context reasoning",
            "status": "active",
            "technologies": ["Python", "OpenAI API", "Docker", "Modal"],
        },
    )

    print("🤖 AgentRLM initialized with tools and context")
    print("Available tools:", list(agent.agent_context.tools.keys()))
    print()

    # Example conversation
    conversations = [
        "Hello! Can you help me analyze this long research paper about machine learning?",
        "Based on my interests in AI and programming, what aspects of this RLM project would you recommend I focus on learning?",
        "I need to calculate the complexity of training an RLM model. If we have 1M tokens of context and break it into 100 chunks, how many LLM calls would we need?",
        "Can you search for recent developments in recursive language models and summarize the key findings?",
        "Help me design an experiment to test RLM performance on different types of long-context tasks.",
    ]

    for i, user_message in enumerate(conversations, 1):
        print(f"\n{'=' * 60}")
        print(f"Conversation {i}: {user_message[:50]}...")
        print(f"{'=' * 60}")

        # Stream the response
        response_chunks = []
        async for chunk in agent.chat(user_message, stream=True):
            print(chunk, end="", flush=True)
            response_chunks.append(chunk)

        print("\n")

        # Show conversation history summary
        history = agent.get_conversation_history()
        print(f"Conversation turns so far: {len(history)}")
        print(f"Context items stored: {len(agent.agent_context.context_data)}")
        print()

    # Demonstrate context persistence
    print("💾 Saving agent context...")
    agent.save_context("agent_context.json")

    print("🔄 Creating new agent and loading context...")
    new_agent = AgentRLM(
        backend="openai",
        backend_kwargs={"model_name": "gpt-4", "api_key": os.getenv("OPENAI_API_KEY")},
        environment="agent",
    )

    # Re-register tools (they're not serialized)
    new_agent.register_tool("search_web", search_web)
    new_agent.register_tool("calculate", calculate_math)
    new_agent.register_tool("read_file", read_file)

    new_agent.load_context("agent_context.json")

    print(f"Loaded context with {len(new_agent.get_conversation_history())} conversation turns")
    print(f"Context data keys: {list(new_agent.agent_context.context_data.keys())}")

    # Test continuity
    async for chunk in new_agent.chat(
        "What were we just discussing about RLM experiments?", stream=True
    ):
        print(chunk, end="", flush=True)
    print("\n")

    print("✅ AgentRLM demonstration completed!")


if __name__ == "__main__":
    asyncio.run(main())
