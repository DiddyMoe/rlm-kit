"""Tests for custom tool injection into LocalREPL (RF-052)."""

from rlm.environments.local_repl import LocalREPL
from rlm.utils.prompts import QueryMetadata, build_rlm_system_prompt


class TestCustomToolInjection:
    """Test that custom tools are available in REPL execution namespace."""

    def test_custom_tool_callable_in_repl(self) -> None:
        def my_tool(x: int) -> int:
            return x * 2

        repl = LocalREPL(context_payload="test", custom_tools={"my_tool": my_tool})
        result = repl.execute_code("answer = my_tool(21)\nprint(answer)")
        assert "42" in result.stdout
        repl.cleanup()

    def test_custom_tool_survives_overwrite(self) -> None:
        """Custom tools should be restored after user code overwrites them."""

        def my_tool() -> str:
            return "original"

        repl = LocalREPL(context_payload="test", custom_tools={"my_tool": my_tool})
        # Overwrite the tool
        repl.execute_code("my_tool = 'overwritten'")
        # Tool should be restored
        result = repl.execute_code("print(my_tool())")
        assert "original" in result.stdout
        repl.cleanup()

    def test_no_custom_tools_is_fine(self) -> None:
        repl = LocalREPL(context_payload="test")
        result = repl.execute_code("print('ok')")
        assert "ok" in result.stdout
        repl.cleanup()

    def test_multiple_custom_tools(self) -> None:
        def tool_a() -> str:
            return "a"

        def tool_b() -> str:
            return "b"

        repl = LocalREPL(context_payload="test", custom_tools={"tool_a": tool_a, "tool_b": tool_b})
        result = repl.execute_code("print(tool_a() + tool_b())")
        assert "ab" in result.stdout
        repl.cleanup()


class TestCustomToolsInPrompt:
    """Test that system prompt mentions custom tools when provided."""

    def test_prompt_includes_tool_names(self) -> None:
        tools = {"read_file": lambda: None, "search": lambda: None}
        metadata = QueryMetadata("test")
        messages = build_rlm_system_prompt(
            system_prompt="base", query_metadata=metadata, custom_tools=tools
        )
        system_content = messages[0]["content"]
        assert "`read_file`" in system_content
        assert "`search`" in system_content

    def test_prompt_no_tools_no_mention(self) -> None:
        metadata = QueryMetadata("test")
        messages = build_rlm_system_prompt(
            system_prompt="base", query_metadata=metadata, custom_tools=None
        )
        system_content = messages[0]["content"]
        assert "custom tools" not in system_content.lower()
