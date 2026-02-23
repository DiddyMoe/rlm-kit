"""Call history tracking for LLM debugging.

Tracks all LLM calls (prompts, responses, token usage) for debugging and analysis.
Supports JSON export for IDE debugging tools.
"""

import json
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CallHistoryEntry:
    """Entry in the call history tracking a single LLM call."""

    call_id: str
    timestamp: float
    model: str
    prompt: str | dict[str, Any]
    response: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CallHistoryEntry":
        """Create from dictionary."""
        return cls(**data)


class CallHistory:
    """Track all LLM calls for debugging and analysis."""

    def __init__(self) -> None:
        """Initialize empty call history."""
        self.entries: list[CallHistoryEntry] = []
        self._call_counter: int = 0

    def add_call(
        self,
        model: str,
        prompt: str | dict[str, Any],
        response: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        execution_time: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CallHistoryEntry:
        """Add a call to the history.

        Args:
            model: Model name used for the call
            prompt: Prompt sent to the model
            response: Response received from the model
            input_tokens: Number of input tokens (optional)
            output_tokens: Number of output tokens (optional)
            total_tokens: Total tokens (optional, calculated if not provided)
            execution_time: Execution time in seconds (optional)
            metadata: Additional metadata (optional)

        Returns:
            The created CallHistoryEntry
        """
        self._call_counter += 1
        call_id = f"call_{self._call_counter}_{int(time.time())}"

        # Calculate total tokens if not provided
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        entry = CallHistoryEntry(
            call_id=call_id,
            timestamp=time.time(),
            model=model,
            prompt=prompt,
            response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            execution_time=execution_time,
            metadata=metadata or {},
        )

        self.entries.append(entry)
        return entry

    def add_from_rlm_completion(
        self,
        completion: Any,  # RLMChatCompletion
        metadata: dict[str, Any] | None = None,
    ) -> CallHistoryEntry:
        """Add a call from an RLMChatCompletion object.

        Args:
            completion: RLMChatCompletion object
            metadata: Additional metadata (optional)

        Returns:
            The created CallHistoryEntry
        """
        usage = completion.usage_summary
        model_usage = usage.model_usage_summaries.get(completion.root_model)

        input_tokens = None
        output_tokens = None
        total_tokens = None

        if model_usage:
            input_tokens = model_usage.total_input_tokens
            output_tokens = model_usage.total_output_tokens
            total_tokens = model_usage.total_input_tokens + model_usage.total_output_tokens

        return self.add_call(
            model=completion.root_model,
            prompt=completion.prompt,
            response=completion.response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            execution_time=completion.execution_time,
            metadata=metadata,
        )

    def get_calls(
        self,
        model: str | None = None,
        limit: int | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[CallHistoryEntry]:
        """Get filtered call history entries.

        Args:
            model: Filter by model name (optional)
            limit: Maximum number of entries to return (optional)
            start_time: Filter entries after this timestamp (optional)
            end_time: Filter entries before this timestamp (optional)

        Returns:
            List of matching CallHistoryEntry objects
        """
        return self._apply_filters(
            model=model,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def _apply_filters(
        self,
        model: str | None,
        start_time: float | None,
        end_time: float | None,
        limit: int | None,
    ) -> list[CallHistoryEntry]:
        filtered = self._filter_by_model(self.entries, model)
        filtered = self._filter_by_start_time(filtered, start_time)
        filtered = self._filter_by_end_time(filtered, end_time)
        return self._apply_limit(filtered, limit)

    def _filter_by_model(
        self, entries: list[CallHistoryEntry], model: str | None
    ) -> list[CallHistoryEntry]:
        if model is None:
            return entries
        return [entry for entry in entries if entry.model == model]

    def _filter_by_start_time(
        self, entries: list[CallHistoryEntry], start_time: float | None
    ) -> list[CallHistoryEntry]:
        if start_time is None:
            return entries
        return [entry for entry in entries if entry.timestamp >= start_time]

    def _filter_by_end_time(
        self, entries: list[CallHistoryEntry], end_time: float | None
    ) -> list[CallHistoryEntry]:
        if end_time is None:
            return entries
        return [entry for entry in entries if entry.timestamp <= end_time]

    def _apply_limit(
        self, entries: list[CallHistoryEntry], limit: int | None
    ) -> list[CallHistoryEntry]:
        if limit is None:
            return entries
        return entries[-limit:]

    def _model_statistics(self) -> dict[str, dict[str, Any]]:
        model_stats: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
            if entry.model not in model_stats:
                model_stats[entry.model] = {
                    "call_count": 0,
                    "total_tokens": 0,
                    "total_execution_time": 0.0,
                }

            model_stats[entry.model]["call_count"] += 1
            if entry.total_tokens is not None:
                model_stats[entry.model]["total_tokens"] += entry.total_tokens
            if entry.execution_time is not None:
                model_stats[entry.model]["total_execution_time"] += entry.execution_time

        return model_stats

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the call history.

        Returns:
            Dictionary with statistics
        """
        if not self.entries:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_execution_time": 0.0,
                "models": {},
            }

        total_tokens = sum(e.total_tokens or 0 for e in self.entries if e.total_tokens is not None)
        total_execution_time = sum(
            e.execution_time or 0.0 for e in self.entries if e.execution_time is not None
        )

        models = self._model_statistics()

        return {
            "total_calls": len(self.entries),
            "total_tokens": total_tokens,
            "total_execution_time": total_execution_time,
            "models": models,
        }

    def export_json(self, filepath: str, indent: int = 2) -> None:
        """Export call history to JSON file.

        Args:
            filepath: Path to output JSON file
            indent: JSON indentation level
        """
        data: dict[str, Any] = {
            "metadata": {
                "export_timestamp": time.time(),
                "total_calls": len(self.entries),
            },
            "calls": [entry.to_dict() for entry in self.entries],
            "statistics": self.get_statistics(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert call history to dictionary for serialization.

        Returns:
            Dictionary representation of call history
        """
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CallHistory":
        """Create CallHistory from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            CallHistory instance
        """
        history = cls()
        for entry_data in data.get("entries", []):
            history.entries.append(CallHistoryEntry.from_dict(entry_data))
        return history

    def clear(self) -> None:
        """Clear all call history entries."""
        self.entries.clear()
        self._call_counter = 0
