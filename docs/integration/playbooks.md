# IDE playbooks

Step-by-step usage from VS Code Agent Chat and Cursor Agent Chat. Single doc, two sections (proposal #8 recommendation A).

---

## Use from VS Code Agent Chat

### Prerequisites

- Python 3.11+, [uv](https://astral.sh/uv)
- VS Code 1.99+ (see `vscode-extension/package.json` engines)
- Either: GitHub Copilot subscription (built-in LM) **or** an LLM API key

### Setup

1. Clone repo and install: `uv sync` (or `uv pip install -e .`).
2. Open repo in VS Code. Install extension dependencies: `make ext-install` then `make ext-build` (or from `vscode-extension/`: `npm ci` and `npx tsc -p ./`).
3. (Optional) Run Extension Development Host (F5) to load the extension in a new window, or install the built VSIX in your main VS Code.

### Using the Chat Participant

1. Open Chat (e.g. Copilot Chat or Agent Chat).
2. Invoke the RLM participant: type `@rlm` and your question. The participant id is `rlm-chat.rlm`, display name `rlm`.
3. **Built-in mode (Copilot)**: No API key. Extension uses `vscode.lm`; ensure Copilot is signed in and subscription active.
4. **API key mode**: In Settings, set `rlm.llmProvider` to `"api_key"`, set `rlm.backend` (e.g. `openai`, `anthropic`) and `rlm.model`. Run command **RLM: Set API Key** and store your key in SecretStorage. Then chat as above.

### Config reference

- Settings under `rlm.*`: provider, backend, model, baseUrl, subBackend, subModel, maxIterations, maxOutputChars, pythonPath, showIterationDetails, tracingEnabled, logLevel, logMaxSizeMB.
- In API-key mode, extension backend aliases `openrouter`, `vercel`, and `vllm` to `litellm` automatically, prefixing the model as `<provider>/<model>` for LiteLLM routing.
- Trace log: default `logs/trace.jsonl` in workspace; configurable; redaction and rolling in extension logger.
- Backend: Extension spawns `python -u rlm_backend.py` from repo root (parent of `vscode-extension/`); stdio JSON-over-newline.

### Optional: MCP in VS Code

This repo includes a workspace MCP config at `.vscode/mcp.json` that registers `rlmGateway` in stdio mode. If needed, you can also add the same server in user configuration. See [ide_matrix.md](ide_matrix.md) and [ide_touchpoints.md](ide_touchpoints.md).

One-click install URL:

- `vscode:mcp/install?%7B%22name%22%3A%22rlmGateway%22%2C%22type%22%3A%22stdio%22%2C%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22python%22%2C%22scripts%2Frlm_mcp_gateway.py%22%5D%2C%22cwd%22%3A%22%24%7BworkspaceFolder%7D%22%2C%22env%22%3A%7B%22PYTHONPATH%22%3A%22%24%7BworkspaceFolder%7D%22%7D%7D`
- `vscode:mcp/install?%7B%22name%22%3A%22rlmGateway%22%2C%22type%22%3A%22stdio%22%2C%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22--extra%22%2C%22mcp%22%2C%22python%22%2C%22scripts%2Frlm_mcp_gateway.py%22%5D%2C%22cwd%22%3A%22%24%7BworkspaceFolder%7D%22%2C%22env%22%3A%7B%22PYTHONPATH%22%3A%22%24%7BworkspaceFolder%7D%22%7D%7D`

For contributors, `.vscode/mcp.json` includes MCP dev mode with watch (`rlm/mcp_gateway/**/*.py`) and Python debug launch settings.

---

## Use from Cursor Agent Chat

### Prerequisites

- Python 3.11+, [uv](https://astral.sh/uv)
- Cursor (MCP-supported version)
- For **Cursor-as-outer-loop**: no RLM API key (Cursor’s LLM drives the agent; RLM tools are called by the agent).
- For **RLM completion** (`rlm_complete`): set provider API key (e.g. `OPENAI_API_KEY`) in env or Cursor config.

### Setup

1. Clone repo and install: `uv sync` (or `uv pip install -e .`).
2. MCP config: `.cursor/mcp.json` in the workspace. Example:

```json
{
  "mcpServers": {
    "rlm-gateway": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "python", "scripts/rlm_mcp_gateway.py"],
      "cwd": "${workspaceFolder}",
      "env": { "PYTHONPATH": "${workspaceFolder}" }
    }
  }
}
```

3. Restart Cursor or reload MCP so it picks up the server.

### Using RLM in Cursor Agent

1. Open Agent Chat (or Plan/Ask/Debug). Cursor discovers tools from the RLM MCP server.
2. **Primary (zero keys)**: Ask the agent to use the workspace; it can call `rlm_fs_list`, `rlm_search_query`, `rlm_span_read`, etc. Cursor’s LLM decides when to call `rlm_complete`; if it does, you must provide an API key (see below).
3. **Full RLM completion**: To run the full RLM recursive loop from Cursor, the agent (or you) invokes the `rlm_complete` tool with `session_id` and `task`. Set `OPENAI_API_KEY` (or the provider you use) in the environment Cursor uses to run the MCP server (e.g. in `env` in `mcp.json`, or in Cursor’s env).

### MCP tool list (contract)

- Session: `rlm_session_create`, `rlm_session_close`, `rlm_roots_set`
- Filesystem: `rlm_fs_list`, `rlm_fs_manifest`, `rlm_fs_handle_create`
- Spans/chunks: `rlm_span_read`, `rlm_chunk_create`, `rlm_chunk_get`
- Search: `rlm_search_query`, `rlm_search_regex`
- Execution: `rlm_exec_run`
- Completion: `rlm_complete`
- Provenance: `rlm_provenance_report`

Search tools accept optional `include_patterns` for multi-language retrieval. If omitted, search defaults to `*.py`.
Examples:
- `include_patterns: ["*.py", "*.ts", "*.tsx", "*.md"]`
- `include_patterns: ["**/*.py", "**/*.md"]`

See [ide_touchpoints.md](ide_touchpoints.md) for registration and config details.

### Server mode

- **Stdio (default)**: Local; `command` + `args` as above. No extra ports.
- **HTTP (optional)**: For remote isolation, run `python scripts/rlm_mcp_gateway.py --mode http --repo-path <path> --api-key <key>` (or `RLM_GATEWAY_API_KEY`). Requires FastAPI/uvicorn; add to `[mcp]` extra if used. See [setup_matrix.md](../index/setup_matrix.md).

---

## Cross-IDE summary

| IDE     | Entry point        | LLM source              | Config file(s)              |
|---------|--------------------|--------------------------|-----------------------------|
| VS Code | Chat `@rlm`        | Copilot or API key       | settings.json (rlm.*)       |
| Cursor  | MCP tools          | Cursor LLM + optional key| .cursor/mcp.json            |

Both: repo root = workspace (or parent of `vscode-extension/` for backend spawn). No trajectory schema or public API changes without approval.
