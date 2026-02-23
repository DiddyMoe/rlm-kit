"""Tests for RLMConfig constructor support."""

from typing import Any, cast

import pytest

from rlm.core.rlm import RLM, RLMConfig


class TestRLMConfigConstructor:
    def test_accepts_config_object(self) -> None:
        config = RLMConfig(
            backend="openai",
            backend_kwargs={"model_name": "gpt-4o-mini"},
            max_iterations=12,
            compaction=True,
        )

        rlm = RLM(config)

        assert rlm.backend == "openai"
        assert rlm.backend_kwargs == {"model_name": "gpt-4o-mini"}
        assert rlm.max_iterations == 12
        assert rlm.compaction is True

    def test_rejects_additional_init_args(self) -> None:
        config = RLMConfig(backend="openai")

        with pytest.raises(TypeError):
            cast(Any, RLM)(config, max_iterations=50)
