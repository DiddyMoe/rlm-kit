```instructions
# RLMConfig Features Reference

Complete reference for `RLMConfig` fields in `rlm/core/rlm.py`. This covers features beyond the basic architecture documented in `project-overview.instructions.md`.

## Configuration Dataclass

Fields are grouped here by topic for readability. The actual declaration order in source differs (e.g., `max_root_tokens`/`max_sub_tokens` appear after callbacks, `custom_system_prompt` appears after `max_errors`).

```python
@dataclass
class RLMConfig:
    # Core
    backend: ClientBackend = "openai"
    backend_kwargs: dict[str, Any] | None = None
    environment: EnvironmentType = "local"
    environment_kwargs: dict[str, Any] | None = None

    # Depth & iteration
    depth: int = 0
    max_depth: int = 1
    max_iterations: int = 30

    # Budgets & limits
    max_budget: float | None = None
    max_timeout: float | None = None
    max_errors: int | None = None
    max_root_tokens: int | None = None
    max_sub_tokens: int | None = None

    # System prompt
    custom_system_prompt: str | None = None

    # Multi-backend
    other_backends: list[ClientBackend] | None = None
    other_backend_kwargs: list[dict[str, Any]] | None = None
    sub_lms: dict[str, BaseLM] | None = None

    # Recursive subcalls
    enable_recursive_subcalls: bool = False
    on_subcall_start: Callable[[dict[str, Any]], None] | None = None
    on_subcall_complete: Callable[[dict[str, Any]], None] | None = None

    # Iteration callbacks
    on_iteration_start: Callable[[dict[str, Any]], None] | None = None
    on_iteration_complete: Callable[[dict[str, Any]], None] | None = None

    # Streaming
    on_root_chunk: Callable[[str], None] | None = None

    # Prefix caching
    enable_prefix_cache: bool = False

    # Logging
    logger: RLMLogger | None = None
    verbose: bool = False

    # Persistence
    persistent: bool = False

    # Compaction
    compaction: bool = False
    compaction_threshold_pct: float = 0.85

    # Custom tools
    custom_tools: dict[str, Any] | None = None
```

## Budget & Limit Enforcement

### Cost Budget (`max_budget`)

Tracks cumulative cost across all LLM calls (including recursive subcalls). Uses an approximate conversion: `$0.01 per 1K tokens`.

```python
config = RLMConfig(max_budget=1.0)  # $1.00 budget cap
```

- Checked before each iteration via `_check_iteration_limits()`
- Raises `BudgetExceededError(cumulative_cost, max_budget)` when exceeded
- Subcalls inherit remaining budget: `remaining_budget = max(max_budget - cumulative_cost, 0.0)`

### Timeout (`max_timeout`)

Wall-clock timeout in seconds for the entire completion call.

```python
config = RLMConfig(max_timeout=120.0)  # 2-minute timeout
```

- Uses `time.perf_counter()` for accurate measurement
- Raises `TimeoutError` when exceeded
- Subcalls inherit remaining time

### Error Limit (`max_errors`)

Counts code blocks with non-empty stderr output.

```python
config = RLMConfig(max_errors=5)  # Stop after 5 execution errors
```

- Raises `RuntimeError` when error count reaches limit
- Subcall error counts are aggregated to parent

### Token Limits (`max_root_tokens`, `max_sub_tokens`)

Per-call token limits enforced at the `LMHandler` level.

```python
config = RLMConfig(
    max_root_tokens=50_000,   # Limit root-level LLM calls
    max_sub_tokens=10_000,    # Limit sub-LLM calls (llm_query)
)
```

### BudgetExceededError

```python
from rlm.core.types import BudgetExceededError

try:
    result = rlm.completion(prompt)
except BudgetExceededError as e:
    print(f"Cost {e.cumulative_cost:.4f} exceeded budget {e.max_budget:.4f}")
```

## Compaction

Automatic history summarization when token usage approaches model context limits. Prevents `ContextWindowExceededError` in long-running tasks.

### How It Works

1. Before each iteration, `_maybe_compact()` checks current token count vs. threshold
2. Threshold = `compaction_threshold_pct × model_context_limit` (default: 85%)
3. When triggered, asks the LLM to summarize progress so far
4. Replaces message history with: `[system, initial_assistant, summary, continue_prompt]`
5. Continue prompt tells the LLM to use `SHOW_VARS()` and check `history` for context

### Configuration

```python
config = RLMConfig(
    compaction=True,                     # Enable compaction
    compaction_threshold_pct=0.85,       # Trigger at 85% of context limit (default)
)
```

### REPL Integration

When compaction is enabled:
- `append_compaction_entry()` is called on the environment after each iteration
- The `history` REPL variable tracks all compaction entries
- `SHOW_VARS()` lists available REPL variables for context recovery
- Compaction count is tracked and displayed in continue prompts

### Compaction Summary Prompt

The LLM is asked to summarize:
1. Completed vs. remaining steps/sub-tasks
2. Concrete intermediate results (numbers, values, variable names)
3. Next planned action

## Recursive Subcalls

Enables RLM instances to spawn child RLM completions at incrementing depth.

### Configuration

```python
config = RLMConfig(
    enable_recursive_subcalls=True,
    max_depth=3,                          # Allow 3 levels of recursion
)
```

### Mechanics

- `_subcall(prompt)` creates a child `RLM` at `depth + 1`
- When `depth >= max_depth`, falls back to a direct LLM call (`_fallback_answer`)
- Child inherits: backend, environment, system prompt, max_iterations, tools, compaction settings
- Child receives: remaining budget, remaining timeout, remaining error count
- Parent accumulates child's cost and error count after completion

### Callbacks

```python
def on_start(info: dict[str, Any]) -> None:
    # info: {"parent_depth": 0, "child_depth": 1, "max_depth": 3}
    ...

def on_complete(info: dict[str, Any]) -> None:
    # info: {"parent_depth": 0, "child_depth": 1, "max_depth": 3,
    #        "status": "success", "response": "...", "execution_time": 1.5}
    # or:   {..., "status": "error", "error": "..."}
    ...

config = RLMConfig(
    enable_recursive_subcalls=True,
    on_subcall_start=on_start,
    on_subcall_complete=on_complete,
)
```

## Custom Tools

Inject callable tools into the REPL namespace. Available to model-generated code during execution.

### Configuration

```python
def my_search(query: str) -> str:
    return f"Results for: {query}"

config = RLMConfig(
    custom_tools={"search": my_search},
)
```

### Behavior

- Tools are injected into environment globals during `_create_environment()`
- Reserved tool names (`context`, `history`, `llm_query`, `llm_query_batched`, `FINAL_VAR`, `SHOW_VARS`) are protected via `_scaffold_backup` — they are restored after each code execution, so user code cannot permanently shadow them
- Tools survive environment variable overwrites via the same `_scaffold_backup` mechanism
- Custom tool names are mentioned in the system prompt so the LLM knows they're available

## Iteration Callbacks

```python
def on_iter_start(info: dict[str, Any]) -> None:
    # info: {"depth": 0, "iteration": 1, "max_iterations": 30}
    ...

def on_iter_complete(info: dict[str, Any]) -> None:
    # info: {"depth": 0, "iteration": 1, "response": "...",
    #        "code_block_count": 2, "iteration_time": 3.5}
    ...

config = RLMConfig(
    on_iteration_start=on_iter_start,
    on_iteration_complete=on_iter_complete,
)
```

## Streaming

Stream root-level LLM response chunks in real-time:

```python
def on_chunk(text: str) -> None:
    print(text, end="", flush=True)

config = RLMConfig(on_root_chunk=on_chunk)
```

Only fires at `depth == 0`. Uses `lm_handler.completion(prompt, on_chunk=callback)`.

## Prefix Caching

Caches message history prefixes to avoid re-encoding on each iteration:

```python
config = RLMConfig(enable_prefix_cache=True)
```

- Cache is bounded to 128 entries (FIFO eviction)
- Key: `f"{len(message_history)}:{hash(str(message_history[-1])) if message_history else 0}"`
- Reduces redundant prompt construction overhead

## Sub-LM Registry

Register named LM clients for use in `llm_query(prompt, model="alias")`:

```python
from rlm.clients.openai import OpenAIClient

fast_model = OpenAIClient(model_name="gpt-4o-mini", api_key="...")

config = RLMConfig(
    sub_lms={"fast": fast_model},           # Available as llm_query(prompt, model="fast")
    other_backends=["anthropic"],            # Also available
    other_backend_kwargs=[{"model_name": "claude-3-haiku", "api_key": "..."}],
)
```

## Persistence

Multi-turn conversation mode. Environment is reused across `completion()` calls:

```python
config = RLMConfig(persistent=True, environment="local")

with RLM(config) as rlm:
    result1 = rlm.completion("Load this CSV data")
    result2 = rlm.completion("Now analyze column A")     # REPL state preserved
```

- Only `local` environment supports persistence currently
- Environment must implement `SupportsPersistence` protocol
- `close()` or `__exit__` cleans up the persistent environment

## Batched Concurrency

`llm_query_batched()` calls inside REPL code use a semaphore to limit concurrent LLM requests:

```python
# rlm/core/lm_handler.py
_MAX_CONCURRENT_BATCH = 16  # Max concurrent requests in a batch
```

This prevents overwhelming the LLM provider API with too many simultaneous requests.

```
```
