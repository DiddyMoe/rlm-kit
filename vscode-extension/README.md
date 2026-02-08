# RLM VS Code Extension

The RLM extension integrates Recursive Language Models into VS Code's chat interface via the `@rlm` chat participant. It also works in Cursor IDE.

## How It Works

1. **You type** `@rlm <question>` in VS Code Chat
2. **The Orchestrator** enforces bounded recursion (max iterations, wall-clock budget) and emits trace spans
3. **The BackendBridge** sends your prompt to the Python RLM backend
4. **Python runs** `RLM.completion()` — iteratively executing code in a REPL, calling sub-LLMs, and reasoning
5. **The result** streams back to the chat UI

The entire RLM loop (prompt construction, code parsing, REPL execution, FINAL detection) runs in Python. The TypeScript extension provides orchestration, tracing, and a security boundary.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  VS Code / Cursor                                        │
│                                                          │
│  Chat UI  ──►  RLMChatParticipant                        │
│                    │                                     │
│                    ▼                                     │
│              ConfigService  (centralized typed settings)  │
│                    │                                     │
│                    ▼                                     │
│              Orchestrator  (bounded recursion, tracing)   │
│                    │                                     │
│                    ▼                                     │
│              BackendBridge  (JSON-over-stdin/stdout)      │
│                    │                                     │
│                    ▼                                     │
│              Python rlm_backend.py  (child process)      │
└──────────────────────────────────────────────────────────┘
```

## File Structure

```
vscode-extension/
├── src/
│   ├── extension.ts        # Entry point, command registration
│   ├── rlmParticipant.ts   # Chat Participant handler
│   ├── orchestrator.ts     # Bounded recursion, wall-clock budget, tracing
│   ├── configService.ts    # Centralized typed settings reader
│   ├── backendBridge.ts    # Python subprocess management
│   ├── types.ts            # Shared type definitions
│   ├── platform.ts         # VS Code vs Cursor detection
│   ├── apiKeyManager.ts    # SecretStorage-based key management
│   ├── logger.ts           # Structured JSONL logger with redaction
│   └── logger.test.ts      # 12 unit tests for logger
├── python/
│   └── rlm_backend.py      # Full RLM backend (imports rlm package)
├── eslint.config.cjs        # ESLint v9 flat config (strict)
├── package.json              # Extension manifest
└── tsconfig.json             # TypeScript config (strict mode)
```

## Quality Gates

All enforced in CI (`.github/workflows/extension.yml`):

| Gate | Command | Threshold |
|------|---------|-----------|
| TypeScript strict typecheck | `npx tsc --noEmit` | 0 errors |
| ESLint strict | `npx eslint src/ --max-warnings 0` | 0 errors, 0 warnings |
| Unit tests | `node out/logger.test.js` | 12/12 pass |

## LLM Provider Modes

### Builtin Mode (`rlm.llmProvider: "builtin"`)
- Uses VS Code's Language Model API (`vscode.lm`)
- Requires a GitHub Copilot subscription
- Zero API keys needed
- The Python backend sends `llm_request` messages; the TS extension fulfills them via `vscode.lm`

### API Key Mode (`rlm.llmProvider: "api_key"`)
- Uses `rlm/clients/` directly (OpenAI, Anthropic, etc.)
- Set your backend via `rlm.backend` and model via `rlm.model`
- Store API keys securely via `RLM: Set API Key` command
- No `vscode.lm` involvement — Python calls the API directly

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `rlm.llmProvider` | enum | `builtin` | LLM provider mode |
| `rlm.backend` | enum | `openai` | Client backend for API key mode |
| `rlm.model` | string | `gpt-4o` | Model name |
| `rlm.maxIterations` | number | `15` | Max RLM iterations per run |
| `rlm.tracingEnabled` | boolean | `true` | Enable JSONL trace logging |
| `rlm.logLevel` | enum | `info` | Minimum log level |
| `rlm.logMaxSizeMB` | number | `10` | Max log file size before rotation |

## Development

```bash
cd vscode-extension
npm install
npm run compile    # or: npm run watch

# Launch: F5 in VS Code (launches Extension Host)

# Quality checks:
npx tsc --noEmit              # typecheck
npx eslint src/ --max-warnings 0  # lint
npx tsc -p ./ && node out/logger.test.js  # tests
```

## Protocol

The extension and Python backend communicate via JSON-over-newline on stdin/stdout:

| Direction | Message | Purpose |
|-----------|---------|---------|
| TS → Py | `configure` | Set provider, backend, model on startup |
| TS → Py | `completion` | Run full RLM completion |
| Py → TS | `llm_request` | Request LLM call (builtin mode) |
| TS → Py | `llm_response` | Return LLM result |
| Py → TS | `progress` | Iteration progress updates |
| Py → TS | `result` | Final answer |
| Py → TS | `error` | Error message |
