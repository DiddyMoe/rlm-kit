# IDE touchpoints

Map of where the repo interfaces with VS Code and Cursor expectations.

## VS Code

### Chat Participant

- **Registration**: `vscode-extension/src/rlmParticipant.ts` — `vscode.chat.createChatParticipant(PARTICIPANT_ID, handler)`. Participant id: `rlm-chat.rlm`; name: `rlm`. Only registered when `hasChatApi()` is true (skipped on Cursor).
- **Handler flow**: User message → `handleRequest()` → resolve references (files/workspace) → `Orchestrator.run()` with config from ConfigService → BackendBridge sends JSON to Python backend.
- **Backend spawn**: `backendBridge.ts` — spawns `python -u rlm_backend.py` with filtered env, cwd = repo root (parent of vscode-extension). Stdio: JSON-over-newline.
- **vscode.lm usage**: In builtin mode, Python sends `{"type":"llm_request","nonce":...,"prompt":...,"model":...}`; extension calls `vscode.lm.selectChatModels()` / chat request and replies with `{"type":"llm_response","nonce":...,"text":...}`.

### Settings

- **Keys**: All under `rlm.*` — provider, backend, model, baseUrl, subBackend, subModel, maxIterations, maxOutputChars, pythonPath, showIterationDetails, tracingEnabled, logLevel, logMaxSizeMB. See `vscode-extension/package.json` contributes.configuration and `configService.ts`.
- **Trace log**: Configurable; default workspace `logs/trace.jsonl`; redaction and rolling in `logger.ts`.

### Commands

- **RLM: Set API Key** (and similar) — in package.json; implemented via ApiKeyManager (SecretStorage).

## Cursor

### MCP

- **Config**: `.cursor/mcp.json` — key `mcpServers.rlm-gateway` (or `mcp.servers` in some schemas) with `command`, `args`, `cwd`, `env`. Typical: `uv run python scripts/rlm_mcp_gateway.py` with `PYTHONPATH=${workspaceFolder}`.
- **Server mode**: Stdio (default). HTTP: `--mode http --repo-path ... --api-key ...` (optional; requires FastAPI/uvicorn and API key).
- **Tool names**: `rlm.session.create`, `rlm.session.close`, `rlm.roots.set`, `rlm.fs.list`, `rlm.fs.manifest`, `rlm.fs.handle.create`, `rlm.span.read`, `rlm.chunk.create`, `rlm.chunk.get`, `rlm.search.query`, `rlm.search.regex`, `rlm.exec.run`, `rlm.complete`, `rlm.provenance.report`.
- **No Chat Participant**: Extension does not register the chat participant when running in Cursor (platform detection in `platform.ts`); Cursor uses MCP tools only.

### Rules / playbooks

- **.cursorrules** — Project-level rules for Cursor; describes MCP usage, tool list, and architecture. No programmatic contract; documentation only.
