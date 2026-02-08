# RLM VS Code Extension

The RLM extension integrates Recursive Language Models into VS Code's chat interface via the `@rlm` chat participant.

## How It Works

1. **You type** `@rlm <question>` in VS Code Chat
2. **The extension** sends your prompt to the Python RLM backend
3. **Python runs** `RLM.completion()` — iteratively executing code in a REPL, calling sub-LLMs, and reasoning
4. **The result** streams back to the chat UI

The entire RLM loop (prompt construction, code parsing, REPL execution, FINAL detection) runs in Python. The TypeScript extension is a thin bridge.

## File Structure

```
vscode-extension/
├── src/
│   ├── extension.ts        # Entry point, command registration
│   ├── rlmParticipant.ts   # Chat Participant handler
│   ├── backendBridge.ts     # Python subprocess management
│   ├── types.ts             # Shared type definitions
│   ├── platform.ts          # VS Code vs Cursor detection
│   ├── apiKeyManager.ts     # SecretStorage-based key management
│   └── logger.ts            # Structured JSONL logger
├── python/
│   └── rlm_backend.py       # Full RLM backend (imports rlm package)
├── package.json              # Extension manifest
└── tsconfig.json             # TypeScript config (strict mode)
```

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

## Development

```bash
cd vscode-extension
npm install
npm run compile    # or: npm run watch

# Launch: F5 in VS Code (launches Extension Host)
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
