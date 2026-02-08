# ADR-001: Extension Architecture — RLM Orchestrator Integration

## Status

Accepted (updated 2026-02-07)

## Context

The repository delivers a VS Code / Cursor extension that integrates
Recursive Language Model (RLM) inference into the editor's built-in chat
agent workflow.

Key components:

| Layer | Language | Purpose |
|-------|----------|---------|
| `vscode-extension/src/` | TypeScript | Extension host: chat participant, orchestrator, bridge, config, logger |
| `vscode-extension/python/rlm_backend.py` | Python | Glue process spawned by the extension; creates `RLM` instances |
| `rlm/` | Python | Core RLM engine, LM clients, local REPL, parsing, prompts |

## Decision

### Architecture

```
User → @rlm Chat → RLMChatParticipant → Orchestrator → BackendBridge → rlm_backend.py
                                            ↕                               ↕
                                     ConfigService                    RLM.completion()
                                     Logger (JSONL)                   + LocalREPL
```

**Orchestrator** (`src/orchestrator.ts`) — the boundary between the chat
participant and the Python backend.  It does NOT duplicate the Python RLM
iteration loop.  It enforces:

- Bounded recursion depth (configurable, hard cap 50)
- Wall-clock timeout (10 min default)
- Trace span emission for every orchestration call
- Error boundary with structured logging

**BackendBridge** (`src/backendBridge.ts`) — spawns the Python process
with a filtered environment (secrets, cloud vars, Electron vars blocked).
JSON-over-newline protocol on stdin/stdout.  Generation counter prevents
stale exit/error events from affecting new sessions.

**ConfigService** (`src/configService.ts`) — singleton reading all
`rlm.*` settings.  Emits typed change events.  Controls tracing toggle,
log level, recursion limits, and safety budgets.

**Logger** (`src/logger.ts`) — structured JSONL logger:

- Output: `logs/trace.jsonl` (workspace-local) or global storage
- Rolling at configurable threshold (default 10 MB, keeps newest 50%)
- 10 redaction patterns covering API keys, tokens, secrets
- Crash-safe: sync flush on WARN+, `process.on('uncaughtException')`
- Toggleable via `rlm.tracingEnabled`

**Platform detection** (`src/platform.ts`) — detects VS Code vs Cursor.
VS Code → chat participant registered.  Cursor → api_key mode.

### Typing strategy

- `exactOptionalPropertyTypes: true` in tsconfig
- All `strict` flags enabled
- ESLint `strictTypeChecked` ruleset
- `no-explicit-any: "error"`, `no-floating-promises: "error"`
- Complexity cap at 15

### Python sidecar

The `rlm/` package is an isolated Python library.  The only bridge is
`rlm_backend.py` which speaks the JSON protocol defined in `types.ts`.
The extension sets `PYTHONPATH` so `import rlm` resolves without
installation.  Only the `local` REPL environment is supported.

### Security model

- API keys stored via `vscode.SecretStorage` (OS keychain) — never on disk
- Environment variables filtered: cloud provider vars, tokens, secrets blocked
- Log redaction: 10 regex patterns, applied recursively to nested objects/arrays
- Orphan protection: Python process monitors parent PID
- Timeout enforcement at multiple layers

## Consequences

- Extension bundle has zero runtime npm dependencies
- Python backend owns the full RLM iteration loop
- TypeScript orchestrator provides observability, safety bounds, configuration
- Both VS Code (chat participant) and Cursor (api_key mode) are supported
