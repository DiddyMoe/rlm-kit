from collections.abc import Callable
from typing import Any

from rlm.clients.base_lm import BaseLM
from rlm.core.lm_handler import LMHandler
from rlm.core.types import ModelUsageSummary, UsageSummary


class DummyLM(BaseLM):
    def completion(self, prompt: str | list[dict[str, Any]]) -> str:
        return f"{self.model_name}:{prompt}"

    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str:
        return self.completion(prompt)

    def get_usage_summary(self) -> UsageSummary:
        return UsageSummary(
            model_usage_summaries={
                self.model_name: ModelUsageSummary(
                    total_calls=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                )
            }
        )

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=0,
            total_input_tokens=0,
            total_output_tokens=0,
        )

    def stream_completion(
        self,
        prompt: str | list[dict[str, Any]],
        on_chunk: Callable[[str], None],
        model: str | None = None,
    ) -> str:
        _ = model
        output = f"{self.model_name}:{prompt}"
        on_chunk(f"{self.model_name}:")
        on_chunk(str(prompt))
        return output


def test_get_client_routes_other_backend_for_depth_greater_than_one() -> None:
    root_client = DummyLM("root-model")
    sub_client = DummyLM("sub-model")
    handler = LMHandler(root_client, other_backend_client=sub_client)

    assert handler.get_client(depth=2).model_name == "sub-model"


def test_get_client_uses_model_preferences_direct_model() -> None:
    root_client = DummyLM("root-model")
    preferred_client = DummyLM("gpt-4o-mini")
    handler = LMHandler(root_client)
    handler.register_client(preferred_client.model_name, preferred_client)

    selected = handler.get_client(model_preferences={"model": "gpt-4o-mini"})
    assert selected.model_name == "gpt-4o-mini"


def test_get_client_uses_model_preferences_family_match() -> None:
    root_client = DummyLM("root-model")
    family_client = DummyLM("anthropic/claude-3-5-sonnet")
    handler = LMHandler(root_client)
    handler.register_client(family_client.model_name, family_client)

    selected = handler.get_client(model_preferences={"family": "claude"})
    assert selected.model_name == "anthropic/claude-3-5-sonnet"


def test_direct_completion_streams_chunks_when_callback_provided() -> None:
    root_client = DummyLM("root-model")
    handler = LMHandler(root_client)
    emitted: list[str] = []

    result = handler.completion("hello", on_chunk=emitted.append)

    assert result == "root-model:hello"
    assert emitted == ["root-model:", "hello"]
