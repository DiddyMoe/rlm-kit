# Developing Environments

Environment implementations live in `rlm/environments/`. Choose the appropriate base class.

## Base Classes

```
BaseEnv (ABC)
├── IsolatedEnv (ABC)     — Remote sandboxes (Modal, Prime, Daytona, E2B)
└── NonIsolatedEnv (ABC)  — Local execution (LocalREPL, Docker)
```

All share the same abstract methods: `setup()`, `load_context()`, `execute_code() -> REPLResult`

## Interface Summary

```python
class BaseEnv(ABC):
    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def load_context(self, context_payload: dict | list | str) -> None: ...

    @abstractmethod
    def execute_code(self, code: str) -> REPLResult: ...

    def cleanup(self) -> None: ...
```

## Implementation for Non-Isolated (Local)

```python
from rlm.environments.base_env import NonIsolatedEnv
from rlm.core.types import REPLResult

class MyEnvironment(NonIsolatedEnv):
    def __init__(
        self,
        lm_handler_address: tuple[str, int] | None = None,
        context_payload: dict[str, Any] | list[Any] | str | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.lm_handler_address = lm_handler_address
        self.setup()
        if context_payload:
            self.load_context(context_payload)

    def setup(self) -> None:
        # Initialize execution namespace with safe builtins
        # Inject: llm_query, llm_query_batched, FINAL, FINAL_VAR, SHOW_VARS
        ...

    def load_context(self, context_payload: dict | list | str) -> None:
        # Make context available as `context` variable in namespace
        ...

    def execute_code(self, code: str) -> REPLResult:
        # Execute code, capture stdout/stderr, return REPLResult
        ...

    def cleanup(self) -> None:
        # Clean up temp directories, threads, etc.
        ...
```

## Globals Required in Execution Namespace

Every environment must provide these globals to executed code:

| Global | Purpose |
|--------|---------|
| `context` | The loaded context payload |
| `llm_query(prompt, model=None)` | For sub-LM calls |
| `llm_query_batched(prompts, model=None)` | For batched sub-LM calls |
| `FINAL(answer)` | Return final answer as string |
| `FINAL_VAR(variable_name)` | Return final answer from variable |
| `SHOW_VARS()` | Display available variables |

Reserved tool names (cannot be overridden by custom tools):
```python
RESERVED_TOOL_NAMES = frozenset({"context", "history", "llm_query", "llm_query_batched", "FINAL_VAR", "SHOW_VARS"})
```

## Communication Patterns

### Non-Isolated (Socket Protocol)

Direct TCP connection to `LMHandler`:
- 4-byte big-endian length prefix + UTF-8 JSON payload
- `llm_query()` → `send_lm_request(address, LMRequest)` → `LMResponse`
- Uses `retry_with_backoff` for transient socket failures

### Isolated (HTTP Broker)

Cloud sandboxes cannot connect directly to host. Use HTTP broker:
1. Broker server runs inside sandbox (Flask with `/enqueue`, `/pending`, `/respond`)
2. Broker exposed via encrypted tunnel (e.g., Modal's `encrypted_ports`)
3. Host polls `{tunnel_url}/pending` for new requests
4. Host forwards to `LMHandler`, posts response to `{tunnel_url}/respond`
5. State persistence via `dill` serialization

See `rlm/environments/modal_repl.py` as canonical reference.

## Registration

Add to `get_environment()` in `rlm/environments/__init__.py` and update `EnvironmentType` in `rlm/core/types.py`.

## Persistence Protocol

If your environment supports multi-turn persistence, implement `SupportsPersistence`:

```python
@runtime_checkable
class SupportsPersistence(Protocol):
    def update_handler_address(self, address: tuple[str, int]) -> None: ...
    def add_context(self, context_payload: dict | list | str, context_index: int | None = None) -> int: ...
    def get_context_count(self) -> int: ...
    def add_history(self, message_history: list[dict[str, Any]], history_index: int | None = None) -> int: ...
    def get_history_count(self) -> int: ...
    def append_compaction_entry(self, entry: list[dict[str, Any]] | dict[str, Any]) -> None: ...
    def cleanup(self) -> None: ...
```

This is a `runtime_checkable Protocol` (duck typing, not inheritance).

## Safety

- Use `get_safe_builtins_for_repl()` for REPL environments (allows `__import__`, `open`, `globals`, `locals`; note: `LocalREPL` further blocks `globals`/`locals`)
- Use `get_safe_builtins()` for MCP exec (stricter — blocks `__import__`, `open`, `globals`, `locals`)
- Both block: `eval`, `exec`, `compile`, `input`
- Both set dangerous builtins to `None` (not removed)

## Custom Tools

Environments receive `custom_tools` via `_create_environment()` kwargs. These are injected into the REPL namespace alongside standard globals. Reserved tool names (`RESERVED_TOOL_NAMES`) cannot be overridden.

## Default Packages for Isolated Environments

Defined in `rlm/environments/constants.py`:

**APT packages**: `build-essential`, `git`, `curl`, `wget`, `libopenblas-dev`, `liblapack-dev`

**pip packages**: `numpy`, `pandas`, `scipy`, `sympy`, `requests`, `httpx`, `flask`, `pyyaml`, `toml`, `tqdm`, `python-dateutil`, `regex`, `dill`

## Exec Script Templates

Isolated environments use script templates from `rlm/environments/exec_script_templates.py`:

| Template | Environment | Key Differences |
|----------|-------------|-----------------|
| `MODAL_EXEC_SCRIPT_TEMPLATE` | Modal | Broker at `localhost:__BROKER_PORT__` |
| `DOCKER_EXEC_SCRIPT_TEMPLATE` | Docker | Proxy at `host.docker.internal:__PROXY_PORT__` |

Templates provide:
- State persistence via `dill` serialization to `/tmp/rlm_state.dill`
- `llm_query()` / `llm_query_batched()` via HTTP broker
- `FINAL_VAR()` and `SHOW_VARS()` helper functions
- Base64-encoded code execution with stdout/stderr capture

Use `render_exec_script(template, replacements)` to fill in template placeholders.

## Available Environment Types

| Type | Class | Isolation | Status |
|------|-------|-----------|--------|
| `local` | `LocalREPL` | Non-isolated | Full support + persistence |
| `docker` | `DockerREPL` | Container | Full support |
| `modal` | `ModalREPL` | Cloud sandbox | Full support |
| `prime` | `PrimeREPL` | Cloud sandbox | Full support |
| `daytona` | `DaytonaREPL` | Cloud sandbox | Available |
| `e2b` | `E2BREPL` | Cloud sandbox | Available |
