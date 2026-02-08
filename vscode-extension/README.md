# RLM VS Code Extension

The RLM extension integrates Recursive Language Models into VS Code's
chat interface via the `@rlm` chat participant. Also works in Cursor IDE.

## How It Works

1. **You type** `@rlm <question>` in VS Code Chat
2. **The Orchestrator** enforces bounded recursion (max iterations,
   wall-clock budget) and emits trace spans
3. **The BackendBridge** sends your prompt to the Python RLM backend
4. **Python runs** `RLM.completion()` — iteratively executing code in a
   REPL, calling sub-LLMs, and reasoning
5. **The result** streams back to the chat UI

The full RLM loop (prompt construction, code parsing, REPL execution,
FINAL detection) runs in Python. TypeScript provides orchestration,
tracing, and a security boundary.

## Architecture

```
Chat UI ──► RLMChatParticipant
                  │
                  ▼
            ConfigService  (centralized typed settings)
                  │
                  ▼
            Orchestrator   (bounded recursion, tracing)
                  │
                  ▼
            BackendBridge  (JSON-over-stdin/stdout)
                  │
                  ▼
            rlm_backend.py (Python child process)
```

## File Structure

```
src/
├── extension.ts        # Entry point, command registration
├── rlmParticipant.ts   # Chat Participant handler
├── orchestrator.ts     # Bounded recursion, wall-clock budget, tracing
├── configService.ts    # Centralized typed settings reader
├── backendBridge.ts    # Python subprocess management
├── types.ts            # Shared type definitions (no vscode imports)
├── platform.ts         # VS Code vs Cursor detection
├── apiKeyManager.ts    # SecretStorage-based key management
├── logger.ts           # Structured JSONL logger with redaction
└── logger.test.ts      # 15 unit tests for logger
python/
└── rlm_backend.py      # Full RLM backend (imports rlm package)
```

## Quality Gates

Enforced in CI (`.github/workflows/extension.yml`):

| Gate | Command | Threshold |
|------|---------|-----------|
| TypeScript strict typecheck | `npx tsc --noEmit` | 0 errors |
| ESLint strict | `npx eslint src/ --max-warnings 0` | 0 errors, 0 warnings |
| Unit tests | `node out/logger.test.js` | 15/15 pass |

## LLM Provider Modes

### Builtin Mode (`rlm.llmProvider: "builtin"`)

- Uses VS Code's Language Model API (`vscode.lm`)
- Requires a GitHub Copilot subscription
- Zero API keys needed
- Python sends `llm_request`; TS fulfills via `vscode.lm`

### API Key Mode (`rlm.llmProvider: "api_key"`)

- Uses `rlm/clients/` directly (OpenAI, Anthropic, etc.)
- Store keys securely via **RLM: Set API Key** command
- Python calls the API directly — no `vscode.lm` involvement

## Protocol

The extension and Python backend communicate via JSON-over-newline on
stdin/stdout:

| Direction | Message | Purpose |
|-----------|---------|---------|
| TS → Py | `configure` | Set provider, backend, model on startup |
| TS → Py | `completion` | Run full RLM completion |
| Py → TS | `llm_request` | Request LLM call (builtin mode) |
| TS → Py | `llm_response` | Return LLM result |
| Py → TS | `progress` | Iteration progress updates |
| Py → TS | `result` | Final answer |
| Py → TS | `error` | Error message |

## Development

```bash
cd vscode-extension
npm ci && npm run compile

# Launch: F5 in VS Code (Extension Development Host)

npx tsc --noEmit                           # typecheck
npx eslint src/ --max-warnings 0           # lint
npx tsc -p ./ && node out/logger.test.js   # test
```
