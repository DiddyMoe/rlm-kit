# Developing LM Clients

LM client implementations live in `rlm/clients/`. All clients inherit from `BaseLM`.

## Base Class

```python
# rlm/clients/base_lm.py
class BaseLM(ABC):
    def __init__(self, model_name: str, timeout: float | None = None, **kwargs: Any): ...

    @abstractmethod
    def completion(self, prompt: str | list[dict[str, Any]]) -> str: ...

    @abstractmethod
    async def acompletion(self, prompt: str | list[dict[str, Any]]) -> str: ...

    @abstractmethod
    def get_usage_summary(self) -> UsageSummary: ...

    @abstractmethod
    def get_last_usage(self) -> ModelUsageSummary: ...

    def stream_completion(self, prompt, on_chunk, model=None) -> str: ...  # default: falls back to completion()
    def get_total_tokens(self) -> int: ...  # sums across all models
```

## Requirements

1. Inherit from `BaseLM` in `rlm/clients/base_lm.py`
2. Implement all abstract methods: `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`
3. Handle both `str` and `list[dict[str, Any]]` prompt formats (individual clients may add a `model` parameter, but it is NOT part of the abstract interface)
4. Track per-model usage with `defaultdict(int)` for token counts
5. Register client in `rlm/clients/__init__.py`

## Registration

Add to `_CLIENT_SPECS` in `rlm/clients/__init__.py`:

```python
_CLIENT_SPECS: dict[ClientBackend, tuple[str, str]] = {
    "openai": ("rlm.clients.openai", "OpenAIClient"),
    "anthropic": ("rlm.clients.anthropic", "AnthropicClient"),
    # Add your client:
    "my_provider": ("rlm.clients.my_provider", "MyProviderClient"),
}
```

Also update `ClientBackend` type alias in `rlm/core/types.py`.

## Implementation Pattern

```python
from collections import defaultdict
from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

class MyProviderClient(BaseLM):
    def __init__(self, api_key: str, model_name: str, **kwargs: Any):
        super().__init__(model_name=model_name, **kwargs)
        self._client = MyProviderSDK(api_key=api_key)
        self._usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        target_model = model or self.model_name
        # Handle both str and message list formats
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        response = self._client.chat(model=target_model, messages=messages)

        # Track usage
        self._usage[target_model]["calls"] += 1
        self._usage[target_model]["input_tokens"] += response.usage.input_tokens
        self._usage[target_model]["output_tokens"] += response.usage.output_tokens

        return response.content

    async def acompletion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        # Async variant — same logic with async client
        ...

    def get_usage_summary(self) -> UsageSummary:
        summaries = {}
        for model, usage in self._usage.items():
            summaries[model] = ModelUsageSummary(
                total_calls=usage["calls"],
                total_input_tokens=usage["input_tokens"],
                total_output_tokens=usage["output_tokens"],
            )
        return UsageSummary(model_usage_summaries=summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        # Return usage from most recent call
        ...
```

## Configuration

- **Environment variables**: ONLY for API keys (e.g., `OPENAI_API_KEY`)
- **Hardcode**: Default base URLs and reasonable defaults
- **Arguments**: Essential customization via `__init__()`
- Never hardcode secrets

## Optional Overrides

### `stream_completion()`

Default implementation falls back to `completion()`. Override for native streaming:

```python
def stream_completion(
    self,
    prompt: str | list[dict[str, Any]],
    on_chunk: Callable[[str], None],
    model: str | None = None,
) -> str:
    # Stream response chunks via on_chunk callback
    # Return full response string
    ...
```

### `timeout` Parameter

`BaseLM.__init__` accepts an optional `timeout: float | None` parameter. Pass through to your SDK:

```python
class MyClient(BaseLM):
    def __init__(self, api_key: str, model_name: str, timeout: float | None = None, **kwargs):
        super().__init__(model_name=model_name, timeout=timeout, **kwargs)
        self._client = MyProviderSDK(api_key=api_key, timeout=timeout)
```

### `get_total_tokens()`

Returns sum of all tokens across all models. Default implementation sums from `get_usage_summary()`. Override only if you track totals differently.
