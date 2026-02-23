"""
Logger for RLM iterations.

Writes RLMIteration data to JSON-lines files for analysis and debugging.
Supports optional max file size with rotation to a new file (same schema per file).
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

from rlm.core.types import RLMIteration, RLMMetadata


class RLMLogger:
    """Logger that writes RLMIteration data to a JSON-lines file.

    When *log_dir* is ``None`` the logger operates in **in-memory only** mode:
    iterations are captured for ``get_trajectory()`` but nothing is written to
    disk.  When *log_dir* is a path string, behaviour is identical to the
    original disk-logging mode.

    Optional max_file_bytes: when set, the logger rotates to a new file when the
    current file would exceed this size. Each file remains valid JSONL (metadata
    line first, then iteration lines). Schema unchanged.
    """

    def __init__(
        self,
        log_dir: str | None,
        file_name: str = "rlm",
        max_file_bytes: int | None = None,
    ) -> None:
        self.log_dir = log_dir
        self.file_name = file_name
        self.max_file_bytes = max_file_bytes  # None = no rotation

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = str(uuid.uuid4())[:8]

        # In-memory iteration store (always populated)
        self._iterations: list[dict[str, Any]] = []

        if log_dir is not None:
            os.makedirs(log_dir, exist_ok=True)
            self.log_file_path: str | None = os.path.join(
                log_dir, f"{file_name}_{timestamp}_{self.run_id}.jsonl"
            )
        else:
            self.log_file_path = None

        self._iteration_count = 0
        self._metadata_logged = False
        self._last_metadata: RLMMetadata | None = None

    def _rotate_if_needed(self, next_entry_size: int) -> None:
        """If max_file_bytes set and current file would exceed it, start a new file."""
        if self.max_file_bytes is None or self.log_file_path is None:
            return
        try:
            current_size = os.path.getsize(self.log_file_path)
        except OSError:
            return
        if current_size + next_entry_size <= self.max_file_bytes:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = str(uuid.uuid4())[:8]
        assert self.log_dir is not None  # guarded by log_file_path check above
        self.log_file_path = os.path.join(
            self.log_dir, f"{self.file_name}_{timestamp}_{self.run_id}.jsonl"
        )
        self._metadata_logged = False

        if self._last_metadata is not None:
            meta_dict = self._last_metadata.to_dict()
            meta_dict["run_id"] = self.run_id
            entry: dict[str, Any] = {
                "type": "metadata",
                "timestamp": datetime.now().isoformat(),
                **meta_dict,
            }
            with open(self.log_file_path, "a") as f:
                json.dump(entry, f)
                f.write("\n")
            self._metadata_logged = True

    def log_metadata(self, metadata: RLMMetadata) -> None:
        """Log RLM metadata as the first entry in the file."""
        if self._metadata_logged:
            return

        self._last_metadata = metadata
        entry: dict[str, Any] = {
            "type": "metadata",
            "timestamp": datetime.now().isoformat(),
            **metadata.to_dict(),
        }

        if self.log_file_path is not None:
            with open(self.log_file_path, "a") as f:
                json.dump(entry, f)
                f.write("\n")

        self._metadata_logged = True

    def log(self, iteration: RLMIteration) -> None:
        """Log an RLMIteration to the file (and always to memory)."""
        self._iteration_count += 1

        entry: dict[str, Any] = {
            "type": "iteration",
            "iteration": self._iteration_count,
            "timestamp": datetime.now().isoformat(),
            **iteration.to_dict(),
        }

        # Always capture in memory for get_trajectory()
        self._iterations.append(entry)

        if self.log_file_path is not None:
            line = json.dumps(entry) + "\n"
            next_size = len(line.encode("utf-8"))
            self._rotate_if_needed(next_size)
            with open(self.log_file_path, "a") as f:
                f.write(line)

    @property
    def iteration_count(self) -> int:
        return self._iteration_count

    def clear_iterations(self) -> None:
        """Reset in-memory iteration store for a new completion call."""
        self._iterations.clear()
        self._iteration_count = 0

    def get_trajectory(self) -> dict[str, Any]:
        """Return the in-memory trajectory for the current completion.

        Returns a dict with ``run_metadata`` (from the last ``log_metadata`` call)
        and ``iterations`` (list of iteration dicts captured by ``log``).
        """
        run_metadata: dict[str, Any] = {}
        if self._last_metadata is not None:
            run_metadata = self._last_metadata.to_dict()
            run_metadata["run_id"] = self.run_id
        return {
            "run_metadata": run_metadata,
            "iterations": list(self._iterations),
        }
