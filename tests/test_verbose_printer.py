from __future__ import annotations

from unittest.mock import MagicMock

from rlm.core.types import CodeBlock, REPLResult, RLMIteration, RLMMetadata
from rlm.logger.verbose import VerbosePrinter


class TestVerbosePrinter:
    def test_disabled_mode_no_console_output(self) -> None:
        printer = VerbosePrinter(enabled=False)
        printer.console.print = MagicMock()

        printer.print_header("openai", "gpt-4o", "local", 10, 2)
        printer.print_compaction()
        printer.print_final_answer("answer")

        printer.console.print.assert_not_called()

    def test_print_iteration_outputs_response_and_execution(self) -> None:
        printer = VerbosePrinter(enabled=True)
        printer.console.print = MagicMock()

        repl_result = REPLResult(
            stdout="hello",
            stderr="",
            locals={"x": 1},
            execution_time=0.1,
            rlm_calls=[],
        )
        code_block = CodeBlock(code="print('hello')", result=repl_result)
        iteration = RLMIteration(
            prompt="test prompt",
            response="working",
            code_blocks=[code_block],
            iteration_time=0.2,
        )

        printer.print_iteration(iteration, 1)

        assert printer.console.print.call_count >= 3

    def test_print_metadata_uses_header_values(self) -> None:
        printer = VerbosePrinter(enabled=True)
        printer.print_header = MagicMock()

        metadata = RLMMetadata(
            root_model="gpt-4o-mini",
            max_depth=3,
            max_iterations=30,
            backend="openai",
            backend_kwargs={"model_name": "gpt-4o-mini"},
            environment_type="local",
            environment_kwargs={},
            other_backends=[],
        )

        printer.print_metadata(metadata)

        printer.print_header.assert_called_once()
