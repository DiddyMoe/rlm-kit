# TypeScript Conventions (VS Code Extension)

## Setup

The extension lives in `vscode-extension/`. Zero runtime npm dependencies.

```bash
make ext-install    # npm ci
make ext-build      # npx tsc -p ./
make ext-typecheck  # npx tsc --noEmit
make ext-lint       # npx eslint src/ --max-warnings 0
make ext-test       # Build + run unit tests
make ext-check      # typecheck + lint + test
make ext-clean      # Remove out/ directory
```

## Strictness

- `strict: true` in tsconfig.json with all strict flags enabled
- `exactOptionalPropertyTypes: true`
- `noUnusedLocals`, `noUnusedParameters`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`
- Target: ES2022, CommonJS module
- ESLint: `strictTypeChecked` ruleset
- `@typescript-eslint/no-explicit-any: "error"` — no `any` allowed
- `@typescript-eslint/no-floating-promises: "error"` — all promises must be handled
- `@typescript-eslint/no-unsafe-*: "error"` (assignment, call, member-access, return)
- Complexity cap: 15 (warn level)

## Typing Rules

- **No `any`**: Use `unknown` and narrow with type guards (`typeof`, `instanceof`, discriminated unions)
- **No type assertions (`as`)** without documented justification
- **All interface fields `readonly`** unless mutation is necessary
- **Use discriminated unions** for message types (e.g., `type: "result" | "error" | "progress"`)
- `_` prefix for unused parameters (ESLint allows this)

## Complexity

Same limits as Python:
- Maximum 3 levels of nesting inside any function body
- Maximum 50 lines per function
- Maximum 5 parameters per function
- Prefer early returns / guard clauses

## Error Handling

- All async operations must have try/catch
- Errors propagate to user (shown in chat)
- All event listeners and subscriptions tracked and disposed via `vscode.Disposable`
- Use `context.subscriptions.push()` for cleanup

## Architecture

```
User → @rlm Chat → RLMChatParticipant → Orchestrator → BackendBridge → rlm_backend.py
                                            ↕                               ↕
                                     ConfigService                    RLM.completion()
                                     Logger (JSONL)                   + LocalREPL
```

**Orchestrator** — boundary between chat and Python backend. Enforces:
- Bounded recursion depth (configurable, hard cap 50)
- Wall-clock timeout (10 min default)
- Trace span emission
- Error boundary with structured logging

**BackendBridge** — spawns Python process with filtered environment. JSON-over-newline protocol on stdin/stdout. Generation counter prevents stale events.

**ConfigService** — singleton reading `rlm.*` settings. Emits typed change events.

**Logger** — JSONL with rolling (10 MB default), 9 redaction patterns, crash-safe sync flush.

**Platform** — detects VS Code vs Cursor. VS Code → chat participant registered. Cursor → MCP only.

## Key Files

| File | Purpose |
|------|---------|
| `src/extension.ts` | Entry point, activation, command/tool registration |
| `src/rlmParticipant.ts` | `@rlm` chat participant (commands: analyze, summarize, search) |
| `src/orchestrator.ts` | Chat-to-backend boundary, safety bounds |
| `src/backendBridge.ts` | Spawns Python sidecar, JSON-over-stdin/stdout protocol |
| `src/configService.ts` | Singleton for rlm.* settings |
| `src/configModel.ts` | `RlmConfig` interface, defaults (`DEFAULT_RLM_CONFIG`), normalization |
| `src/apiKeyManager.ts` | API key storage via vscode.SecretStorage |
| `src/logger.ts` | JSONL logger with rolling, redaction, crash-safe |
| `src/platform.ts` | VS Code vs Cursor detection |
| `src/platformLogic.ts` | Pure detection logic (testable without VS Code host) |
| `src/tools.ts` | Language Model Tools (`rlm_analyze`, `rlm_execute`) |
| `src/toolsFormatting.ts` | Tool output formatting and truncation |
| `src/mcpServerProvider.ts` | MCP server definition provider for VS Code |
| `src/cursorMcpRegistration.ts` | MCP server registration for Cursor |
| `src/types.ts` | Protocol types (OutboundMessage, InboundMessage, PendingRequest) |
| `python/rlm_backend.py` | Python sidecar, creates RLM instances |

## Design Patterns

### Pure Logic for Testing

Extract pure logic into separate files for unit testing without VS Code host:
- `platformLogic.ts` — pure detection logic, tested by `platformLogic.test.ts`
- `configModel.ts` — config normalization logic, tested by `configModel.test.ts`
- `toolsFormatting.ts` — output formatting, tested by `toolsFormatting.test.ts`

### Protocol Contract as Types

`types.ts` defines the full protocol contract as discriminated unions:
- `OutboundMessage` — 7 message types (configure, completion, execute, cancel, llm_response, ping, shutdown)
- `InboundMessage` — 9 message types (ready, configured, result, exec_result, llm_request, progress, chunk, error, pong)
- Changes to protocol types must be reflected in both TypeScript and Python sides

## Protocol (BackendBridge ↔ rlm_backend.py)

JSON-over-newline on stdin/stdout.

**Outbound (TS → Python)**: `configure`, `completion`, `execute`, `cancel`, `llm_response`, `ping`, `shutdown`
**Inbound (Python → TS)**: `ready`, `configured`, `result`, `exec_result`, `llm_request`, `progress`, `chunk`, `error`, `pong` (9 types)

Orphan process protection: Python sidecar monitors parent PID every 2s, exits if parent dies.

Thread-safe IO: `_stdout_lock` in Python, `generation` counter in TypeScript.

## Security

- API keys stored via `vscode.SecretStorage` (OS keychain) — never on disk
- Environment vars filtered: cloud provider vars, tokens, secrets blocked
- Log redaction: 9 regex patterns (OpenAI keys, bearer tokens, etc.)
- Orphan protection: Python process monitors parent PID
- Timeout enforcement at multiple layers

## Dependencies

- **Zero runtime npm dependencies** — all dependencies are `devDependencies`
- Extension must remain self-contained
