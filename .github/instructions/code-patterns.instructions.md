# Key Code Patterns

Quick reference for the recurring patterns used in this codebase. Follow these when writing new code.

## Dataclass + Manual Serialization

All data-carrying types use `@dataclass` with explicit `to_dict()`/`from_dict()`. No Pydantic.

```python
@dataclass
class MyType:
    name: str
    count: int
    items: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name, "count": self.count}
        if self.items is not None:
            result["items"] = self.items
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MyType":
        return cls(
            name=str(data["name"]),
            count=int(data["count"]),
            items=cast(list[str] | None, data.get("items")),
        )
```

## Factory Functions with Lazy Imports

Clients and environments use factory functions that lazily import implementations:

```python
_CLIENT_SPECS: dict[ClientBackend, tuple[str, str]] = {
    "openai": ("rlm.clients.openai", "OpenAIClient"),
    ...
}

def get_client(backend: ClientBackend, backend_kwargs: dict[str, Any]) -> BaseLM:
    if backend not in _CLIENT_SPECS:
        raise ValueError(f"Unknown backend: {backend}")
    module_path, class_name = _CLIENT_SPECS[backend]
    cls = _load_client_class(module_path, class_name)
    return cls(**backend_kwargs)
```

## Context Manager Protocol

Resources that need cleanup implement `__enter__`/`__exit__`:

```python
class RLM:
    def __enter__(self) -> "RLM": return self
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: self.close()
    def close(self) -> None: ...
```

`_spawn_completion_context` uses `@contextmanager` for per-call resource lifecycle.

## Socket IPC Protocol

4-byte big-endian length prefix + UTF-8 JSON:

```python
def socket_send(sock: socket.socket, data: dict) -> None:
    payload = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)

def socket_recv(sock: socket.socket) -> dict:
    raw_len = sock.recv(4)
    length = struct.unpack(">I", raw_len)[0]
    chunks = []
    while length > 0:
        chunk = sock.recv(min(length, 4096))
        chunks.append(chunk)
        length -= len(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))
```

## TYPE_CHECKING Guard

Used to avoid circular imports while keeping type annotations:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rlm.environments.base_env import BaseEnv

def find_final_answer(text: str, environment: "BaseEnv | None" = None) -> str | None:
    ...
```

## Retry with Backoff

Transient failures use exponential backoff:

```python
from rlm.core.retry import retry_with_backoff

result = retry_with_backoff(
    lambda: socket_request(address, request),
    max_attempts=3,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)
```

## Usage Tracking with defaultdict

All LM clients track per-model usage:

```python
from collections import defaultdict

self._usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
self._usage[model]["calls"] += 1
self._usage[model]["input_tokens"] += response.usage.input_tokens
```

## VerbosePrinter No-Op Pattern

Methods are no-ops when disabled — no conditional checks at call sites:

```python
class VerbosePrinter:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
    def print_iteration(self, ...):
        if not self.enabled: return
        # ... actual printing
```

## Thread-Safe IO

Backend sidecar uses lock for stdout:

```python
_stdout_lock = threading.Lock()

def send_msg(msg: dict) -> None:
    with _stdout_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
```

## Orphan Process Protection

Python sidecar monitors parent PID:

```python
_PARENT_PID = os.getppid()

def _watchdog():
    while True:
        time.sleep(2)
        if os.getppid() != _PARENT_PID:
            os._exit(0)

threading.Thread(target=_watchdog, daemon=True).start()
```

## Singleton Pattern (TypeScript)

ConfigService and logger use singletons:

```typescript
class ConfigService implements vscode.Disposable {
    private static _instance: ConfigService | undefined;
    static get instance(): ConfigService {
        if (!this._instance) this._instance = new ConfigService();
        return this._instance;
    }
}
```

## Generation Counter (Stale Event Prevention)

BackendBridge uses monotonic counter to ignore events from old processes:

```typescript
private generation = 0;
// On new process spawn:
this.generation++;
const gen = this.generation;
// In event handlers:
if (gen !== this.generation) return; // stale event
```

## Safe Builtins (Two Tiers)

```python
# Strict (MCP exec): blocks __import__, open, globals, locals
builtins = get_safe_builtins()

# Relaxed (REPL): allows __import__, open, globals, locals; blocks eval/exec/compile/input
builtins = get_safe_builtins_for_repl()
# Note: LocalREPL further overrides globals/locals to None
```

Both set dangerous builtins to `None` rather than removing them.

## Compaction Entry Pattern

When compaction is enabled, iteration messages are tracked for context recovery:

```python
if self.compaction and hasattr(environment, "append_compaction_entry"):
    environment.append_compaction_entry(new_messages)
```

The REPL `history` variable stores compaction entries. `SHOW_VARS()` lists available variables after compaction.

## Custom Tool Scaffold Backup

Custom tools injected via `custom_tools` survive environment variable overwrites via an internal `_scaffold_backup` mechanism. This ensures tools remain callable even if user code accidentally reassigns the tool name.

## Prefix Caching Pattern

Message history prefixes are cached to avoid redundant encoding:

```python
self._prefix_prompt_cache: dict[str, list[dict[str, Any]]] = {}
# Key: f"{len(message_history)}:{hash(str(message_history[-1])) if message_history else 0}"
# Max 128 entries, FIFO eviction (deletes oldest key when full)
```

## Nonce-Based Request Tracking (TypeScript)

BackendBridge uses nonces to match requests with responses:

```typescript
interface PendingRequest<T> {
    resolve: (value: T) => void;
    reject: (reason: Error) => void;
}
// Map<nonce, PendingRequest>
```
