"""
Parsing utilities for RLM trajectories.
"""

import re
from typing import TYPE_CHECKING, Any, cast

from rlm.core.types import REPLResult, RLMIteration

if TYPE_CHECKING:
    from rlm.environments.base_env import BaseEnv


def find_code_blocks(text: str) -> list[str]:
    """
    Find REPL code blocks in text wrapped in triple backticks and return List of content(s).
    Returns None if no code blocks are found.
    """
    pattern = r"```repl\s*\n(.*?)\n```"
    results: list[str] = []

    for match in re.finditer(pattern, text, re.DOTALL):
        code_content = match.group(1).strip()
        results.append(code_content)

    return results


def find_final_answer(text: str, environment: "BaseEnv | None" = None) -> str | None:
    """
    Find FINAL(...) or FINAL_VAR(...) statement in response and return the final answer string.

    If FINAL_VAR is found and an environment is provided, executes code to retrieve the variable value.
    Returns None if neither pattern is found.

    Args:
        text: The response text to parse
        environment: Optional environment to execute code for FINAL_VAR retrieval

    Returns:
        The final answer string, or None if no final answer pattern is found
    """
    text_without_code_fences = _strip_code_fences(text)
    final_var_name = _extract_final_var_name(text_without_code_fences)
    if final_var_name is not None:
        return _resolve_final_var(final_var_name, environment)

    final_payload = _extract_final_payload(text_without_code_fences)
    if final_payload is not None:
        return final_payload

    return _consume_environment_final_answer(environment)


def format_iteration(
    iteration: RLMIteration, max_character_length: int = 20000
) -> list[dict[str, str]]:
    """
    Format an RLM iteration (including all code blocks) to append to the message history for
    the prompt of the LM in the next iteration. We also truncate code execution results
    that exceed the max_character_length.

    Args:
        iteration: The iteration to format
        max_character_length: The maximum character length of the result

    Returns:
        A list of messages to add to the next prompt
    """
    messages = [{"role": "assistant", "content": iteration.response}]

    for code_block in iteration.code_blocks:
        code = code_block.code
        result = code_block.result
        result = format_execution_result(result)
        if len(result) > max_character_length:
            result = (
                result[:max_character_length]
                + f"... + [{len(result) - max_character_length} chars...]"
            )

        execution_message = {
            "role": "user",
            "content": f"Code executed:\n```python\n{code}\n```\n\nREPL output:\n{result}",
        }
        messages.append(execution_message)
    return messages


# Legacy helpers retained for compatibility with existing tests and callers.


def format_execution_result(result: REPLResult) -> str:
    """
    Format the execution result as a string for display.

    Args:
        result: The REPLResult object to format.
    """
    result_parts = _collect_execution_result_parts(result)

    if not result_parts:
        return "No output"
    return "\n\n".join(result_parts)


def check_for_final_answer(response: str, repl_env: Any, logger: Any) -> str | None:
    """Check if response contains a final answer."""
    # Use the new find_final_answer function which handles both FINAL and FINAL_VAR
    _ = logger
    return find_final_answer(response, environment=repl_env)


def convert_context_for_repl(context: Any) -> tuple[Any, str | None]:
    """Convert context payload into REPL data and optional raw string form."""
    if isinstance(context, dict):
        return cast(dict[str, Any], context), None

    if isinstance(context, str):
        return None, context

    if isinstance(context, list):
        return _convert_list_context(cast(list[Any], context))

    return context, None


def _strip_code_fences(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _extract_final_var_name(text: str) -> str | None:
    final_var_match = re.search(r"^\s*FINAL_VAR\((.*?)\)", text, re.MULTILINE | re.DOTALL)
    if final_var_match is None:
        return None
    return final_var_match.group(1).strip().strip('"').strip("'")


def _resolve_final_var(variable_name: str, environment: "BaseEnv | None") -> str | None:
    if environment is None:
        return None
    result = environment.execute_code(f"print(FINAL_VAR({variable_name!r}))")
    stdout_value = result.stdout.strip()
    if stdout_value:
        return stdout_value
    return result.stderr.strip() or ""


def _extract_final_payload(text: str) -> str | None:
    final_match = re.search(r"^\s*FINAL\((.*)\)\s*$", text, re.MULTILINE | re.DOTALL)
    if final_match is None:
        return None
    return final_match.group(1).strip()


def _consume_environment_final_answer(environment: "BaseEnv | None") -> str | None:
    if environment is None:
        return None
    consume = getattr(environment, "consume_final_answer", None)
    if not callable(consume):
        return None
    final_answer = consume()
    if final_answer is None:
        return None
    return str(final_answer)


def _collect_execution_result_parts(result: REPLResult) -> list[str]:
    result_parts: list[str] = []
    if result.stdout:
        result_parts.append(f"\n{result.stdout}")
    if result.stderr:
        result_parts.append(f"\n{result.stderr}")

    visible_keys = _get_visible_local_keys(result)
    if visible_keys:
        result_parts.append(f"REPL variables: {visible_keys}\n")
    return result_parts


def _get_visible_local_keys(result: REPLResult) -> list[str]:
    hidden_keys = {"__builtins__", "__name__", "__doc__"}
    return [
        key
        for key, value in result.locals.items()
        if not key.startswith("_")
        and key not in hidden_keys
        and isinstance(value, (str, int, float, bool, list, dict, tuple))
    ]


def _convert_list_context(context_list: list[Any]) -> tuple[Any, str | None]:
    if not context_list:
        return context_list, None

    first_item = context_list[0]
    if not isinstance(first_item, dict):
        return context_list, None

    first_message = cast(dict[str, Any], first_item)
    if "content" not in first_message:
        return context_list, None

    context_data = [
        cast(dict[str, Any], msg).get("content", "")
        for msg in context_list
        if isinstance(msg, dict)
    ]
    return context_data, None
