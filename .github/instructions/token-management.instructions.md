```instructions
# Token Management

Token counting and model context limits, used by compaction and context sizing. Located in `rlm/utils/`.

## Two Token Counting Modules

| Module | File | Purpose |
|--------|------|---------|
| `token_utils` | `rlm/utils/token_utils.py` | Accurate counting (tiktoken), model context limits, used by compaction |
| `token_counter` | `rlm/utils/token_counter.py` | Heuristic estimates (~4 chars/token), display formatting |

### When to Use Which

- **Compaction / context sizing** → `token_utils.count_tokens()` (accurate, tiktoken-backed)
- **Quick estimates / display** → `token_counter.estimate_tokens()` (heuristic, no dependencies)

## token_utils — Accurate Counting

### count_tokens()

Primary token counting function. Uses **tiktoken** when available, falls back to character estimate.

```python
from rlm.utils.token_utils import count_tokens

messages = [{"role": "user", "content": "Hello world"}]
n = count_tokens(messages, model_name="gpt-4o")  # Accurate with tiktoken
n = count_tokens(messages, model_name="unknown")  # Falls back to char estimate
```

**tiktoken integration**:
- Lazy-imported via `importlib.import_module("tiktoken")`
- Tries `encoding_for_model(model_name)` first, falls back to `cl100k_base`
- Handles multimodal content lists (extracts `type: "text"` parts)
- Adds ~3 tokens per message + 1 token per name field (OpenAI format overhead)

### Model Context Limits

```python
from rlm.utils.token_utils import get_context_limit, MODEL_CONTEXT_LIMITS

limit = get_context_limit("gpt-4o")           # → 128_000
limit = get_context_limit("claude-3-5-sonnet") # → 200_000
limit = get_context_limit("gemini-2.5-pro")    # → 1_000_000
limit = get_context_limit("unknown-model")     # → 128_000 (DEFAULT_CONTEXT_LIMIT)
```

**Matching algorithm**: Substring match — the dict key must be contained in the model name. Longest matching key wins. This allows prefixed model names like `@openai/gpt-4o` to match `gpt-4o`.

### Supported Models

| Provider | Models | Context |
|----------|--------|---------|
| OpenAI | GPT-5, GPT-5-nano | 272K |
| OpenAI | GPT-4o, GPT-4o-mini | 128K |
| OpenAI | o1, o1-preview | 128K–200K |
| Anthropic | Claude 3.x family | 200K |
| Google | Gemini 2.x, 1.5 | 1M |
| Alibaba | Qwen3 family | 32K–256K |
| Moonshot | Kimi K2 family | 128K–262K |
| Zhipu | GLM-4 family | 128K–1M |

### Constants

```python
DEFAULT_CONTEXT_LIMIT = 128_000    # Fallback for unknown models
CHARS_PER_TOKEN_ESTIMATE = 4       # Conservative chars-per-token ratio
```

## token_counter — Heuristic Estimates

Simple heuristic estimators for quick token counting without external dependencies.

```python
from rlm.utils.token_counter import (
    estimate_tokens,
    estimate_message_tokens,
    estimate_prompt_tokens,
    format_token_summary,
)

estimate_tokens("Hello world")                              # → 2 (~4 chars/token)
estimate_message_tokens({"role": "user", "content": "Hi"})  # → 2 (content + role overhead)
estimate_prompt_tokens("What is 2+2?")                      # → 3
estimate_prompt_tokens([{"role": "user", "content": "Hi"}]) # → 2

format_token_summary(1000, input_tokens=600, output_tokens=400)
# → "Total: 1,000 tokens | Input: 600 | Output: 400"
```

## Core Constant

```python
# rlm/core/constants.py
MAX_SUB_CALL_PROMPT_CHARS = 100_000  # ~25k tokens
```

Bounds sub-LM call prompts to prevent `ContextWindowExceededError`. Applied to `llm_query()`, recursive subcalls, and gateway tools.

## Adding New Models

To add context limits for new models, update `MODEL_CONTEXT_LIMITS` in `rlm/utils/token_utils.py`:

```python
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # Existing entries...
    "my-new-model": 128_000,
}
```

Use the most specific key possible. Longer keys win in substring matching.

```
```
