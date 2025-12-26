"""
Logger for RLM iterations.

Writes RLMIteration data to JSON-lines files for analysis and debugging.
"""

from rlm.core.types import RLMIteration

from datetime import datetime
import json
import uuid
import os


class RLMLogger:
    """Logger that writes RLMIteration data to a JSON-lines file."""

    def __init__(self, log_dir: str, file_name: str = "rlm"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_id = str(uuid.uuid4())[:8]
        self.log_file_path = os.path.join(
            log_dir, f"{file_name}_{timestamp}_{run_id}.jsonl"
        )

        self._iteration_count = 0

    def log(self, iteration: RLMIteration):
        """Log an RLMIteration to the file."""
        self._iteration_count += 1

        entry = {
            "iteration": self._iteration_count,
            "timestamp": datetime.now().isoformat(),
            **iteration.to_dict(),
        }

        with open(self.log_file_path, "a") as f:
            json.dump(entry, f)
            f.write("\n")

    @property
    def iteration_count(self) -> int:
        return self._iteration_count
