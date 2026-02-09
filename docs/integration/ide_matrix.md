# IDE support matrix

Supported IDE targets and where configuration lives.

## VS Code

- **Minimum version**: 1.99+ (extension `engines.vscode` in `vscode-extension/package.json`).
- **Surface**: Chat Participant `@rlm` (id `rlm-chat.rlm`); recursive reasoning over long context via RLM REPL.
- **LLM access**:
  - **Built-in**: Uses VS Code Language Model API (`vscode.lm`) — requires Copilot subscription; no API keys in extension.
  - **API key**: User sets `rlm.llmProvider` to `"api_key"`, configures `rlm.backend` / `rlm.model`, and uses command "RLM: Set API Key" (SecretStorage).
- **Config location**: Workspace or user `settings.json` under `rlm.*`; extension contributes these in `package.json`.
- **MCP (optional)**: `.vscode/settings.json` can define `mcp.servers` (e.g. `rlm-gateway`) for consistency with Cursor; same schema as Cursor where applicable.

## Cursor

- **Surface**: MCP only. Cursor does not expose the VS Code Chat API or `vscode.lm`, so the Chat Participant is not registered (extension detects and skips).
- **Integration**: Cursor agent calls RLM MCP tools directly. Primary mode: Cursor-as-outer-loop (zero keys); alternate: user sets API key and uses `rlm.complete` MCP tool.
- **Config location**: `.cursor/mcp.json` — defines MCP servers, e.g. `rlm-gateway` with `command`, `args`, `cwd`, `env` (e.g. `uv run python scripts/rlm_mcp_gateway.py` with `PYTHONPATH`).
- **Server mode**: Stdio (default, local); HTTP (optional, for remote isolation, requires `--repo-path` and `--api-key` or `RLM_GATEWAY_API_KEY`).

## Summary

| IDE     | Chat Participant | MCP        | Config / entry              |
|---------|------------------|------------|-----------------------------|
| VS Code | Yes (@rlm)       | Optional   | settings.json, package.json |
| Cursor  | No               | Yes (primary) | .cursor/mcp.json         |
