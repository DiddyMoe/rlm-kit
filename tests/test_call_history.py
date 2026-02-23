from __future__ import annotations

from pathlib import Path

from rlm.core.types import ModelUsageSummary, RLMChatCompletion, UsageSummary
from rlm.debugging.call_history import CallHistory, CallHistoryEntry


class TestCallHistoryEntry:
    def test_round_trip_to_dict_from_dict(self) -> None:
        entry = CallHistoryEntry(
            call_id="call_1",
            timestamp=1234.5,
            model="gpt-4o",
            prompt={"role": "user", "content": "hello"},
            response="world",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            execution_time=0.12,
            metadata={"source": "test"},
        )

        restored = CallHistoryEntry.from_dict(entry.to_dict())

        assert restored == entry


class TestCallHistory:
    def test_add_call_and_get_calls_with_filters(self) -> None:
        history = CallHistory()
        first = history.add_call("gpt-4o-mini", "p1", "r1", input_tokens=1, output_tokens=2)
        second = history.add_call("gpt-4o", "p2", "r2", input_tokens=3, output_tokens=4)
        third = history.add_call("gpt-4o", "p3", "r3", input_tokens=5, output_tokens=6)

        assert len(history.get_calls()) == 3
        assert [entry.response for entry in history.get_calls(model="gpt-4o")] == ["r2", "r3"]
        assert [entry.call_id for entry in history.get_calls(limit=2)] == [
            second.call_id,
            third.call_id,
        ]
        assert [entry.call_id for entry in history.get_calls(start_time=second.timestamp)] == [
            second.call_id,
            third.call_id,
        ]
        assert [entry.call_id for entry in history.get_calls(end_time=second.timestamp)] == [
            first.call_id,
            second.call_id,
        ]

    def test_add_from_rlm_completion(self) -> None:
        usage = UsageSummary(
            model_usage_summaries={
                "gpt-4o": ModelUsageSummary(
                    total_calls=1,
                    total_input_tokens=11,
                    total_output_tokens=7,
                )
            }
        )
        completion = RLMChatCompletion(
            root_model="gpt-4o",
            prompt="explain",
            response="answer",
            usage_summary=usage,
            execution_time=0.33,
        )

        history = CallHistory()
        entry = history.add_from_rlm_completion(completion, metadata={"origin": "unit"})

        assert entry.model == "gpt-4o"
        assert entry.prompt == "explain"
        assert entry.response == "answer"
        assert entry.input_tokens == 11
        assert entry.output_tokens == 7
        assert entry.total_tokens == 18
        assert entry.metadata == {"origin": "unit"}

    def test_get_statistics_returns_expected_values(self) -> None:
        history = CallHistory()
        history.add_call("gpt-4o", "p1", "r1", total_tokens=10, execution_time=0.5)
        history.add_call("gpt-4o-mini", "p2", "r2", total_tokens=20, execution_time=0.25)

        stats = history.get_statistics()

        assert stats["total_calls"] == 2
        assert stats["total_tokens"] == 30
        assert stats["total_execution_time"] == 0.75
        assert stats["models"]["gpt-4o"]["call_count"] == 1
        assert stats["models"]["gpt-4o"]["total_tokens"] == 10
        assert stats["models"]["gpt-4o-mini"]["call_count"] == 1

    def test_to_dict_from_dict_round_trip(self) -> None:
        history = CallHistory()
        history.add_call("gpt-4o", "prompt", "response", total_tokens=9)

        restored = CallHistory.from_dict(history.to_dict())

        assert len(restored.entries) == 1
        assert restored.entries[0].model == "gpt-4o"
        assert restored.entries[0].response == "response"

    def test_clear_resets_state(self) -> None:
        history = CallHistory()
        history.add_call("gpt-4o", "p", "r")

        history.clear()

        assert history.entries == []
        next_entry = history.add_call("gpt-4o", "p2", "r2")
        assert next_entry.call_id.startswith("call_1_")

    def test_export_json_writes_valid_payload(self, tmp_path: Path) -> None:
        history = CallHistory()
        history.add_call("gpt-4o", "p", "r", total_tokens=5)

        output = tmp_path / "calls.json"
        history.export_json(str(output))

        payload = output.read_text(encoding="utf-8")
        assert '"metadata"' in payload
        assert '"calls"' in payload
        assert '"statistics"' in payload
