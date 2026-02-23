"""Integration tests for context compaction in the RLM main loop.

Tests that:
1. Compaction is triggered when token usage exceeds threshold
2. History is preserved in REPL `history` variable during compaction
3. Compaction summarizes and continues from a compact message history
4. append_compaction_entry works correctly on LocalREPL
"""

from typing import Any, cast
from unittest.mock import Mock, patch

import rlm.core.rlm as rlm_module
from rlm import RLM
from rlm.core.rlm import RLMConfig
from rlm.core.types import ModelUsageSummary, UsageSummary
from rlm.environments.local_repl import LocalREPL


def _mock_usage() -> UsageSummary:
    return UsageSummary(
        model_usage_summaries={
            "mock": ModelUsageSummary(total_calls=1, total_input_tokens=100, total_output_tokens=50)
        }
    )


class TestCompactionInit:
    """Test compaction parameter passthrough."""

    def test_compaction_defaults_to_off(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_get_client.return_value = mock_lm
            rlm = RLM(RLMConfig(backend="openai", backend_kwargs={"model_name": "test"}))
            assert rlm.compaction is False
            assert rlm.compaction_threshold_pct == 0.85

    def test_compaction_enabled(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_get_client.return_value = mock_lm
            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "test"},
                    compaction=True,
                    compaction_threshold_pct=0.5,
                )
            )
            assert rlm.compaction is True
            assert rlm.compaction_threshold_pct == 0.5


class TestCompactHistory:
    """Test the _compact_history helper."""

    def test_compact_history_returns_short_history(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.completion.return_value = "Summary of progress"
            mock_lm.get_usage_summary.return_value = _mock_usage()
            mock_lm.get_last_usage.return_value = _mock_usage()
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "test"},
                    compaction=True,
                )
            )

            # Build a realistic message history
            original_history = [
                {"role": "system", "content": "You are helpful."},
                {"role": "assistant", "content": "Context metadata."},
                {"role": "user", "content": "Long user message..."},
                {"role": "assistant", "content": "Long assistant reply..."},
                {"role": "user", "content": "Another long message..."},
            ]

            env = LocalREPL(context_payload="test context")

            from rlm.core.lm_handler import LMHandler

            lm_handler = LMHandler(mock_lm)
            lm_handler.start()
            try:
                new_history = cast(Any, rlm)._compact_history(lm_handler, env, original_history, 1)
            finally:
                lm_handler.stop()

            # Should keep first 2 messages (system + metadata), add summary + continue
            assert len(new_history) == 4
            assert new_history[0]["role"] == "system"
            assert new_history[1]["role"] == "assistant"
            assert new_history[2]["role"] == "assistant"
            assert new_history[2]["content"] == "Summary of progress"
            assert "compacted 1 time" in new_history[3]["content"]

            env.cleanup()


class TestAppendCompactionEntry:
    """Test LocalREPL.append_compaction_entry."""

    def test_append_list_entry(self) -> None:
        repl = LocalREPL(context_payload="test")
        repl.append_compaction_entry([{"role": "user", "content": "msg"}])
        assert "history" in repl.locals
        assert len(repl.locals["history"]) == 1
        assert repl.locals["history"][0]["content"] == "msg"
        repl.cleanup()

    def test_append_dict_entry(self) -> None:
        repl = LocalREPL(context_payload="test")
        repl.append_compaction_entry({"type": "summary", "content": "summarized"})
        assert "history" in repl.locals
        assert len(repl.locals["history"]) == 1
        assert repl.locals["history"][0]["type"] == "summary"
        repl.cleanup()

    def test_append_accumulates(self) -> None:
        repl = LocalREPL(context_payload="test")
        repl.append_compaction_entry([{"role": "user", "content": "a"}])
        repl.append_compaction_entry([{"role": "assistant", "content": "b"}])
        assert len(repl.locals["history"]) == 2
        repl.cleanup()

    def test_scaffold_backup_updated(self) -> None:
        repl = LocalREPL(context_payload="test")
        repl.append_compaction_entry([{"role": "user", "content": "msg"}])
        attribute_name = "_scaffold_backup"
        scaffold_backup = cast(dict[str, Any], getattr(repl, attribute_name))
        assert scaffold_backup["history"] is repl.locals["history"]
        repl.cleanup()


class TestGetCompactionStatus:
    """Test the _get_compaction_status method."""

    def test_returns_three_ints(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_get_client.return_value = mock_lm
            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "gpt-4o"},
                    compaction=True,
                )
            )

            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ]
            current, threshold, maximum = cast(Any, rlm)._get_compaction_status(messages)
            assert isinstance(current, int)
            assert isinstance(threshold, int)
            assert isinstance(maximum, int)
            assert maximum == 128_000
            # Threshold should be 85% of max
            assert threshold == int(0.85 * 128_000)
            # Current tokens for these short messages should be much less than threshold
            assert current < threshold


class TestCompactionInLoop:
    """Integration-level compaction trigger check in the RLM loop."""

    def test_compaction_triggers_in_iteration_loop(self) -> None:
        with patch.object(rlm_module, "get_client") as mock_get_client:
            mock_lm = Mock()
            mock_lm.completion.return_value = "FINAL(compacted answer)"
            mock_lm.get_usage_summary.return_value = _mock_usage()
            mock_lm.get_last_usage.return_value = _mock_usage()
            mock_get_client.return_value = mock_lm

            rlm = RLM(
                RLMConfig(
                    backend="openai",
                    backend_kwargs={"model_name": "test"},
                    compaction=True,
                    max_iterations=3,
                )
            )

            def _copy_history(
                _handler: Any,
                _env: Any,
                history: list[dict[str, Any]],
                _count: int,
            ) -> list[dict[str, Any]]:
                return list(history)

            compact_history_mock = Mock(side_effect=_copy_history)

            with (
                patch.object(rlm, "_get_compaction_status", return_value=(900, 100, 1000)),
                patch.object(rlm, "_compact_history", compact_history_mock),
            ):
                result = rlm.completion("please compact before answering")

            assert result.response == "compacted answer"
            assert compact_history_mock.call_count >= 1
