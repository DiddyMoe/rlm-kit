# Security surfaces: code execution and paths

Two distinct surfaces run user- or agent-supplied code. Documented here for safe defaults and audit. No code change; documentation only.

## 1. REPL environments (LocalREPL, DockerREPL, ModalREPL, etc.)

- **Where**: `rlm/environments/` — code executed inside the RLM loop (model-generated code blocks).
- **Builtins**: `get_safe_builtins_for_repl()` from `rlm/core/sandbox/safe_builtins.py`. Includes `globals`, `locals`, `__import__`, and `open` so that RLM can inspect the REPL namespace and load context.
- **Use**: Trusted REPL processes only. Not for arbitrary IDE/MCP-submitted code.
- **Path model**: Environment-specific (e.g. container filesystem, workspace mount). No shared PathValidator; each env defines its own working set.

## 2. MCP exec tool (`rlm_exec_run`)

- **Where**: `rlm/mcp_gateway/tools/exec_tools.py` — code submitted via the MCP tool from Cursor or VS Code agents.
- **Builtins**: `get_safe_builtins()` only. Does **not** include `globals`, `locals`, `__import__`, or `open`. Stricter sandbox for unbounded agent code.
- **Path validation**: `rlm/mcp_gateway/validation.py` — `PathValidator.validate_path(path, allowed_roots)`. Paths must fall under one of the session’s `allowed_roots` (set via `rlm_roots_set`). Symlinks and `..` are resolved and checked; path traversal is rejected.
- **Limits**: `rlm/mcp_gateway/constants.py` — `MAX_EXEC_CODE_SIZE` (10KB), `MAX_EXEC_TIMEOUT_MS` (5s), `MAX_EXEC_MEMORY_MB` (256). AST validation and restricted execution in `rlm/core/sandbox/`.

## Summary

| Surface       | Builtins              | Path checks      | Typical caller        |
|---------------|------------------------|------------------|------------------------|
| REPL envs     | get_safe_builtins_for_repl | Env-specific     | RLM loop (model code) |
| MCP exec tool | get_safe_builtins     | PathValidator    | IDE agent (rlm_exec_run) |

Aligning constants (e.g. timeouts, code size) between `rlm/core/sandbox` and `rlm/mcp_gateway/constants` is a possible future patch; see proposal #4 option B.
