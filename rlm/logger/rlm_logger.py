"""
Logger for RLM iterations.

Writes RLMIteration data to JSON-lines files for analysis and debugging.
Supports optional max file size with rotation to a new file (same schema per file).
"""

import json
import os
import uuid
from datetime import datetime

from rlm.core.types import RLMIteration, RLMMetadata


class RLMLogger:
    """Logger that writes RLMIteration data to a JSON-lines file.

    Optional max_file_bytes: when set, the logger rotates to a new file when the
    current file would exceed this size. Each file remains valid JSONL (metadata
    line first, then iteration lines). Schema unchanged.
    """

    def __init__(
        self,
        log_dir: str,
        file_name: str = "rlm",
        max_file_bytes: int | None = None,
    ):
        self.log_dir = log_dir
        self.file_name = file_name
        self.max_file_bytes = max_file_bytes  # None = no rotation
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = str(uuid.uuid4())[:8]
        self.log_file_path = os.path.join(log_dir, f"{file_name}_{timestamp}_{self.run_id}.jsonl")

        self._iteration_count = 0
        self._metadata_logged = False
        self._last_metadata: RLMMetadata | None = None

    def _rotate_if_needed(self, next_entry_size: int) -> None:
        """If max_file_bytes set and current file would exceed it, start a new file."""
        if self.max_file_bytes is None:
            return
        try:
            current_size = os.path.getsize(self.log_file_path)
        except OSError:
            return
        if current_size + next_entry_size <= self.max_file_bytes:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = str(uuid.uuid4())[:8]
        self.log_file_path = os.path.join(
            self.log_dir, f"{self.file_name}_{timestamp}_{self.run_id}.jsonl"
        )
        self._metadata_logged = False

        if self._last_metadata is not None:
            meta_dict = self._last_metadata.to_dict()
            meta_dict["run_id"] = self.run_id
            entry = {
                "type": "metadata",
                "timestamp": datetime.now().isoformat(),
                **meta_dict,
            }
            with open(self.log_file_path, "a") as f:
                json.dump(entry, f)
                f.write("\n")
            self._metadata_logged = True

    def log_metadata(self, metadata: RLMMetadata):
        """Log RLM metadata as the first entry in the file."""
        if self._metadata_logged:
            return

        self._last_metadata = metadata
        entry = {
            "type": "metadata",
            "timestamp": datetime.now().isoformat(),
            **metadata.to_dict(),
        }

        with open(self.log_file_path, "a") as f:
            json.dump(entry, f)
            f.write("\n")

        self._metadata_logged = True

    def log(self, iteration: RLMIteration):
        """Log an RLMIteration to the file."""
        self._iteration_count += 1

        entry = {
            "type": "iteration",
            "iteration": self._iteration_count,
            "timestamp": datetime.now().isoformat(),
            **iteration.to_dict(),
        }
        line = json.dumps(entry) + "\n"
        next_size = len(line.encode("utf-8"))

        self._rotate_if_needed(next_size)

        with open(self.log_file_path, "a") as f:
            f.write(line)

    @property
    def iteration_count(self) -> int:
        return self._iteration_count
