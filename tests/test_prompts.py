from rlm.core.types import QueryMetadata
from rlm.utils.prompts import RLM_SYSTEM_PROMPT, build_rlm_system_prompt, build_user_prompt


def test_system_prompt_contains_reasoning_and_math_examples() -> None:
    assert "math.atan2" in RLM_SYSTEM_PROMPT
    assert "sqrt 2 irrational" in RLM_SYSTEM_PROMPT


def test_build_rlm_system_prompt_includes_metadata_and_custom_tools() -> None:
    metadata = QueryMetadata("example context")
    messages = build_rlm_system_prompt(
        system_prompt=RLM_SYSTEM_PROMPT,
        query_metadata=metadata,
        custom_tools={"fetch_docs": "Fetch docs", "rank": "Rank candidates"},
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "`fetch_docs`" in messages[0]["content"]
    assert "`rank`" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "context" in messages[1]["content"].lower()


def test_custom_tools_numbered_starting_at_six() -> None:
    """RF-088: Custom tools should be numbered starting at 6."""
    metadata = QueryMetadata("ctx")
    messages = build_rlm_system_prompt(
        system_prompt=RLM_SYSTEM_PROMPT,
        query_metadata=metadata,
        custom_tools={"alpha": "First tool", "beta": "", "gamma": "Third tool"},
    )

    content = messages[0]["content"]
    assert "6. A `alpha` function: First tool" in content
    assert "7. A `beta` function available as a custom tool." in content
    assert "8. A `gamma` function: Third tool" in content
    # Custom tool entries should not use numbers below 6
    assert "1. A `alpha" not in content
    assert "2. A `alpha" not in content


def test_custom_tools_empty_dict_no_section() -> None:
    metadata = QueryMetadata("ctx")
    messages = build_rlm_system_prompt(
        system_prompt=RLM_SYSTEM_PROMPT,
        query_metadata=metadata,
        custom_tools={},
    )
    assert "Additional custom tools" not in messages[0]["content"]


def test_build_user_prompt_iteration_zero_single_context_no_history() -> None:
    message = build_user_prompt(root_prompt="Q", iteration=0, context_count=1, history_count=0)
    content = message["content"]
    assert "You have not interacted with the REPL environment" in content
    assert "context_0 through" not in content
    assert "prior conversation history" not in content


def test_build_user_prompt_iteration_zero_multi_context_single_history() -> None:
    message = build_user_prompt(root_prompt="Q", iteration=0, context_count=3, history_count=1)
    content = message["content"]
    assert "You have not interacted with the REPL environment" in content
    assert "context_0 through context_2" in content
    assert "1 prior conversation history" in content


def test_build_user_prompt_iteration_nonzero_single_context_no_history() -> None:
    message = build_user_prompt(root_prompt="Q", iteration=1, context_count=1, history_count=0)
    content = message["content"]
    assert "The history before is your previous interactions" in content
    assert "context_0 through" not in content
    assert "prior conversation history" not in content


def test_build_user_prompt_iteration_nonzero_multi_context_multi_history() -> None:
    message = build_user_prompt(root_prompt="Q", iteration=2, context_count=2, history_count=4)
    content = message["content"]
    assert "The history before is your previous interactions" in content
    assert "context_0 through context_1" in content
    assert "history_0 through history_3" in content
