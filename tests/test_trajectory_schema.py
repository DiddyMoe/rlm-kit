"""Test that RLMLogger JSONL output has expected schema keys (test-side validation only).

No production write path change. Schema is documented in docs/index/trajectory_logging_coverage.md.
"""

import json
import tempfile
from pathlib import Path

from rlm.core.types import (
    CodeBlock,
    ModelUsageSummary,
    REPLResult,
    RLMChatCompletion,
    RLMIteration,
    RLMMetadata,
    UsageSummary,
)
from rlm.logger.rlm_logger import RLMLogger

# Expected top-level keys per doc (trajectory_logging_coverage.md)
METADATA_KEYS = {
    "type",
    "timestamp",
    "root_model",
    "max_depth",
    "max_iterations",
    "backend",
    "backend_kwargs",
    "environment_type",
    "environment_kwargs",
    "other_backends",
    "run_id",  # optional; present in metadata line for trajectory correlation
}

ITERATION_KEYS = {
    "type",
    "iteration",
    "timestamp",
    "prompt",
    "response",
    "code_blocks",
    "final_answer",
    "iteration_time",
}

REPL_RESULT_KEYS = {"stdout", "stderr", "locals", "execution_time", "rlm_calls"}


def test_trajectory_jsonl_metadata_line_has_expected_keys():
    """First line of trajectory JSONL must be metadata with expected keys."""
    with tempfile.TemporaryDirectory() as log_dir:
        logger = RLMLogger(log_dir=log_dir, file_name="rlm")
        metadata = RLMMetadata(
            root_model="test-model",
            max_depth=1,
            max_iterations=5,
            backend="openai",
            backend_kwargs={},
            environment_type="local",
            environment_kwargs={},
            other_backends=None,
        )
        logger.log_metadata(metadata)

        path = Path(log_dir)
        files = list(path.glob("*.jsonl"))
        assert len(files) == 1
        with open(files[0]) as f:
            first_line = json.loads(f.readline())

        assert first_line.get("type") == "metadata"
        assert METADATA_KEYS.issubset(first_line.keys()), (
            f"Missing keys: {METADATA_KEYS - first_line.keys()}"
        )


def test_trajectory_jsonl_iteration_line_has_expected_keys():
    """Iteration line must have expected keys; code_blocks[].result must have REPL result keys."""
    usage = UsageSummary(model_usage_summaries={"gpt-4": ModelUsageSummary(1, 10, 20)})
    rlm_call = RLMChatCompletion(
        root_model="gpt-4",
        prompt="test",
        response="ok",
        usage_summary=usage,
        execution_time=0.1,
    )
    result = REPLResult(
        stdout="",
        stderr="",
        locals={},
        execution_time=0.0,
        rlm_calls=[rlm_call],
    )
    block = CodeBlock(code="1+1", result=result)
    iteration = RLMIteration(
        prompt="q",
        response="a",
        code_blocks=[block],
        final_answer=None,
        iteration_time=1.0,
    )

    with tempfile.TemporaryDirectory() as log_dir:
        logger = RLMLogger(log_dir=log_dir, file_name="rlm")
        metadata = RLMMetadata(
            root_model="test",
            max_depth=1,
            max_iterations=5,
            backend="openai",
            backend_kwargs={},
            environment_type="local",
            environment_kwargs={},
            other_backends=None,
        )
        logger.log_metadata(metadata)
        logger.log(iteration)

        path = Path(log_dir)
        files = list(path.glob("*.jsonl"))
        assert len(files) == 1
        lines = [json.loads(line) for line in open(files[0])]
        assert len(lines) == 2

        iter_line = lines[1]
        assert iter_line.get("type") == "iteration"
        assert ITERATION_KEYS.issubset(iter_line.keys()), (
            f"Missing keys: {ITERATION_KEYS - iter_line.keys()}"
        )
        code_blocks = iter_line.get("code_blocks", [])
        assert len(code_blocks) == 1
        assert "result" in code_blocks[0]
        assert REPL_RESULT_KEYS.issubset(code_blocks[0]["result"].keys()), (
            f"Missing result keys: {REPL_RESULT_KEYS - code_blocks[0]['result'].keys()}"
        )


class TestRLMLoggerInMemory:
    """Tests for RLMLogger with log_dir=None (in-memory only mode)."""

    def _make_metadata(self) -> RLMMetadata:
        return RLMMetadata(
            root_model="test",
            max_depth=1,
            max_iterations=5,
            backend="openai",
            backend_kwargs={},
            environment_type="local",
            environment_kwargs={},
        )

    def _make_iteration(self) -> RLMIteration:
        result = REPLResult(stdout="hi", stderr="", locals={})
        block = CodeBlock(code="print('hi')", result=result)
        return RLMIteration(
            prompt="p",
            response="r",
            code_blocks=[block],
            final_answer=None,
            iteration_time=0.5,
        )

    def test_in_memory_does_not_crash(self):
        logger = RLMLogger(log_dir=None)
        logger.log_metadata(self._make_metadata())
        logger.log(self._make_iteration())
        assert logger.iteration_count == 1

    def test_in_memory_no_file_created(self):
        logger = RLMLogger(log_dir=None)
        assert logger.log_file_path is None

    def test_get_trajectory_captures_iterations(self):
        logger = RLMLogger(log_dir=None)
        logger.log_metadata(self._make_metadata())
        logger.log(self._make_iteration())
        logger.log(self._make_iteration())

        traj = logger.get_trajectory()
        assert "run_metadata" in traj
        assert "iterations" in traj
        assert len(traj["iterations"]) == 2
        assert traj["run_metadata"]["root_model"] == "test"

    def test_clear_iterations_resets_state(self):
        logger = RLMLogger(log_dir=None)
        logger.log_metadata(self._make_metadata())
        logger.log(self._make_iteration())
        assert logger.iteration_count == 1

        logger.clear_iterations()
        assert logger.iteration_count == 0

        traj = logger.get_trajectory()
        assert len(traj["iterations"]) == 0
        # run_metadata persists across clears
        assert traj["run_metadata"]["root_model"] == "test"

    def test_disk_mode_also_captures_in_memory(self):
        with tempfile.TemporaryDirectory() as log_dir:
            logger = RLMLogger(log_dir=log_dir)
            logger.log_metadata(self._make_metadata())
            logger.log(self._make_iteration())

            traj = logger.get_trajectory()
            assert len(traj["iterations"]) == 1
