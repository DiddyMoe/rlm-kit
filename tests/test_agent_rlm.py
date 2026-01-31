"""
Tests for AgentRLM functionality.
"""

from unittest.mock import Mock, patch

import pytest

from rlm.agent_enforcer import AgentRLMValidator, RLMEnforcementError, create_enforced_agent
from rlm.agent_rlm import AgentContext, AgentRLM
from rlm.environments.agent_env import AgentEnvironment


class TestAgentContext:
    """Test AgentContext functionality."""

    def test_agent_context_creation(self):
        """Test creating an agent context."""
        context = AgentContext("test-agent")

        assert context.agent_id == "test-agent"
        assert context.conversation_history == []
        assert context.context_data == {}
        assert context.tools == {}

    def test_add_message(self):
        """Test adding messages to conversation history."""
        context = AgentContext()

        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there!", {"confidence": 0.9})

        assert len(context.conversation_history) == 2
        assert context.conversation_history[0]["role"] == "user"
        assert context.conversation_history[0]["content"] == "Hello"
        assert context.conversation_history[1]["metadata"]["confidence"] == 0.9

    def test_register_tool(self):
        """Test tool registration."""
        context = AgentContext()

        def test_tool(x):
            return x * 2

        context.register_tool("double", test_tool)

        assert "double" in context.tools
        assert context.tools["double"] == test_tool

    def test_add_context(self):
        """Test adding context data."""
        context = AgentContext()

        context.add_context("user_name", "Alice")
        context.add_context("preferences", {"theme": "dark"})

        assert context.context_data["user_name"] == "Alice"
        assert context.context_data["preferences"]["theme"] == "dark"


class TestAgentEnvironment:
    """Test AgentEnvironment functionality."""

    def test_agent_environment_creation(self):
        """Test creating an agent environment."""
        env = AgentEnvironment()

        # Check that agent-specific functions are available
        assert "call_tool" in env.locals
        assert "get_agent_context" in env.locals
        assert "analyze_text" in env.locals
        assert "reason_step_by_step" in env.locals

    def test_call_tool_functionality(self):
        """Test tool calling in agent environment."""
        env = AgentEnvironment()

        # Register a test tool
        def add_numbers(a, b):
            return a + b

        env.tools["add"] = add_numbers

        # Test calling the tool
        result = env.locals["call_tool"]("add", a=5, b=3)
        assert result == 8

    def test_call_tool_error_handling(self):
        """Test error handling in tool calls."""
        env = AgentEnvironment()

        # Try to call non-existent tool
        with pytest.raises(ValueError, match="Tool 'nonexistent' not registered"):
            env.locals["call_tool"]("nonexistent")

    def test_context_search(self):
        """Test context searching functionality."""
        env = AgentEnvironment()
        env.agent_context["doc1"] = "This is about artificial intelligence and machine learning"
        env.agent_context["doc2"] = "This discusses climate change and environmental issues"

        results = env.locals["search_context"]("artificial intelligence")
        assert len(results) == 1
        assert "doc1" in results[0]

    def test_text_analysis(self):
        """Test text analysis functionality."""
        env = AgentEnvironment()
        env.text_analyzer.llm_query = lambda prompt: "Positive sentiment detected"

        result = env.locals["analyze_text"]("I love this!", "sentiment")

        assert result["analysis_type"] == "sentiment"
        assert "Positive sentiment detected" in result["result"]


class TestAgentRLM:
    """Test AgentRLM functionality."""

    @pytest.fixture
    def agent_rlm(self):
        """Create a test AgentRLM instance."""
        with patch("rlm.agent_rlm._get_rlm_class") as mock_get_rlm:
            mock_rlm_class = Mock()
            mock_rlm_instance = Mock()
            mock_rlm_class.return_value = mock_rlm_instance
            mock_get_rlm.return_value = mock_rlm_class

            agent = AgentRLM(
                backend="openai",
                backend_kwargs={"model_name": "gpt-4", "api_key": "test-key"},
                environment="agent",
                enable_tools=True,  # MANDATORY: Tools required for agents per RLM paper
                enable_streaming=True,  # MANDATORY: Streaming required for agents per RLM paper
            )
            agent.rlm = mock_rlm_instance
            return agent

    @pytest.fixture
    def agent_rlm_minimal(self):
        """Create a minimal test AgentRLM instance for basic tests."""
        with patch("rlm.agent_rlm.RLM") as mock_rlm:
            agent = AgentRLM(
                backend="openai",
                backend_kwargs={"api_key": "test-key"},
                environment="agent",
                enable_tools=True,
                enable_streaming=True,
            )
            agent.rlm = mock_rlm.return_value
            return agent

    def test_agent_creation(self, agent_rlm):
        """Test creating an AgentRLM instance."""
        assert isinstance(agent_rlm.agent_context, AgentContext)
        assert agent_rlm.enable_tools is True  # MANDATORY for agents per RLM paper
        assert agent_rlm.enable_streaming is True  # MANDATORY for agents per RLM paper

    def test_register_tool(self, agent_rlm):
        """Test tool registration."""

        def test_tool():
            return "test result"

        agent_rlm.register_tool("test", test_tool)

        assert "test" in agent_rlm.agent_context.tools

    def test_add_context(self, agent_rlm):
        """Test adding context."""
        agent_rlm.add_context("test_key", "test_value")

        assert agent_rlm.agent_context.context_data["test_key"] == "test_value"

    # Non-streaming chat is forbidden for agents per RLM requirements
    # All agent chat must use streaming for real-time conversational responses

    @pytest.mark.asyncio
    async def test_chat_streaming_enabled(self, agent_rlm):
        """Test chat functionality with streaming enabled."""
        mock_completion = Mock(response="Test response")
        agent_rlm.rlm.completion.return_value = mock_completion

        responses = []
        async for response in agent_rlm.chat("Test message", stream=True):
            responses.append(response)

        assert len(responses) > 0
        assert "".join(responses) == "Test response"

    def test_prepare_conversation_context(self, agent_rlm):
        """Test conversation context preparation."""
        agent_rlm.agent_context.add_message("user", "Previous message")
        agent_rlm.agent_context.add_context("test_data", "test_value")

        context = agent_rlm._prepare_conversation_context("Current message")

        assert context["current_message"] == "Current message"
        assert len(context["conversation_history"]) == 1
        assert context["context_data"]["test_data"] == "test_value"

    def test_create_reasoning_prompt(self, agent_rlm):
        """Test reasoning prompt creation."""
        context = {
            "current_message": "Test question",
            "conversation_history": [{"role": "user", "content": "Hi"}],
            "context_data": {"info": "test data"},
            "available_tools": ["search"],
        }

        prompt = agent_rlm._create_reasoning_prompt(context)

        assert "Test question" in prompt
        assert "Hi" in prompt
        assert "test data" in prompt
        assert "search" in prompt


class TestAgentEnforcer:
    """Test RLM enforcement functionality."""

    def test_agent_validator_valid_config(self):
        """Test validation of valid agent configuration."""
        config = {
            "backend": "openai",
            "backend_kwargs": {"api_key": "test-key"},
            "environment": "agent",
            "enable_tools": True,
            "enable_streaming": True,
        }
        # Should not raise
        AgentRLMValidator.validate_agent_config(config)

    def test_agent_validator_invalid_environment(self):
        """Test validation rejects non-agent environment."""
        config = {"environment": "local", "enable_tools": True, "enable_streaming": True}
        with pytest.raises(RLMEnforcementError, match="environment='agent'"):
            AgentRLMValidator.validate_agent_config(config)

    def test_agent_validator_no_tools(self):
        """Test validation rejects disabled tools."""
        config = {"environment": "agent", "enable_tools": False, "enable_streaming": True}
        with pytest.raises(RLMEnforcementError, match="enable_tools=True"):
            AgentRLMValidator.validate_agent_config(config)

    def test_agent_validator_no_streaming(self):
        """Test validation rejects disabled streaming."""
        config = {"environment": "agent", "enable_tools": True, "enable_streaming": False}
        with pytest.raises(RLMEnforcementError, match="enable_streaming=True"):
            AgentRLMValidator.validate_agent_config(config)

    def test_chat_validator_valid(self):
        """Test valid chat usage validation."""
        # Should not raise
        AgentRLMValidator.validate_chat_usage("chat", stream=True)

    def test_chat_validator_invalid_streaming(self):
        """Test chat validation rejects non-streaming."""
        with pytest.raises(RLMEnforcementError, match="stream=True"):
            AgentRLMValidator.validate_chat_usage("chat", stream=False)

    @patch("rlm.agent_rlm._get_rlm_class")
    def test_create_enforced_agent(self, mock_get_rlm):
        """Test create_enforced_agent function."""
        mock_rlm_class = Mock()
        mock_rlm_instance = Mock()
        mock_rlm_class.return_value = mock_rlm_instance
        mock_get_rlm.return_value = mock_rlm_class

        agent = create_enforced_agent(
            backend="openai", backend_kwargs={"model_name": "gpt-4", "api_key": "test-key"}
        )

        assert isinstance(agent, AgentRLM)
        assert agent.environment == "agent"
        assert agent.enable_tools is True
        assert agent.enable_streaming is True

    @patch("rlm.agent_rlm._get_rlm_class")
    def test_create_enforced_agent_validation(self, mock_get_rlm):
        """Test that create_enforced_agent validates configuration."""
        mock_rlm_class = Mock()
        mock_get_rlm.return_value = mock_rlm_class

        with pytest.raises(RLMEnforcementError):
            create_enforced_agent(
                backend="openai",
                environment="local",  # Invalid override
            )

    @patch("rlm.agent_rlm._get_rlm_class")
    def test_budget_controls(self, mock_get_rlm):
        """Test that budget controls are properly passed to RLM."""
        mock_rlm_class = Mock()
        mock_rlm_instance = Mock()
        mock_rlm_class.return_value = mock_rlm_instance
        mock_get_rlm.return_value = mock_rlm_class

        # Test with budget controls
        AgentRLM(
            backend="openai",
            backend_kwargs={"api_key": "test-key"},
            environment="agent",
            enable_tools=True,
            enable_streaming=True,
            max_tokens=1000,
            max_cost=5.0,
        )

        # Verify RLM was created with budget parameters
        mock_rlm_class.assert_called_once()
        call_kwargs = mock_rlm_class.call_args[1]
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["max_cost"] == 5.0

    def test_budget_enforcement_error(self):
        """Test that budget enforcement raises appropriate errors when supported."""
        from rlm.core.rlm import RLM

        # Core RLM may not have _check_budget_exceeded_with_handler; skip if absent
        with (
            patch("rlm.core.rlm.get_client") as mock_get_client,
            patch("rlm.core.rlm.get_environment") as mock_get_env,
        ):
            mock_client = Mock()
            mock_client.completion.return_value = "test response"
            mock_get_client.return_value = mock_client

            mock_env = Mock()
            mock_env.execute_code.return_value = Mock()
            mock_get_env.return_value = mock_env

            rlm = RLM(backend="openai", max_iterations=1)
            if not hasattr(rlm, "_check_budget_exceeded_with_handler"):
                pytest.skip("Core RLM does not define _check_budget_exceeded_with_handler")

            with patch.object(rlm, "_check_budget_exceeded_with_handler") as mock_check:
                mock_check.side_effect = ValueError("Token budget exceeded")

                with pytest.raises(ValueError, match="Token budget exceeded"):
                    rlm.completion("test prompt")


if __name__ == "__main__":
    pytest.main([__file__])
