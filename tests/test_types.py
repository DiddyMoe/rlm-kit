"""Tests for core types."""

from typing import Any

import pytest

import rlm.core.types as core_types
from rlm.core.types import (
    CodeBlock,
    ModelUsageSummary,
    QueryMetadata,
    REPLResult,
    RLMChatCompletion,
    RLMIteration,
    RLMMetadata,
    SnippetProvenance,
    UsageSummary,
)


class TestSerializeValue:
    """Tests for _serialize_value helper."""

    @staticmethod
    def _serialize_helper() -> Any:
        attribute_name = "_serialize_value"
        return getattr(core_types, attribute_name)

    def test_primitives(self):
        serialize_value = self._serialize_helper()
        assert serialize_value(None) is None
        assert serialize_value(True) is True
        assert serialize_value(42) == 42
        assert serialize_value(3.14) == 3.14
        assert serialize_value("hello") == "hello"

    def test_list(self):
        serialize_value = self._serialize_helper()
        result = serialize_value([1, 2, "three"])
        assert result == [1, 2, "three"]

    def test_dict(self):
        serialize_value = self._serialize_helper()
        result = serialize_value({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_callable(self):
        def my_func():
            pass

        serialize_value = self._serialize_helper()
        result = serialize_value(my_func)
        assert "function" in result.lower()
        assert "my_func" in result


class TestModelUsageSummary:
    """Tests for ModelUsageSummary."""

    def test_to_dict(self):
        summary = ModelUsageSummary(
            total_calls=10, total_input_tokens=1000, total_output_tokens=500
        )
        d = summary.to_dict()
        assert d["total_calls"] == 10
        assert d["total_input_tokens"] == 1000
        assert d["total_output_tokens"] == 500

    def test_from_dict(self):
        data = {
            "total_calls": 5,
            "total_input_tokens": 200,
            "total_output_tokens": 100,
        }
        summary = ModelUsageSummary.from_dict(data)
        assert summary.total_calls == 5
        assert summary.total_input_tokens == 200
        assert summary.total_output_tokens == 100

    def test_from_dict_missing_keys_defaults_to_zero(self):
        summary = ModelUsageSummary.from_dict({})
        assert summary.total_calls == 0
        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0


class TestUsageSummary:
    """Tests for UsageSummary."""

    def test_to_dict(self):
        model_summary = ModelUsageSummary(
            total_calls=1, total_input_tokens=10, total_output_tokens=5
        )
        summary = UsageSummary(model_usage_summaries={"gpt-4": model_summary})
        d = summary.to_dict()
        assert "gpt-4" in d["model_usage_summaries"]

    def test_from_dict(self):
        data = {
            "model_usage_summaries": {
                "gpt-4": {
                    "total_calls": 2,
                    "total_input_tokens": 50,
                    "total_output_tokens": 25,
                }
            }
        }
        summary = UsageSummary.from_dict(data)
        assert "gpt-4" in summary.model_usage_summaries
        assert summary.model_usage_summaries["gpt-4"].total_calls == 2


class TestREPLResult:
    """Tests for REPLResult."""

    def test_basic_creation(self):
        result = REPLResult(stdout="output", stderr="", locals={"x": 1})
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.locals == {"x": 1}

    def test_to_dict(self):
        result = REPLResult(stdout="hello", stderr="", locals={"num": 42}, execution_time=0.5)
        d = result.to_dict()
        assert d["stdout"] == "hello"
        assert d["locals"]["num"] == 42
        assert d["execution_time"] == 0.5

    def test_str_representation(self):
        result = REPLResult(stdout="test", stderr="", locals={})
        s = str(result)
        assert "REPLResult" in s
        assert "stdout=test" in s

    def test_roundtrip(self):
        usage = UsageSummary(model_usage_summaries={})
        call = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=usage,
            execution_time=0.1,
        )
        result = REPLResult(
            stdout="out",
            stderr="",
            locals={"x": 1},
            execution_time=0.5,
            rlm_calls=[call],
        )
        result2 = REPLResult.from_dict(result.to_dict())
        assert result2.stdout == result.stdout
        assert result2.locals == result.locals
        assert len(result2.rlm_calls) == 1
        assert result2.rlm_calls[0].response == "r"


class TestCodeBlock:
    """Tests for CodeBlock."""

    def test_to_dict(self):
        result = REPLResult(stdout="3", stderr="", locals={"x": 3})
        block = CodeBlock(code="x = 1 + 2", result=result)
        d = block.to_dict()
        assert d["code"] == "x = 1 + 2"
        assert d["result"]["stdout"] == "3"

    def test_roundtrip(self):
        result = REPLResult(stdout="3", stderr="", locals={"x": 3})
        block = CodeBlock(code="x = 1 + 2", result=result)
        block2 = CodeBlock.from_dict(block.to_dict())
        assert block2.code == block.code
        assert block2.result.stdout == "3"


class TestRLMIteration:
    """Tests for RLMIteration."""

    def test_basic_creation(self):
        iteration = RLMIteration(prompt="test prompt", response="test response", code_blocks=[])
        assert iteration.prompt == "test prompt"
        assert iteration.final_answer is None

    def test_with_final_answer(self):
        iteration = RLMIteration(
            prompt="test",
            response="FINAL(42)",
            code_blocks=[],
            final_answer="42",
        )
        assert iteration.final_answer == "42"

    def test_to_dict(self):
        result = REPLResult(stdout="", stderr="", locals={})
        block = CodeBlock(code="pass", result=result)
        iteration = RLMIteration(
            prompt="p",
            response="r",
            code_blocks=[block],
            iteration_time=1.5,
        )
        d = iteration.to_dict()
        assert d["prompt"] == "p"
        assert d["response"] == "r"
        assert len(d["code_blocks"]) == 1
        assert d["iteration_time"] == 1.5

    def test_roundtrip(self):
        result = REPLResult(stdout="ok", stderr="", locals={"a": 1})
        block = CodeBlock(code="a = 1", result=result)
        iteration = RLMIteration(
            prompt="p",
            response="r",
            code_blocks=[block],
            final_answer="42",
            iteration_time=0.3,
        )
        iteration2 = RLMIteration.from_dict(iteration.to_dict())
        assert iteration2.prompt == iteration.prompt
        assert iteration2.final_answer == "42"
        assert len(iteration2.code_blocks) == 1
        assert iteration2.code_blocks[0].result.locals["a"] == 1


class TestQueryMetadata:
    """Tests for QueryMetadata."""

    def test_string_prompt(self):
        meta = QueryMetadata("Hello, world!")
        assert meta.context_type == "str"
        assert meta.context_total_length == 13
        assert meta.context_lengths == [13]

    def test_roundtrip(self):
        meta = QueryMetadata(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "World"},
            ]
        )
        meta2 = QueryMetadata.from_dict(meta.to_dict())
        assert meta2.context_type == meta.context_type
        assert meta2.context_lengths == meta.context_lengths
        assert meta2.context_total_length == meta.context_total_length


class TestRLMMetadata:
    """Tests for RLMMetadata."""

    def test_to_dict(self):
        meta = RLMMetadata(
            root_model="gpt-4",
            max_depth=2,
            max_iterations=10,
            backend="openai",
            backend_kwargs={"api_key": "secret"},
            environment_type="local",
            environment_kwargs={},
        )
        d = meta.to_dict()
        assert d["root_model"] == "gpt-4"
        assert d["max_depth"] == 2
        assert d["backend"] == "openai"

    def test_roundtrip(self):
        meta = RLMMetadata(
            root_model="gpt-4",
            max_depth=2,
            max_iterations=10,
            backend="openai",
            backend_kwargs={"api_key": "secret"},
            environment_type="local",
            environment_kwargs={"persistent": True},
            run_id="run-123",
        )
        meta2 = RLMMetadata.from_dict(meta.to_dict())
        assert meta2.root_model == meta.root_model
        assert meta2.backend_kwargs["api_key"] == "secret"
        assert meta2.environment_kwargs["persistent"] is True
        assert meta2.run_id == "run-123"


class TestSnippetProvenance:
    def test_roundtrip(self):
        provenance = SnippetProvenance(
            file_path="a.py",
            start_line=1,
            end_line=3,
            content_hash="abc",
            source_type="file",
        )
        provenance2 = SnippetProvenance.from_dict(provenance.to_dict())
        assert provenance2 == provenance


class TestRLMChatCompletion:
    """Tests for RLMChatCompletion metadata field."""

    def _make_usage(self) -> UsageSummary:
        return UsageSummary(model_usage_summaries={})

    def test_metadata_default_none(self):
        c = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=self._make_usage(),
            execution_time=1.0,
        )
        assert c.metadata is None

    def test_to_dict_without_metadata(self):
        c = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=self._make_usage(),
            execution_time=1.0,
        )
        d = c.to_dict()
        assert "metadata" not in d

    def test_to_dict_with_metadata(self):
        meta: dict[str, Any] = {"run_metadata": {}, "iterations": [{"i": 1}]}
        c = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=self._make_usage(),
            execution_time=1.0,
            metadata=meta,
        )
        d = c.to_dict()
        assert d["metadata"] == meta

    def test_roundtrip_with_metadata(self):
        meta: dict[str, Any] = {"run_metadata": {"model": "x"}, "iterations": [{"i": 1}]}
        c = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=self._make_usage(),
            execution_time=1.0,
            metadata=meta,
        )
        c2 = RLMChatCompletion.from_dict(c.to_dict())
        assert c2.metadata == meta

    def test_roundtrip_without_metadata(self):
        c = RLMChatCompletion(
            root_model="m",
            prompt="p",
            response="r",
            usage_summary=self._make_usage(),
            execution_time=1.0,
        )
        c2 = RLMChatCompletion.from_dict(c.to_dict())
        assert c2.metadata is None

    def test_from_dict_missing_required_key_raises(self):
        with pytest.raises(KeyError, match="Missing required keys"):
            RLMChatCompletion.from_dict(
                {
                    "root_model": "m",
                    "prompt": "p",
                    "response": "r",
                    "execution_time": 1.0,
                }
            )
