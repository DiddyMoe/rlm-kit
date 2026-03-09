# IDE Integration

## VS Code Integration

### Chat Participant

- **Participant ID**: `rlm-chat.rlm` (display name: `rlm`)
- **Commands**: `analyze`, `summarize`, `search`
- **Registration**: `vscode.chat.createChatParticipant()` in `rlmParticipant.ts`
- **Only registered when** `hasChatApi()` is true (skipped on Cursor)

### Language Model Tools

Two LM tools registered via `vscode.lm.registerTool()` in `tools.ts`:

| Tool | ID | Purpose |
|------|----|---------|
| `RlmAnalyzeTool` | `rlm_analyze` | Recursive analysis using RLM |
| `RlmExecuteTool` | `rlm_execute` | Python code execution in REPL |

- Both implement `vscode.LanguageModelTool`
- `prepareInvocation()` provides confirmation dialogs before execution
- Output formatting in `toolsFormatting.ts`

### MCP Server Definition Provider

VS Code's native MCP integration via `vscode.lm.registerMcpServerDefinitionProvider()` in `mcpServerProvider.ts`:
- Provider ID: `rlm-chat.rlmMcpServer`
- Registers the MCP gateway as a stdio server
- Adds icon from `vscode-extension/media/rlm-icon.svg`

### Extension Commands

| Command | Purpose |
|---------|---------|
| `rlm-chat.openChat` | Open RLM chat panel |
| `rlm-chat.newSession` | Start new chat session |
| `rlm-chat.openLog` | Open log file |
| `rlm-chat.setApiKey` | Set API key via SecretStorage |
| `rlm-chat.clearApiKey` | "Clear All API Keys" |
| `rlm-chat.showProvider` | Show current provider info |

### Platform Detection

`platform.ts` / `platformLogic.ts` detect the editor environment:
- `detectEditorKind()` → `"vscode" | "cursor" | "unknown"`
- Heuristics: appName contains "Cursor"? uriScheme starts with "cursor"? `vscode.lm` available?
- Pure detection logic in `platformLogic.ts` for unit testing without VS Code host

### Three Activation Paths in `extension.ts`

| Editor | Registers |
|--------|-----------|
| VS Code | Chat Participant + MCP Server Definition Provider + Language Model Tools |
| Cursor | Cursor MCP server registration only (via `cursorMcpRegistration.ts`) |
| Unknown | Falls back to VS Code path |

### Provider Modes

1. **Built-in (Copilot)**: Uses `vscode.lm.selectChatModels()` — no API key needed
2. **API key**: User sets `rlm.llmProvider = "api_key"`, configures `rlm.backend`/`rlm.model`, stores key via "RLM: Set API Key" command

### Settings (`rlm.*`)

| Setting | Purpose |
|---------|---------|
| `rlm.llmProvider` | `"builtin"` or `"api_key"` |
| `rlm.backend` | LM backend (openai, anthropic, etc.) |
| `rlm.model` | Model name |
| `rlm.baseUrl` | Custom API base URL |
| `rlm.subBackend` | Sub-LM backend for recursive calls |
| `rlm.subModel` | Sub-LM model |
| `rlm.maxIterations` | Max REPL iterations |
| `rlm.maxOutputChars` | Max output character length |
| `rlm.pythonPath` | Python interpreter path |
| `rlm.showIterationDetails` | Show iteration details in chat |
| `rlm.environment` | REPL environment type (local, docker, modal, etc.) |
| `rlm.tracingEnabled` | Enable JSONL tracing |
| `rlm.logLevel` | Log level |
| `rlm.logMaxSizeMB` | Max log file size before rolling |

### Backend Aliases

In API-key mode, backend aliases are auto-resolved:
- `openrouter` → `litellm` (model prefixed as `openrouter/<model>`)
- `vercel` → `litellm` (model prefixed as `vercel/<model>`)
- `vllm` → `litellm` (model prefixed as `vllm/<model>`)

### Backend Process

Extension spawns `python -u rlm_backend.py` with:
- Working directory: repo root (parent of `vscode-extension/`)
- `PYTHONPATH` set so `import rlm` resolves without installation
- Only `local` REPL environment supported
- Filtered environment: cloud provider vars, tokens, secrets blocked

## Cursor Integration

### MCP-Only

Cursor does not expose the VS Code Chat API or `vscode.lm`. The Chat Participant is not registered. Integration is via MCP tools only.

### Setup

1. MCP config: `.cursor/mcp.json` in workspace
2. Restart Cursor or reload MCP
3. Cursor discovers tools from the RLM MCP server

### Usage Patterns

**Zero-API-key (Cursor-as-outer-loop)**:
- Cursor's own LLM drives the agent
- RLM tools (`rlm_fs_list`, `rlm_search_query`, `rlm_span_read`, etc.) called by the agent
- No RLM API key needed

**Full RLM completion**:
- Agent invokes `rlm_complete` tool
- Requires API key set in environment (e.g., `OPENAI_API_KEY` in `.cursor/mcp.json` env)

### Cursor Rules

- `.cursor/rules/rlm-architecture.mdc` — architecture and conventions (alwaysApply)
- `.cursor/rules/mcp-tool-use.mdc` — MCP-first tool usage guidance (alwaysApply)
- `.cursor/skills/rlm-mcp-workflow/` — Agent skill for bounded retrieval

### MCP Tool Usage Sequence

Preferred retrieval order (from `.cursor/rules/mcp-tool-use.mdc`):
1. `rlm_session_create` — create session
2. `rlm_roots_set` — scope filesystem roots
3. `rlm_search_query` / `rlm_search_regex` — search-first retrieval
4. `rlm_span_read` / `rlm_chunk_get` — bounded context reads
5. `rlm_complete` — only after context is narrowed

## Development Setup

### VS Code Extension

```bash
make ext-install    # npm ci
make ext-build      # npx tsc -p ./
# F5 to launch Extension Development Host
```

### Cursor MCP

```bash
uv sync             # Install Python deps
# .cursor/mcp.json already configured
# Restart Cursor to pick up server
```

### MCP in VS Code (Optional)

`.vscode/mcp.json` registers `rlmGateway` in stdio mode. Can also add to user settings.

## Reference Docs

- Setup playbooks: `docs/integration/playbooks.md`
- IDE adapter mapping: `docs/integration/ide_adapter.md`
- IDE matrix: `docs/integration/ide_matrix.md`
- IDE touchpoints: `docs/integration/ide_touchpoints.md`
- Extension architecture: `docs/adr/001-extension-architecture.md`
