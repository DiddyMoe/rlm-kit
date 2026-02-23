"""Comprehensive tests for LocalREPL environment."""

import os

from rlm.core.sandbox.safe_builtins import get_safe_builtins, get_safe_builtins_for_repl
from rlm.environments.local_repl import LocalREPL


class TestLocalREPLBasic:
    """Basic functionality tests for LocalREPL."""

    def test_simple_execution(self):
        """Test basic code execution."""
        repl = LocalREPL()
        result = repl.execute_code("x = 1 + 2")
        assert result.stderr == ""
        assert repl.locals["x"] == 3
        repl.cleanup()

    def test_print_output(self):
        """Test that print statements are captured."""
        repl = LocalREPL()
        result = repl.execute_code("print('Hello, World!')")
        assert "Hello, World!" in result.stdout
        repl.cleanup()

    def test_error_handling(self):
        """Test that errors are captured in stderr."""
        repl = LocalREPL()
        result = repl.execute_code("1 / 0")
        assert "ZeroDivisionError" in result.stderr
        repl.cleanup()

    def test_syntax_error(self):
        """Test syntax error handling."""
        repl = LocalREPL()
        result = repl.execute_code("def broken(")
        assert "SyntaxError" in result.stderr
        repl.cleanup()


class TestLocalREPLPersistence:
    """Tests for state persistence across executions."""

    def test_variable_persistence(self):
        """Test that variables persist across multiple code executions."""
        repl = LocalREPL()

        result1 = repl.execute_code("x = 42")
        assert result1.stderr == ""
        assert repl.locals["x"] == 42

        result2 = repl.execute_code("y = x + 8")
        assert result2.stderr == ""
        assert repl.locals["y"] == 50

        result3 = repl.execute_code("print(y)")
        assert "50" in result3.stdout

        repl.cleanup()

    def test_function_persistence(self):
        """Test that defined functions persist."""
        repl = LocalREPL()

        repl.execute_code(
            """
def greet(name):
    return f"Hello, {name}!"
"""
        )

        result = repl.execute_code("print(greet('World'))")
        assert "Hello, World!" in result.stdout
        repl.cleanup()

    def test_list_comprehension(self):
        """Test that list comprehensions work."""
        repl = LocalREPL()

        repl.execute_code("squares = [x**2 for x in range(5)]")
        assert repl.locals["squares"] == [0, 1, 4, 9, 16]

        result = repl.execute_code("print(sum(squares))")
        assert "30" in result.stdout
        repl.cleanup()


class TestLocalREPLBuiltins:
    """Tests for safe builtins and blocked functions."""

    def test_safe_builtins_available(self):
        """Test that safe builtins are available."""
        repl = LocalREPL()

        # Test various safe builtins
        _ = repl.execute_code("x = len([1, 2, 3])")
        assert repl.locals["x"] == 3

        _ = repl.execute_code("y = sum([1, 2, 3, 4])")
        assert repl.locals["y"] == 10

        _ = repl.execute_code("z = sorted([3, 1, 2])")
        assert repl.locals["z"] == [1, 2, 3]

        repl.cleanup()

    def test_imports_work(self):
        """Test that imports work."""
        repl = LocalREPL()
        result = repl.execute_code("import math\nx = math.pi")
        assert result.stderr == ""
        assert abs(repl.locals["x"] - 3.14159) < 0.001
        repl.cleanup()

    def test_eval_is_blocked(self):
        """Test that eval is blocked in REPL builtins."""
        repl = LocalREPL()
        result = repl.execute_code("eval('1 + 1')")
        assert "TypeError" in result.stderr
        repl.cleanup()

    def test_exec_is_blocked(self):
        """Test that exec is blocked in REPL builtins."""
        repl = LocalREPL()
        result = repl.execute_code("exec('x = 1')")
        assert "TypeError" in result.stderr
        repl.cleanup()

    def test_compile_is_blocked(self):
        """Test that compile is blocked in REPL builtins."""
        repl = LocalREPL()
        result = repl.execute_code("compile('x = 1', '<string>', 'exec')")
        assert "TypeError" in result.stderr
        repl.cleanup()

    def test_strict_builtins_are_more_restrictive(self):
        """Strict builtins block more primitives than REPL builtins."""
        strict_builtins = get_safe_builtins()
        repl_builtins = get_safe_builtins_for_repl()

        assert strict_builtins["__import__"] is None
        assert strict_builtins["open"] is None
        assert strict_builtins["globals"] is None
        assert strict_builtins["locals"] is None

        assert callable(repl_builtins["__import__"])
        assert callable(repl_builtins["open"])
        assert callable(repl_builtins["globals"])
        assert callable(repl_builtins["locals"])


class TestLocalREPLContextManager:
    """Tests for context manager usage."""

    def test_context_manager(self):
        """Test using LocalREPL as context manager."""
        with LocalREPL() as repl:
            _ = repl.execute_code("x = 100")
            assert repl.locals["x"] == 100


class TestLocalREPLHelpers:
    """Tests for helper functions (FINAL_VAR, etc.)."""

    def test_final_var_existing(self):
        """Test FINAL_VAR with existing variable."""
        repl = LocalREPL()
        repl.execute_code("answer = 42")
        _ = repl.execute_code("result = FINAL_VAR('answer')")
        assert repl.locals["result"] == "42"
        repl.cleanup()

    def test_final_var_missing(self):
        """Test FINAL_VAR with non-existent variable."""
        repl = LocalREPL()
        _ = repl.execute_code("result = FINAL_VAR('nonexistent')")
        assert "Error" in repl.locals["result"]
        repl.cleanup()

    def test_llm_query_no_handler(self):
        """Test llm_query without handler configured."""
        repl = LocalREPL()
        _ = repl.execute_code("response = llm_query('test')")
        assert "Error" in repl.locals["response"]
        repl.cleanup()


class TestLocalREPLContext:
    """Tests for context loading."""

    def test_string_context(self):
        """Test loading string context."""
        repl = LocalREPL(context_payload="This is the context data.")
        assert "context" in repl.locals
        assert repl.locals["context"] == "This is the context data."
        repl.cleanup()

    def test_dict_context(self):
        """Test loading dict context."""
        repl = LocalREPL(context_payload={"key": "value", "number": 42})
        assert "context" in repl.locals
        assert repl.locals["context"]["key"] == "value"
        assert repl.locals["context"]["number"] == 42
        repl.cleanup()

    def test_list_context(self):
        """Test loading list context."""
        repl = LocalREPL(context_payload=[1, 2, 3, "four"])
        assert "context" in repl.locals
        assert repl.locals["context"] == [1, 2, 3, "four"]
        repl.cleanup()


class TestLocalREPLCleanup:
    """Tests for cleanup behavior."""

    def test_cleanup_clears_state(self):
        """Test that cleanup clears the namespace."""
        repl = LocalREPL()
        repl.execute_code("x = 42")
        assert "x" in repl.locals
        repl.cleanup()
        assert len(repl.locals) == 0

    def test_temp_dir_created_and_cleaned(self):
        """Test that temp directory is created and cleaned up."""
        repl = LocalREPL()
        temp_dir = repl.temp_dir
        assert os.path.exists(temp_dir)
        repl.cleanup()
        assert not os.path.exists(temp_dir)


class TestLocalREPLEdgeCases:
    """Tests for timeout and large-output behavior."""

    def test_execution_timeout_stops_infinite_loop(self):
        repl = LocalREPL(execution_timeout_seconds=0.05)
        result = repl.execute_code("while True:\n    pass")
        assert "ExecutionTimeoutError" in result.stderr
        repl.cleanup()

    def test_large_stdout_is_captured(self):
        repl = LocalREPL()
        payload = "x" * 100_000
        result = repl.execute_code(f"print('{payload}')")
        assert result.stderr == ""
        assert len(result.stdout) >= 100_000
        assert result.stdout.startswith("x")
        repl.cleanup()

    def test_binary_output_handled_gracefully(self):
        repl = LocalREPL()
        result = repl.execute_code("import sys\nsys.stdout.buffer.write(b'\\xff\\xfe')")
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert "AttributeError" in result.stderr
        repl.cleanup()


class TestLocalREPLSimulatingRLMNoPersistence:
    """
    Tests simulating RLM's non-persistent completion behavior.

    When RLM is configured without persistent=True (the default), each
    get_completion() call spawns a fresh environment and destroys it after.
    This test suite simulates that behavior to prove variables don't survive
    across RLM completions.

    Why this matters: This is NOT just testing that two Python objects don't
    share state (trivially true). This simulates the actual RLM workflow where
    environments are created and destroyed per completion.
    """

    def test_simulated_rlm_completions_reset_environment(self):
        """
        Simulates 2 RLM completions to show env resets between calls.

        Without persistent=True, RLM creates a fresh environment for each
        completion, so state doesn't carry over.
        """
        completion_1_env = LocalREPL()
        completion_1_env.execute_code("important_result = 42")
        assert completion_1_env.locals["important_result"] == 42
        completion_1_env.cleanup()

        completion_2_env = LocalREPL()
        result = completion_2_env.execute_code("print(important_result)")

        assert "NameError" in result.stderr
        assert "important_result" in result.stderr
        completion_2_env.cleanup()

    def test_simulated_rlm_completions_functions_not_preserved(self):
        """
        Simulates 2 RLM completions to show functions don't persist.
        """
        completion_1_env = LocalREPL()
        completion_1_env.execute_code("def my_helper(): return 'useful'")
        assert completion_1_env.execute_code("print(my_helper())").stdout.strip() == "useful"
        completion_1_env.cleanup()

        completion_2_env = LocalREPL()
        result = completion_2_env.execute_code("my_helper()")

        assert "NameError" in result.stderr
        assert "my_helper" in result.stderr
        completion_2_env.cleanup()


class TestLocalREPLScaffoldRestoration:
    """Tests that scaffold names are restored after user code overwrites them."""

    def test_llm_query_restored_after_overwrite(self):
        """User code overwriting llm_query should not break subsequent calls."""
        repl = LocalREPL()
        original = repl.globals["llm_query"]

        repl.execute_code("llm_query = 'oops'")

        # After execute_code, scaffold should be restored
        assert repl.globals["llm_query"] is original
        repl.cleanup()

    def test_final_var_restored_after_overwrite(self):
        """User code overwriting FINAL_VAR should not break subsequent calls."""
        repl = LocalREPL()
        original = repl.globals["FINAL_VAR"]

        repl.execute_code("FINAL_VAR = None")

        assert repl.globals["FINAL_VAR"] is original
        repl.cleanup()

    def test_show_vars_restored_after_overwrite(self):
        """User code overwriting SHOW_VARS should not break subsequent calls."""
        repl = LocalREPL()
        original = repl.globals["SHOW_VARS"]

        repl.execute_code("SHOW_VARS = 123")

        assert repl.globals["SHOW_VARS"] is original
        repl.cleanup()

    def test_context_restored_after_overwrite(self):
        """User code overwriting context should not lose the loaded data."""
        repl = LocalREPL(context_payload="important data")

        repl.execute_code("context = 'overwritten'")

        assert repl.locals["context"] == "important data"
        repl.cleanup()

    def test_history_restored_after_overwrite(self):
        """User code overwriting history should not lose the stored history."""
        repl = LocalREPL()
        repl.add_history([{"role": "user", "content": "hello"}])

        repl.execute_code("history = []")

        assert repl.locals["history"] == [{"role": "user", "content": "hello"}]
        repl.cleanup()

    def test_multiple_overwrites_still_restored(self):
        """Multiple overwrites in sequence should all be recovered."""
        repl = LocalREPL(context_payload="my context")
        original_fv = repl.globals["FINAL_VAR"]
        original_lq = repl.globals["llm_query"]

        repl.execute_code("FINAL_VAR = 1; llm_query = 2; context = 3")
        assert repl.globals["FINAL_VAR"] is original_fv
        assert repl.globals["llm_query"] is original_lq
        assert repl.locals["context"] == "my context"

        repl.execute_code("FINAL_VAR = 'x'; llm_query = 'y'; context = 'z'")
        assert repl.globals["FINAL_VAR"] is original_fv
        assert repl.globals["llm_query"] is original_lq
        assert repl.locals["context"] == "my context"
        repl.cleanup()

    def test_non_scaffold_variables_not_affected(self):
        """Regular user variables should persist normally across executions."""
        repl = LocalREPL()

        repl.execute_code("my_var = 42")
        assert repl.locals["my_var"] == 42

        repl.execute_code("my_var = my_var + 1")
        assert repl.locals["my_var"] == 43
        repl.cleanup()
