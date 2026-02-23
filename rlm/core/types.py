from dataclasses import dataclass
from types import ModuleType
from typing import Any, Literal, cast

ClientBackend = Literal[
    "openai",
    "portkey",
    "openrouter",
    "vercel",
    "vllm",
    "litellm",
    "anthropic",
    "azure_openai",
    "gemini",
    "ollama",
    "vscode_lm",
]
EnvironmentType = Literal["local", "docker", "modal", "prime", "daytona", "e2b"]


def _serialize_sequence(value: Any) -> list[Any]:
    sequence = cast(list[Any] | tuple[Any, ...], value)
    return [_serialize_value(item) for item in sequence]


def _serialize_mapping(value: Any) -> dict[str, Any]:
    mapping = cast(dict[Any, Any], value)
    return {str(key): _serialize_value(item) for key, item in mapping.items()}


def _serialize_callable(value: Any) -> str:
    return f"<{type(value).__name__} '{getattr(value, '__name__', repr(value))}'>"


def _serialize_value(value: Any) -> Any:
    """Convert a value to a JSON-serializable representation."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, ModuleType):
        return f"<module '{value.__name__}'>"

    serializers: list[tuple[type[Any] | tuple[type[Any], ...], Any]] = [
        ((list, tuple), _serialize_sequence),
        (dict, _serialize_mapping),
    ]
    for expected_type, serializer in serializers:
        if isinstance(value, expected_type):
            return serializer(value)

    if callable(value):
        return _serialize_callable(value)

    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__}>"


########################################################
########    Types for LM Cost Tracking         #########
########################################################


@dataclass
class ModelUsageSummary:
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelUsageSummary":
        return cls(
            total_calls=int(data.get("total_calls", 0)),
            total_input_tokens=int(data.get("total_input_tokens", 0)),
            total_output_tokens=int(data.get("total_output_tokens", 0)),
        )


@dataclass
class UsageSummary:
    model_usage_summaries: dict[str, ModelUsageSummary]

    def to_dict(self) -> dict[str, dict[str, dict[str, int]]]:
        return {
            "model_usage_summaries": {
                model: usage_summary.to_dict()
                for model, usage_summary in self.model_usage_summaries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageSummary":
        raw_summaries_value = data.get("model_usage_summaries")
        raw_summaries: dict[str, dict[str, Any]] = {}
        if isinstance(raw_summaries_value, dict):
            typed_raw_summaries = cast(dict[Any, Any], raw_summaries_value)
            for model_name, usage_payload in typed_raw_summaries.items():
                if isinstance(model_name, str) and isinstance(usage_payload, dict):
                    raw_summaries[model_name] = cast(dict[str, Any], usage_payload)

        parsed_summaries: dict[str, ModelUsageSummary] = {}
        for model_name, usage_payload in raw_summaries.items():
            parsed_summaries[model_name] = ModelUsageSummary.from_dict(usage_payload)

        return cls(
            model_usage_summaries=parsed_summaries,
        )


########################################################
########   Provenance (MCP gateway)              #########
########################################################


@dataclass
class SnippetProvenance:
    """Provenance for a code snippet or file span (MCP gateway)."""

    file_path: str | None
    start_line: int | None
    end_line: int | None
    content_hash: str | None
    source_type: str  # e.g. "file", "chunk", "execution"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
            "source_type": self.source_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SnippetProvenance":
        return cls(
            file_path=data.get("file_path"),
            start_line=data.get("start_line"),
            end_line=data.get("end_line"),
            content_hash=data.get("content_hash"),
            source_type=data.get("source_type", "unknown"),
        )


########################################################
########   Types for REPL and RLM Iterations   #########
########################################################
@dataclass
class RLMChatCompletion:
    """Record of a single LLM call made from within the environment."""

    root_model: str
    prompt: str | dict[str, Any] | list[dict[str, Any]]
    response: str
    usage_summary: UsageSummary
    execution_time: float
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "root_model": self.root_model,
            "prompt": self.prompt,
            "response": self.response,
            "usage_summary": self.usage_summary.to_dict(),
            "execution_time": self.execution_time,
        }
        if self.metadata is not None:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RLMChatCompletion":
        required_keys = [
            "root_model",
            "prompt",
            "response",
            "usage_summary",
            "execution_time",
        ]
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise KeyError(f"Missing required keys for RLMChatCompletion: {missing_keys}")

        return cls(
            root_model=data["root_model"],
            prompt=data["prompt"],
            response=data["response"],
            usage_summary=UsageSummary.from_dict(data["usage_summary"]),
            execution_time=data["execution_time"],
            metadata=data.get("metadata"),
        )


@dataclass
class REPLResult:
    """Result of a REPL code execution. Attribute is rlm_calls (sub-call completions)."""

    stdout: str
    stderr: str
    locals: dict[str, Any]
    execution_time: float | None
    rlm_calls: list["RLMChatCompletion"]

    def __init__(
        self,
        stdout: str,
        stderr: str,
        locals: dict[str, Any],
        execution_time: float | None = None,
        rlm_calls: list["RLMChatCompletion"] | None = None,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.locals = locals
        self.execution_time = execution_time
        self.rlm_calls = rlm_calls or []

    def __str__(self) -> str:
        return f"REPLResult(stdout={self.stdout}, stderr={self.stderr}, locals={self.locals}, execution_time={self.execution_time}, rlm_calls={len(self.rlm_calls)})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "locals": {k: _serialize_value(v) for k, v in self.locals.items()},
            "execution_time": self.execution_time,
            "rlm_calls": [call.to_dict() for call in self.rlm_calls],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "REPLResult":
        return cls(
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            locals=data.get("locals", {}),
            execution_time=data.get("execution_time"),
            rlm_calls=[
                RLMChatCompletion.from_dict(call_data) for call_data in data.get("rlm_calls", [])
            ],
        )


@dataclass
class CodeBlock:
    code: str
    result: REPLResult

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "result": self.result.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeBlock":
        return cls(
            code=data.get("code", ""),
            result=REPLResult.from_dict(data.get("result", {})),
        )


@dataclass
class RLMIteration:
    prompt: str | dict[str, Any] | list[dict[str, Any]]
    response: str
    code_blocks: list[CodeBlock]
    final_answer: str | None = None
    iteration_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "response": self.response,
            "code_blocks": [code_block.to_dict() for code_block in self.code_blocks],
            "final_answer": self.final_answer,
            "iteration_time": self.iteration_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RLMIteration":
        return cls(
            prompt=data.get("prompt", ""),
            response=data.get("response", ""),
            code_blocks=[
                CodeBlock.from_dict(block_data) for block_data in data.get("code_blocks", [])
            ],
            final_answer=data.get("final_answer"),
            iteration_time=data.get("iteration_time"),
        )


########################################################
########   Types for RLM Metadata   #########
########################################################


@dataclass
class RLMMetadata:
    """Metadata about the RLM configuration."""

    root_model: str
    max_depth: int
    max_iterations: int
    backend: str
    backend_kwargs: dict[str, Any]
    environment_type: str
    environment_kwargs: dict[str, Any]
    max_root_tokens: int | None = None
    max_sub_tokens: int | None = None
    on_root_chunk: bool = False
    enable_prefix_cache: bool = False
    other_backends: list[str] | None = None
    run_id: str | None = None  # Optional; set by RLMLogger when logging for trajectory correlation

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_model": self.root_model,
            "max_depth": self.max_depth,
            "max_iterations": self.max_iterations,
            "backend": self.backend,
            "backend_kwargs": {k: _serialize_value(v) for k, v in self.backend_kwargs.items()},
            "environment_type": self.environment_type,
            "environment_kwargs": {
                k: _serialize_value(v) for k, v in self.environment_kwargs.items()
            },
            "max_root_tokens": self.max_root_tokens,
            "max_sub_tokens": self.max_sub_tokens,
            "on_root_chunk": self.on_root_chunk,
            "enable_prefix_cache": self.enable_prefix_cache,
            "other_backends": self.other_backends,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RLMMetadata":
        return cls(
            root_model=data.get("root_model", ""),
            max_depth=data.get("max_depth", 0),
            max_iterations=data.get("max_iterations", 0),
            backend=data.get("backend", ""),
            backend_kwargs=data.get("backend_kwargs", {}),
            environment_type=data.get("environment_type", ""),
            environment_kwargs=data.get("environment_kwargs", {}),
            max_root_tokens=data.get("max_root_tokens"),
            max_sub_tokens=data.get("max_sub_tokens"),
            on_root_chunk=data.get("on_root_chunk", False),
            enable_prefix_cache=data.get("enable_prefix_cache", False),
            other_backends=data.get("other_backends"),
            run_id=data.get("run_id"),
        )


########################################################
########   Types for RLM Prompting   #########
########################################################


@dataclass
class QueryMetadata:
    context_lengths: list[int]
    context_total_length: int
    context_type: str

    @staticmethod
    def _compute_length(item: Any) -> int:
        if isinstance(item, str):
            return len(item)

        try:
            import json

            return len(json.dumps(item, default=str))
        except Exception:
            return len(repr(item))

    @classmethod
    def _compute_list_lengths(cls, prompt: list[Any]) -> list[int]:
        if len(prompt) == 0:
            return [0]

        first_item = prompt[0]
        if isinstance(first_item, dict) and "content" in first_item:
            return [len(str(chunk.get("content", ""))) for chunk in prompt]

        return [cls._compute_length(chunk) for chunk in prompt]

    def __init__(self, prompt: str | list[str] | dict[Any, Any] | list[dict[Any, Any]]):
        if isinstance(prompt, str):
            self.context_lengths = [len(prompt)]
            self.context_type = "str"
        elif isinstance(prompt, dict):
            self.context_lengths = [self._compute_length(chunk) for chunk in prompt.values()]
            self.context_type = "dict"
        else:
            self.context_type = "list"
            self.context_lengths = self._compute_list_lengths(prompt)

        self.context_total_length = sum(self.context_lengths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_lengths": self.context_lengths,
            "context_total_length": self.context_total_length,
            "context_type": self.context_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryMetadata":
        query_metadata = cls.__new__(cls)
        query_metadata.context_lengths = list(data.get("context_lengths", []))
        query_metadata.context_total_length = data.get(
            "context_total_length", sum(query_metadata.context_lengths)
        )
        query_metadata.context_type = data.get("context_type", "unknown")
        return query_metadata
