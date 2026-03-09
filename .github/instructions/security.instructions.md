# Security and Sandbox

## Two Execution Surfaces

| Surface | Builtins | Path Checks | Typical Caller |
|---------|----------|-------------|----------------|
| REPL environments | `get_safe_builtins_for_repl()` | Env-specific | RLM loop (model-generated code) |
| MCP exec tool (`rlm_exec_run`) | `get_safe_builtins()` | PathValidator | IDE agent |

### REPL Environments (Relaxed)

- **Location**: `rlm/environments/` — code executed inside the RLM loop
- **Builtins**: `get_safe_builtins_for_repl()` from `rlm/core/sandbox/safe_builtins.py`
  - Allows: `__import__`, `open` (needed for context loading)
  - Also enables: `globals`, `locals` (note: `LocalREPL` overrides these back to `None`)
  - Blocks: `eval`, `exec`, `compile`, `input` → set to `None`
- **Path model**: Environment-specific (container filesystem, workspace mount)

### MCP Exec Tool (Strict)

- **Location**: `rlm/mcp_gateway/tools/exec_tools.py`
- **Builtins**: `get_safe_builtins()` only
  - Blocks: `eval`, `exec`, `compile`, `input`, `globals`, `locals`, `__import__`, `open`, `file` → all set to `None`
- **Path validation**: `PathValidator.validate_path()` — paths must fall under session's `allowed_roots`
- **Resource limits**: `MAX_EXEC_CODE_SIZE` (10KB), `MAX_EXEC_TIMEOUT_MS` (5s), `MAX_EXEC_MEMORY_MB` (256)

## AST Validation

`rlm/core/sandbox/ast_validator.py` blocks dangerous modules and functions at the AST level before execution:
- Blocked modules: `os`, `subprocess`, `socket`, `shutil`, `ctypes`, `pickle`, `marshal`, `importlib`, `sys`, `multiprocessing`, `requests`, `urllib`, `http`, `httpx`, etc.
- Blocked functions: `eval`, `exec`, `compile`, `__import__`, `open`, `file`, `input`, `raw_input`, `execfile`, `reload`, `exit`, `quit`
- `BlockedModule` replaces dangerous modules in `sys.modules` at runtime

## Extension Security

- **API keys**: Stored via `vscode.SecretStorage` (OS keychain) — never on disk, never in settings
- **Environment filtering**: `BackendBridge.buildChildEnv()` blocks cloud provider vars, tokens, secrets from spawned processes
- **Log redaction**: 9 regex patterns covering:
  - OpenAI keys (`sk-`)
  - Bearer tokens
  - API key fields in JSON
  - Google keys (`AIza`)
  - Generic token/key prefixes
- **Orphan protection**: Python sidecar monitors parent PID every 2s, exits if parent dies
- **Timeout enforcement**: Multiple layers (orchestrator wall-clock, backend completion timeout, REPL execution timeout)

## MCP Gateway Security

- **PathValidator**: Blocks traversal (`..`), symlink resolution, restricted patterns:
  - `.git`, `__pycache__`, `.venv`, `node_modules`, `.env`, `secrets`, `credentials`
- **API key auth**: `RLM_GATEWAY_API_KEY` env var for HTTP mode (simple string match)
- **OAuth support**: RFC 7662 token introspection via `GatewayAuth` in `auth.py`:
  - Introspects tokens via HTTP POST to configured endpoint
  - Caches validated tokens with TTL from `exp` claim
  - Supports `oauth_metadata()` for well-known endpoint discovery
- **Session cancellation**: `cancel_session()` / `cancel_by_request_id()` with request ID → session mapping
- **Session budget checks**: Tool call count, output bytes, timeout enforcement via `check_budget()`

## Environment Variables

- **ONLY used for API keys** — never hardcode secrets
- Documented in `.env.example`:
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PORTKEY_API_KEY`, `GOOGLE_API_KEY`, `PRIME_API_KEY`
  - Optional: `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `RLM_LOG_LEVEL`, `RLM_LOG_DIR`

## Failure Modes

- **Provider errors**: API key missing/invalid, rate limit, timeout → fail fast with ValueError
- **Socket failures**: Transient connection errors → `retry_with_backoff` (max 3 attempts)
- **Recursion runaway**: Python `RLMConfig.max_iterations` (default 30) with no hard cap in core; TypeScript orchestrator enforces `ABSOLUTE_MAX_ITERATIONS=50` as extension-side hard cap
- **Context overflow**: `MAX_SUB_CALL_PROMPT_CHARS = 100_000` (~25k tokens)
- **Cancellation**: `session.cancellation_requested` flag for MCP sessions; extension cancel via `CancelMessage`; hard-kill fallback at 5s
