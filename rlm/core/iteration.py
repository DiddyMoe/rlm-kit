"""RLM iteration logic - extracted for maintainability and testability."""

import time
from collections.abc import Callable
from typing import Any

from rlm.core.lm_handler import LMHandler
from rlm.core.types import CodeBlock, REPLResult, RLMIteration, SnippetProvenance
from rlm.environments import BaseEnv, SupportsPersistence
from rlm.utils.parsing import find_code_blocks, find_final_answer, format_iteration
from rlm.utils.prompts import build_user_prompt


def run_rlm_iterations(
    max_iterations: int,
    lm_handler: LMHandler,
    environment: BaseEnv,
    message_history: list[dict[str, Any]],
    root_prompt: str | None,
    check_budget: Callable[[LMHandler], None],
    log_iteration: Callable[[RLMIteration], None],
    print_iteration: Callable[[RLMIteration, int], None],
) -> str:
    """
    Run RLM iterations until final answer found or max iterations reached.

    Extracted iteration logic for better maintainability and testability.

    Args:
        max_iterations: Maximum number of iterations
        lm_handler: LM handler for making completion calls
        environment: Execution environment
        message_history: Current message history
        root_prompt: Optional root prompt
        check_budget: Function to check budget limits
        log_iteration: Function to log iteration
        print_iteration: Function to print iteration

    Returns:
        Final answer string
    """
    for i in range(max_iterations):
        # Check budget limits before each iteration
        check_budget(lm_handler)

        # Build current prompt with context metadata
        current_prompt = build_iteration_prompt(message_history, root_prompt, i, environment)

        # Execute one iteration
        iteration = execute_completion_turn(
            prompt=current_prompt,
            lm_handler=lm_handler,
            environment=environment,
        )

        # Check for final answer
        final_answer = find_final_answer(iteration.response, environment=environment)
        iteration.final_answer = final_answer

        # Log and print iteration
        log_iteration(iteration)
        print_iteration(iteration, i + 1)

        # If final answer found, return early
        if final_answer is not None:
            return final_answer

        # Update message history for next iteration
        new_messages = format_iteration(iteration)
        message_history.extend(new_messages)

    # Max iterations reached, return default answer
    return get_default_answer(message_history, lm_handler)


def build_iteration_prompt(
    message_history: list[dict[str, Any]],
    root_prompt: str | None,
    iteration: int,
    environment: BaseEnv,
) -> list[dict[str, Any]]:
    """Build prompt for current iteration with context metadata."""
    # Get context and history counts (flattened conditional)
    context_count = 1
    history_count = 0
    if isinstance(environment, SupportsPersistence):
        context_count = environment.get_context_count()
        history_count = environment.get_history_count()

    user_prompt = build_user_prompt(root_prompt, iteration, context_count, history_count)
    return message_history + [user_prompt]


def execute_completion_turn(
    prompt: str | dict[str, Any],
    lm_handler: LMHandler,
    environment: BaseEnv,
) -> RLMIteration:
    """
    Perform a single iteration of the RLM, including prompting the model
    and code execution + tool execution.
    """
    iter_start = time.perf_counter()
    response = lm_handler.completion(prompt)
    code_block_strs = find_code_blocks(response)
    code_blocks = []

    for code_block_str in code_block_strs:
        code_result: REPLResult = environment.execute_code(code_block_str)
        code_blocks.append(CodeBlock(code=code_block_str, result=code_result))

    iteration_time = time.perf_counter() - iter_start

    # Track context provenance
    context_provenance = extract_context_provenance(prompt)

    return RLMIteration(
        prompt=prompt,
        response=response,
        code_blocks=code_blocks,
        iteration_time=iteration_time,
        context_provenance=context_provenance,
    )


def extract_context_provenance(prompt: str | dict[str, Any]) -> list[SnippetProvenance]:
    """
    Extract provenance information from the prompt/context.

    This tracks where snippets of context originated from for auditability.
    Flattened conditionals for better readability.
    """
    import hashlib

    from rlm.core.types import SnippetProvenance

    provenance: list[SnippetProvenance] = []

    # Handle string prompt (early return)
    if isinstance(prompt, str):
        content_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        provenance.append(SnippetProvenance(content_hash=content_hash, source_type="prompt"))
        return provenance

    # Handle dict prompt with messages
    if not isinstance(prompt, dict):
        return provenance

    messages = prompt.get("messages", [])
    for message in messages:
        content = extract_message_content(message)
        if not content:
            continue

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        provenance.append(SnippetProvenance(content_hash=content_hash, source_type="message"))

    return provenance


def extract_message_content(message: Any) -> str | None:
    """Extract content from message (dict or str)."""
    if isinstance(message, dict):
        return str(message.get("content", ""))
    if isinstance(message, str):
        return message
    return None


def get_default_answer(
    message_history: list[dict[str, Any]],
    lm_handler: LMHandler,
    log_iteration: Callable[[RLMIteration], None] | None = None,
) -> str:
    """
    Default behavior if the RLM runs out of iterations and does not find a final answer.
    It will take the message history, and try to generate a final answer from it.
    """
    from rlm.core.types import RLMIteration

    current_prompt = message_history + [
        {
            "role": "assistant",
            "content": "Please provide a final answer to the user's question based on the information provided.",
        }
    ]
    response = lm_handler.completion(current_prompt)

    if log_iteration:
        log_iteration(
            RLMIteration(
                prompt=current_prompt,
                response=response,
                final_answer=response,
                code_blocks=[],
            )
        )

    return response
