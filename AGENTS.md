# AGENTS.md
This guide covers best practices for contributing to the core Recursive Language Models `rlm` library and developing new environments (in `rlm/environments/`) and LM clients (in `rlm/clients/`).

## Architecture Overview

```
RLM.completion(prompt)
  ├── get_client() → BaseLM              # rlm/clients/__init__.py factory
  ├── LMHandler(client)                   # TCP socket server wrapping BaseLM
  ├── get_environment() → BaseEnv         # rlm/environments/__init__.py factory
  ├── Iteration loop (max 30):
  │     ├── lm_handler.completion()        # LLM call
  │     ├── find_code_blocks(response)     # extract ```repl blocks
  │     ├── env.execute_code(code)         # run in REPL
  │     │     └── llm_query() → socket → LMHandler   # sub-LM calls
  │     └── find_final_answer()            # check FINAL()/FINAL_VAR()
  └── Return RLMChatCompletion
```

| Layer | Location | Purpose |
|-------|----------|--------|
| Core | `rlm/core/` | RLM loop (`rlm.py`), LM handler, types, comms |
| Clients | `rlm/clients/` | LM API integrations (OpenAI, Anthropic, Gemini, etc.) |
| Environments | `rlm/environments/` | REPL execution: Local, Docker, Modal, Prime, Daytona |
| MCP Gateway | `rlm/mcp_gateway/` | MCP server for IDE integration (Cursor) |
| Extension | `vscode-extension/` | VS Code Chat Participant + Python backend bridge |
| Sandbox | `rlm/core/sandbox/` | AST validation, builtins restriction, runtime blocking |

**Key types** (`rlm/core/types.py`): `REPLResult`, `RLMChatCompletion`, `RLMIteration`, `CodeBlock`, `UsageSummary`. All are `@dataclass` with manual `to_dict()`/`from_dict()` — no Pydantic.

**Public API** (`rlm/__init__.py`): exports only `RLM`. Clients via `get_client()`, environments via `get_environment()` — both use lazy imports.

## Setup

We use `uv` for developing `rlm`. Python ≥ 3.11 required.
```bash
# Install uv (first time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup blank project if needed
uv init && uv venv --python 3.12
source .venv/bin/activate

# Install in editable mode
uv pip install -e .

# For Modal sandbox support
uv pip install -e ".[modal]"

# For Prime sandbox support
uv pip install -e ".[prime]"
```

## General Guidelines

### Code Style & Typing
- **Formatting**: Strict `ruff` enforcement. All PRs must pass `ruff check --fix .`
- **Typing**: Explicit types preferred
  - **OK**: `cast(...)`, `assert ...` for type narrowing
  - **SOMETIMES OK**: Untyped args for simple cases (e.g., prompt handlers)
  - **NOT OK**: `# type: ignore` without strong justification

### Naming Conventions
- **Methods**: snake_case
- **Classes**: PascalCase (e.g., `LocalREPL`, `PortkeyClient`)
- **Variables**: snake_case
- **Constants**: UPPER_CASE (e.g., `_SAFE_BUILTINS`, `RLM_SYSTEM_PROMPT`)

Do NOT use `_` prefix for private methods unless explicitly requested.

### Error Handling Philosophy
- **Fail fast, fail loud** - No defensive programming or silent fallbacks
- **Minimize branching** - Prefer single code paths; every `if`/`try` needs justification
- **Example**: Missing API key → immediate `ValueError`, not graceful fallback

## Build and Test

All commands are available via `make`. Prefer these over raw `uv run` invocations:

| Command | Action |
|---------|--------|
| `make install` | `uv sync` |
| `make install-dev` | `uv sync --group dev --group test` |
| `make install-modal` | `uv pip install -e ".[modal]"` |
| `make lint` | `uv run ruff check .` |
| `make format` | `uv run ruff format .` |
| `make test` | `uv run pytest` |
| `make typecheck` | `uv run ty check --exit-zero --output-format=concise` |
| `make check` | lint + format + test (run before PRs) |

**VSCode extension commands:**

| Command | Action |
|---------|--------|
| `make ext-install` | `cd vscode-extension && npm ci` |
| `make ext-build` | `cd vscode-extension && npx tsc -p ./` |
| `make ext-typecheck` | `cd vscode-extension && npx tsc --noEmit` |
| `make ext-lint` | `cd vscode-extension && npx eslint src/ --max-warnings 0` |
| `make ext-test` | `node vscode-extension/out/logger.test.js` |
| `make ext-check` | ext-typecheck + ext-lint + ext-test |

**Ruff config**: line-length=100, target Python 3.11, rules E/W/F/I/B/UP, `E501` ignored, double-quote format.
**Type checker**: `ty` (not mypy/pyright).

## Core Repository Development

For PRs to `rlm` core:
```bash
git clone https://github.com/alexzhang13/rlm.git
cd rlm

# Standard development:
uv sync

# Install dev + test dependencies:
uv sync --group dev --group test

# Install pre-commit hooks:
uv run pre-commit install
```

### Dependencies
- Avoid new core dependencies
- Use optional extras for non-essential features (e.g., `modal` extra)
- Exception: tiny deps that simplify widely-used code

### Testing
- `uv run pytest` with discovery under `tests/`
- Class-based test grouping (e.g., `class TestLocalREPLBasic`), plain `assert` statements
- Mock LM clients with `tests/mock_lm.py` (`BaseLM` subclass) or `unittest.mock.patch`
- Use `pytest.importorskip` for optional dependency tests (litellm, portkey_ai, etc.)
- No pytest fixtures — tests create objects directly
- Update tests when changing functionality
- For isolated environments, mock external services

### Documentation
- Keep concise and actionable
- Update README when behavior changes
- Avoid content duplication

### Scope
- Small, focused diffs
- One change per PR
- Backward compatibility is only desirable if it can be done without introducing excessive maintenance burden
- Delete dead code (don't guard it)

### Checklist

Before a PR:

```bash
# Run all checks (lint + format + test):
make check

# Or individually:
make lint
make format
make test

# Pre-commit hooks:
uv run pre-commit run --all-files
```

Ensure docs and tests are updated if necessary, and dead code is deleted. Strive for minimal, surgical diffs.

## Developing LM Clients

LM client implementations live in `rlm/clients/`. All clients must inherit from `BaseLM`.

### Client Pattern

| Base Class | When to Use | Key Methods |
|------------|-------------|-------------|
| `BaseLM` | All LM integrations | `completion`, `acompletion`, `get_usage_summary`, `get_last_usage` |

### Requirements
- Inherit from `BaseLM` in `rlm/clients/base_lm.py`
- Implement all abstract methods: `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`
- Track per-model usage (calls, input/output tokens)
- Handle both string and message list prompts
- Register client in `rlm/clients/__init__.py`

### Example Structure
```python
from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

class MyClient(BaseLM):
    def __init__(self, api_key: str, model_name: str, **kwargs):
        super().__init__(model_name=model_name, **kwargs)
        # Initialize your client
        
    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        # Handle both str and message list formats
        # Track usage with _track_cost()
        # Return response string
        
    def get_usage_summary(self) -> UsageSummary:
        # Return aggregated usage across all calls
```

### Configuration Guidelines
- **Environment variables**: ONLY for API keys (document in README)
- **Hardcode**: Default base URLs, reasonable defaults
- **Arguments**: Essential customization via `__init__()`

## Developing Environments

Environment implementations live in `rlm/environments/`. Choose the appropriate base class.

### Environment Pattern

| Pattern | Base Class | When to Use | Key Methods |
|---------|------------|-------------|-------------|
| **Non-isolated** | `NonIsolatedEnv` | Local execution, same machine | `setup`, `load_context`, `execute_code` |
| **Isolated** | `IsolatedEnv` | Cloud sandboxes (Modal, Prime) | `setup`, `load_context`, `execute_code` |

### Requirements
- Inherit from `NonIsolatedEnv` or `IsolatedEnv` in `rlm/environments/base_env.py`
- Implement all abstract methods: `setup`, `load_context`, `execute_code`
- Return `REPLResult` from `execute_code`
- Handle `lm_handler_address` for sub-LM calls via `llm_query()`
- Implement `cleanup()` for resource management
- Register environment in `rlm/environments/__init__.py`

### Key Implementation Details
- `setup()`: Initialize globals, locals, and helper functions
- `load_context()`: Make context available as `context` variable
- `execute_code()`: Execute code, capture stdout/stderr, return `REPLResult`
- Always provide `llm_query` and `llm_query_batched` functions in environment globals

### State Management
Environments must provide these globals to executed code:
- `context`: The loaded context payload
- `llm_query(prompt, model=None)`: For sub-LM calls
- `llm_query_batched(prompts, model=None)`: For batched sub-LM calls
- `FINAL_VAR(variable_name)`: For returning final answers

### Example Structure
```python
from rlm.environments.base_env import NonIsolatedEnv
from rlm.core.types import REPLResult

class MyEnvironment(NonIsolatedEnv):
    def __init__(self, lm_handler_address: tuple[str, int] | None = None, 
                 context_payload: dict | list | str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.lm_handler_address = lm_handler_address
        self.setup()
        if context_payload:
            self.load_context(context_payload)
            
    def setup(self):
        # Initialize execution namespace
        
    def load_context(self, context_payload: dict | list | str):
        # Make context available to executed code
        
    def execute_code(self, code: str) -> REPLResult:
        # Execute code and return REPLResult
        
    def cleanup(self):
        # Clean up resources
```

### Checklist
- Guidelines here are followed
- Environment works with basic RLM completion calls
- `cleanup()` properly releases all resources
- Sub-LM calls work via `llm_query()`

## Architecture: Environment ↔ LM Handler Communication

Understanding how environments communicate with the LM Handler is essential for developing new environments.

### Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Host Machine                                                       │
│  ┌─────────────┐       Socket (TCP)        ┌──────────────────────┐ │
│  │   RLM       │◄──────────────────────────►  LMHandler           │ │
│  │  (main)     │                           │  (ThreadingTCPServer)│ │
│  └─────────────┘                           └──────────────────────┘ │
│        │                                            ▲               │
│        ▼                                            │               │
│  ┌─────────────┐       Socket (TCP)                 │               │
│  │ LocalREPL   │────────────────────────────────────┘               │
│  │ (exec code) │  llm_query() → send_lm_request()                   │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Socket Protocol (Non-Isolated Environments)

Non-isolated environments like `LocalREPL` communicate directly with the `LMHandler` via TCP sockets using a length-prefixed JSON protocol:

**Protocol Format**: `4-byte big-endian length prefix + UTF-8 JSON payload`

```python
# Sending a message (from rlm/core/comms_utils.py)
def socket_send(sock: socket.socket, data: dict) -> None:
    payload = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)
```

**Request Flow**:
1. Environment's `llm_query(prompt)` is called during code execution
2. Creates `LMRequest` dataclass and calls `send_lm_request(address, request)`
3. Opens TCP connection to `LMHandler` at `(host, port)`
4. Sends length-prefixed JSON request
5. `LMHandler` processes via `LMRequestHandler.handle()`
6. Returns `LMResponse` with `RLMChatCompletion` or error

**Key Components**:
- `LMHandler` (`rlm/core/lm_handler.py`): Multi-threaded TCP server wrapping LM clients
- `LMRequest` / `LMResponse` (`rlm/core/comms_utils.py`): Typed request/response dataclasses
- `send_lm_request()` / `send_lm_request_batched()`: Helper functions for socket communication

### HTTP Broker Pattern (Isolated Environments)

Isolated environments (Modal, Prime) cannot directly connect to the host's socket server. They use an HTTP broker pattern:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Host Machine                                                               │
│  ┌─────────┐    Socket    ┌────────────┐    HTTP Poll    ┌────────────────┐ │
│  │   RLM   │◄────────────►│  LMHandler │◄────────────────│   ModalREPL    │ │
│  └─────────┘              └────────────┘                 │  (poller)      │ │
│                                                          └────────────────┘ │
│                                                                  │          │
│                                                          HTTP (tunnel)      │
│                                                                  │          │
└──────────────────────────────────────────────────────────────────┼──────────┘
                                                                   │
┌──────────────────────────────────────────────────────────────────┼──────────┐
│  Cloud Sandbox (Modal/Prime)                                     ▼          │
│  ┌─────────────┐     HTTP (localhost)     ┌─────────────────────────────┐   │
│  │ Exec Script │◄────────────────────────►│   Broker Server (Flask)     │   │
│  │ (exec code) │     /enqueue, etc.       │   - /enqueue (submit req)   │   │
│  └─────────────┘                          │   - /pending (poll reqs)    │   │
│                                           │   - /respond (return resp)  │   │
│                                           └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**How It Works**:

1. **Sandbox Setup**: Environment creates a cloud sandbox with an HTTP broker server running inside
2. **Tunnel Exposure**: Broker server is exposed via encrypted tunnel (e.g., Modal's `encrypted_ports`)
3. **Code Execution**: When `llm_query()` is called inside sandbox, it POSTs to `http://localhost:8080/enqueue`
4. **Request Queuing**: Broker queues the request and blocks waiting for response
5. **Host Polling**: `ModalREPL` on host polls `{tunnel_url}/pending` for new requests
6. **LM Forwarding**: Host forwards requests to `LMHandler` via socket, gets response
7. **Response Delivery**: Host POSTs response to `{tunnel_url}/respond`
8. **Unblocking**: Broker unblocks the original `/enqueue` call with the response

**Broker Endpoints**:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/enqueue` | POST | Submit LLM request from sandbox code (blocks until response) |
| `/pending` | GET | Get list of pending requests (called by host poller) |
| `/respond` | POST | Submit response for a request ID (called by host poller) |
| `/health` | GET | Health check |

**Key Implementation Details**:
- Broker runs as a Flask server inside the sandbox
- Uses `threading.Event` for request/response synchronization
- Poller thread on host runs in background with 100ms polling interval
- State persistence via `dill` serialization to `/tmp/rlm_state.dill`

### Implementing a New Isolated Environment

When building a new isolated environment (e.g., for a new cloud provider):

1. **Create broker server** - Flask/HTTP server with `/enqueue`, `/pending`, `/respond` endpoints
2. **Expose tunnel** - Use provider's tunnel/port forwarding to expose broker to host
3. **Implement poller** - Background thread on host to poll and forward requests
4. **Build exec script** - Script that runs inside sandbox with `llm_query()` calling broker
5. **Handle state** - Serialize/deserialize execution state between code blocks

See `rlm/environments/modal_repl.py` as the canonical reference implementation.

## Project Conventions

Patterns specific to this codebase that differ from standard Python practices:

- **`@dataclass` + manual `to_dict()`/`from_dict()`** for all types — no Pydantic or dataclasses-json
- **`defaultdict(int)`** for all token/usage tracking (see `rlm/clients/openai.py`)
- **Factory functions with lazy imports**: `get_client()` and `get_environment()` avoid loading unused backends
- **`SupportsPersistence`** is a `runtime_checkable Protocol` — duck typing, not ABC inheritance (see `rlm/environments/base_env.py`)
- **Context managers everywhere**: `RLM`, `LMHandler`, `LocalREPL` all support `with` blocks; `_spawn_completion_context()` is a `@contextmanager`
- **`TYPE_CHECKING` guards** for circular imports (e.g., `rlm/utils/parsing.py` imports `BaseEnv` only for type hints)
- **`textwrap.dedent`** for long string constants (see `rlm/utils/prompts.py`)
- **`VerbosePrinter`** methods are no-ops when `enabled=False` — no conditional checks at call sites
- **Socket protocol for IPC**: 4-byte big-endian length prefix + UTF-8 JSON (not HTTP/gRPC) between handler and non-isolated environments
- **Two sandbox tiers** (`rlm/core/sandbox/`): strict builtins for MCP exec, relaxed builtins for REPL (allows `__import__`, `open`)

### Key Reference Files

| File | Exemplifies |
|------|------------|
| `rlm/core/rlm.py` | Main loop, iteration, context manager pattern |
| `rlm/clients/openai.py` | Client implementation, usage tracking |
| `rlm/environments/local_repl.py` | Environment implementation, persistence, sandboxed exec |
| `rlm/environments/modal_repl.py` | Isolated environment, HTTP broker pattern |
| `rlm/core/types.py` | Dataclass pattern, serialization |
| `rlm/utils/parsing.py` | Code block extraction, `TYPE_CHECKING` guard |
| `tests/mock_lm.py` | Test mock pattern |
| `tests/test_multi_turn_integration.py` | Integration test pattern with `patch.object` |

## VSCode Extension Development

The extension lives in `vscode-extension/`. Zero runtime npm dependencies.

| File | Purpose |
|------|--------|
| `src/extension.ts` | Entry point, activation |
| `src/rlmParticipant.ts` | `@rlm` chat participant with commands: `analyze`, `summarize`, `search` |
| `src/orchestrator.ts` | Boundary between chat and Python backend, safety bounds |
| `src/backendBridge.ts` | Spawns Python sidecar, JSON-over-stdin/stdout protocol |
| `src/configService.ts` | Singleton for `rlm.*` settings with typed change events |
| `src/apiKeyManager.ts` | API key storage via `vscode.SecretStorage` |
| `src/logger.ts` | JSONL logger with rolling, redaction (10 patterns), crash-safe |
| `python/rlm_backend.py` | Python sidecar, creates `RLM` instances, only `local` REPL supported |

**TypeScript strictness**: `exactOptionalPropertyTypes`, all strict flags, ESLint `strictTypeChecked`, `no-explicit-any: "error"`, complexity cap at 15.

**Architecture decision**: Python backend owns the full RLM iteration loop; TypeScript orchestrator provides observability and safety bounds. See `docs/adr/001-extension-architecture.md`.

## MCP Gateway

The MCP gateway (`rlm/mcp_gateway/`) exposes RLM tools for IDE integration (Cursor). Entry point: `scripts/rlm_mcp_gateway.py`.

**Key tools**: `rlm.session.create`, `rlm.complete`, `rlm.exec.run`, `rlm.fs.list`, `rlm.search.query`, `rlm.search.regex`.

**Security**: `PathValidator` blocks traversal and restricted patterns (`.git`, `__pycache__`, `.venv`, `node_modules`, `.env`, `secrets`, `credentials`). Optional API key auth via `RLM_GATEWAY_API_KEY` env var.

## Security

- **Sandbox** (`rlm/core/sandbox/`): AST validation blocks dangerous modules (`os`, `subprocess`, `socket`, etc.) and functions (`eval`, `exec`, `compile`). `BlockedModule` replaces dangerous modules in `sys.modules` at runtime.
- **LocalREPL**: Uses `_SAFE_BUILTINS` — blocks `eval`, `exec`, `compile`, `input`, `globals`, `locals` by setting to `None`. Allows `__import__` and `open`.
- **Extension**: API keys stored in OS keychain (`vscode.SecretStorage`), env vars filtered via `filter_sensitive_keys()`, log redaction for 10 sensitive patterns, orphan process protection via parent PID monitoring.
- **Environment variables**: ONLY for API keys. Never hardcode secrets.

## Orchestrator Prompts

This project uses structured prompt files in `.github/prompts/` for multi-step workflows. Each prompt is idempotent — re-running produces the same effect without duplication or conflict.

### Quality Pipeline Philosophy

The orchestrator pipeline is designed to **converge**, not to "find all bugs":

- **Tool-first detection**: Debug plan uses real static analysis tools (`ruff`, `ty`, `tsc`, `eslint`, `pytest`) for deterministic, exhaustive findings within their domain. Model analysis supplements but never replaces tool output.
- **Orthogonal passes**: Detection is split into focused passes (tool errors → protocol/schema → incomplete implementations → complexity → test gaps) rather than one monolithic audit. Each pass has a narrow lens.
- **Evidence-based backlog**: Every backlog item must cite specific tool output, file:line references, or code snippets. Narrative-only findings are not accepted.
- **Regression-aware fixes**: Agent prompts require test coverage for cross-boundary fixes and re-run tool checks after every change. Items are not "done" without passing evidence gates.
- **Exposure tracking**: Fixes can expose latent issues. Agents add newly discovered issues to the backlog rather than ignoring them, with explicit convergence tracking in session summaries.

### Prompt Overview

| Prompt | Mode | Purpose | Artifacts |
|--------|------|---------|-----------|
| `research-plan.prompt.md` | Plan | Research upstream repos, forks, paper, IDE integration methods | `docs/orchestrator/research-findings.md`, `docs/orchestrator/research-backlog.md` |
| `research-agent.prompt.md` | Agent | Read plan artifacts from disk, then implement with test-verified evidence | Updates backlog + findings |
| `debug-plan.prompt.md` | Plan | Tool-assisted quality audit with orthogonal detection passes | `docs/orchestrator/debug-findings.md`, `docs/orchestrator/debug-backlog.md` |
| `debug-agent.prompt.md` | Agent | Fix backlog items with regression-aware verification and evidence gates | Updates backlog + findings |
| `refactor-plan.prompt.md` | Plan | Structural refactoring audit across six dimensions | `docs/orchestrator/refactor-findings.md`, `docs/orchestrator/refactor-backlog.md` |
| `refactor-agent.prompt.md` | Agent | Implement refactors with full migration, no backward compat, evidence gates | Updates backlog + findings |

### Workflow

1. Run a **plan** prompt first — it researches/audits and writes findings and backlog artifacts directly to disk
2. Run the matching **agent** prompt — it reads artifacts from disk and implements backlog items
3. Plans write only to `docs/orchestrator/` artifact files; agents implement and verify with `make check`
4. Research, debug, and refactor backlogs are separate — agents stay in their lane
5. Agent prompts enforce **evidence gates**: tool verification, test requirements, and regression checks before marking items done

### Artifact Ownership

- **Findings files** (`research-findings.md`, `debug-findings.md`, `refactor-findings.md`): Agents remove completed/implemented entries; only actionable findings remain
- **Backlog files** (`research-backlog.md`, `debug-backlog.md`, `refactor-backlog.md`): Items are removed by their respective agent when implemented; items include test requirements
- **State** (`state.json`, `run_log.md`): Updated by all agents (append-only for run_log); run_log includes tool output summaries
- **Plan** (`plan.md`): Never modified by agents; propose amendments if needed

### Pipeline Limitations

This pipeline cannot:
- Find runtime-only bugs, race conditions, or environment-specific failures (static analysis only)
- Guarantee exhaustive coverage — each pass has documented scope limits
- Verify behavioral correctness — it targets structural and type-level properties
- Prevent all regressions — fixes can expose latent issues (tracked via exposure checks)

These limitations are documented in the debug-plan findings artifact and acknowledged in session summaries.

### Instruction File Roles

| File | Audience | Scope |
|------|----------|-------|
| `AGENTS.md` | All AI agents and human contributors | Canonical project guide — architecture, conventions, patterns |
| `CLAUDE.md` | Claude-based agents (Claude Code, Cursor with Claude) | Quick reference + orchestrator prompt documentation |
| `.github/copilot-instructions.md` | GitHub Copilot (VS Code Chat, Agent Mode) | Quick reference + orchestrator prompt documentation |
| `.cursor/rules/*.mdc` | Cursor | Architecture + MCP integration rules |
| `.github/prompts/*.prompt.md` | All agents (invoked explicitly) | Task-specific workflows with idempotent protocols |
