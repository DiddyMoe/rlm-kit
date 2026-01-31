# API: RLM class

The `RLM` class is the main entry point for Recursive Language Model completions. It wraps an LM client and execution environment for iterative, code-augmented reasoning.

```python
from rlm import RLM

rlm = RLM(
    backend="openai",
    backend_kwargs={"model_name": "gpt-5"},
)
```

---

## Constructor

```python
RLM(
    backend: str = "openai",
    backend_kwargs: dict | None = None,
    environment: str = "local",
    environment_kwargs: dict | None = None,
    depth: int = 0,
    max_depth: int = 1,
    max_iterations: int = 30,
    custom_system_prompt: str | None = None,
    other_backends: list[str] | None = None,
    other_backend_kwargs: list[dict] | None = None,
    logger: RLMLogger | None = None,
    verbose: bool = False,
)
```

### Parameters

**`backend`** — `Literal["openai", "portkey", "openrouter", "vllm", "litellm", "anthropic"]`, default `"openai"`. LM provider for the root model.

**`backend_kwargs`** — `dict[str, Any] | None`. Passed to the LM client. Varies by backend:

| Backend | Required | Optional |
|---------|----------|----------|
| openai | model_name | api_key, base_url |
| anthropic | model_name | api_key |
| portkey | model_name, api_key | base_url |
| openrouter | model_name | api_key |
| vllm | model_name, base_url | — |
| litellm | model_name | varies |

**`environment`** — `Literal["local", "modal", "docker"]`, default `"local"`. Execution environment for generated code: same-process (local), Docker, or Modal.

**`environment_kwargs`** — Environment-specific config (e.g. `setup_code` for local, `image` for Docker, `app_name`/`timeout` for Modal).

**`max_depth`** — `int`, default `1`. Max recursion depth; only depth 1 is fully supported. When `depth >= max_depth`, RLM falls back to a regular LM completion.

**`max_iterations`** — `int`, default `30`. Max REPL iterations before forcing a final answer.

**`custom_system_prompt`** — Override the default RLM system prompt (context, `llm_query`, `FINAL()`).

**`other_backends` / `other_backend_kwargs`** — Additional backends for sub-calls via `llm_query(prompt, model=...)`.

**`logger`** — `RLMLogger | None`. Saves iteration trajectories to disk.

**`verbose`** — `bool`. Rich console output (metadata, iterations, code results, final answer).

---

## Methods

### `completion()`

```python
def completion(
    self,
    prompt: str | dict[str, Any],
    root_prompt: str | None = None,
) -> RLMChatCompletion
```

- **`prompt`:** Input/context; becomes the `context` variable in the REPL. Can be a string, dict, or list.
- **`root_prompt`:** Optional short prompt shown to the root LM (e.g. the question in Q&A).

**Returns:** `RLMChatCompletion` with `root_model`, `prompt`, `response`, `usage_summary`, `execution_time`.

---

## Response types

### `RLMChatCompletion`

- `root_model` — Model name used
- `prompt` — Original input
- `response` — Final answer string
- `execution_time` — Total seconds
- `usage_summary` — `UsageSummary` object

### `UsageSummary`

- `to_dict()` — e.g. `model_usage_summaries` with `total_calls`, `total_input_tokens`, `total_output_tokens` per model

---

## Error handling

RLM fails fast: missing required args (e.g. `base_url` for vLLM) or unknown backend raise immediately. If `max_iterations` is reached without `FINAL()`, the LM is prompted once more to give a final answer from the conversation.

---

## Thread safety

Each `completion()` call starts its own `LMHandler` and environment and cleans up when done. Calls are independent; do not share a single `RLM` instance across threads without synchronization.

---

## Example: full configuration

```python
import os
from rlm import RLM
from rlm.logger import RLMLogger

logger = RLMLogger(log_dir="./logs", file_name="analysis")
rlm = RLM(
    backend="anthropic",
    backend_kwargs={
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "model_name": "claude-sonnet-4-20250514",
    },
    environment="docker",
    environment_kwargs={"image": "python:3.11-slim"},
    other_backends=["openai"],
    other_backend_kwargs=[{
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model_name": "gpt-4o-mini",
    }],
    max_iterations=40,
    max_depth=1,
    logger=logger,
    verbose=True,
)
result = rlm.completion(
    prompt=massive_document,
    root_prompt="Summarize the key findings",
)
```
