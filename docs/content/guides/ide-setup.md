# IDE setup (Cursor & VS Code)

Configure Cursor or VS Code so AI agents use the RLM MCP Gateway and only access the repository through bounded MCP tools.

---

## One-click setup (local gateway)

From the repo root, run:

```bash
make ide-setup
```

This runs `make install-gateway` (installs MCP gateway deps: mcp, fastapi, uvicorn), then creates `.cursor/mcp.json` and `.vscode/settings.json` in the workspace with the local stdio gateway command. Restart the IDE and ask in chat: “What RLM tools are available?” For a thin workspace (remote gateway), use `uv run python scripts/install_ide_config.py --all --thin --output-dir ~/rlm-kit-thin` (then edit the gateway URL in the created config).

**Makefile alternatives:** Install gateway deps only: `make install-gateway`. Run the MCP server manually: `make mcp-server`. One-click without Make: `uv sync --extra gateway && uv run python scripts/install_ide_config.py --all`.

---

## Option 1: Local gateway (development)

### MCP configuration

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "rlm-gateway": {
      "command": "uv",
      "args": ["run", "python", "scripts/rlm_mcp_gateway.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  }
}
```

**VS Code** (`.vscode/settings.json`):

```json
{
  "mcp.servers": {
    "rlm-gateway": {
      "command": "uv",
      "args": ["run", "python", "scripts/rlm_mcp_gateway.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  }
}
```

Restart the IDE and verify in chat: “What RLM tools are available?” You should see `rlm.session.create`, `rlm.fs.list`, `rlm.span.read`, etc.

### VS Code + Copilot agent instructions

Add to `.vscode/settings.json`:

```json
{
  "github.copilot.advanced": {
    "agent": {
      "instructions": [
        "You cannot read the repository directly. Use MCP tools only.",
        "All repository access must go through rlm.* MCP tools.",
        "Use rlm.session.create to start, then rlm.fs.list, rlm.span.read, etc.",
        "Always respect bounded operations (max lines, max bytes)."
      ]
    }
  }
}
```

### Cursor rules

Ensure `.cursorrules` (or project rules) state that repository access must go through MCP tools: `rlm.session.create`, `rlm.fs.list`, `rlm.span.read`, `rlm.search.query`, etc., and that direct file reads are not allowed.

---

## Option 2: Remote gateway (production)

For true remote isolation, run the gateway on another host and use a thin workspace. See [Remote isolation](remote-isolation.md) and [Cursor thin workspace](cursor-thin-workspace.md) in this section.

Quick steps:

1. Deploy gateway (Docker/Python/systemd) on the remote host.
2. Create thin workspace: `python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin`.
3. Point MCP config at the gateway URL and set `RLM_GATEWAY_API_KEY`.
4. Open the thin workspace in the IDE.

---

## Tool usage

### Basic workflow

1. Create session: `rlm.session.create({ "max_tool_calls": 50, "timeout_ms": 300000 })`.
2. Set roots: `rlm.roots.set(session_id, roots=["rlm/core"])` (paths **relative to repo root**; see below).
3. List directory: `rlm.fs.list(session_id, root="rlm/core", depth=2)` (metadata only).
4. Create handle: `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")`.
5. Read span: `rlm.span.read(session_id, handle, start_line=1, end_line=200)` (max 200 lines / 8KB).
6. Provenance: `rlm.provenance.report(session_id)`.

### Roots and paths (local vs remote)

- **Local:** Repo root is the workspace folder. Roots and paths in tool calls are relative to that (e.g. `roots=["rlm/core"]`, `root="rlm/core"`).
- **Remote (thin workspace):** The repo lives on the **gateway host** at `--repo-path` (e.g. `/repo/rlm-kit` or `REPO_PATH`). Roots and all paths in tool calls are **relative to that repo root**. Example: `rlm.roots.set(session_id, roots=["rlm/core"])` allows access under `/repo/rlm-kit/rlm/core` on the gateway. Use `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")` — do not use absolute paths like `/repo/rlm-kit/...` in tool parameters.

### Search

Use `rlm.search.query` or `rlm.search.regex` for references only; then read bounded spans with `rlm.fs.handle.create` and `rlm.span.read` as needed.

---

## Other IDEs

If your editor supports MCP (e.g. other IDEs with an MCP client), use the same MCP server config shape: `command` + `args` for stdio (local) or curl/HTTP for remote. Tool list and semantics are in [Quick reference](../reference/quick-reference.md). No Cursor/VS Code–specific steps are required beyond the JSON config.

---

## Models (Cursor / Copilot)

MCP tools are intended for use with the **Agent** in Cursor Composer and with GitHub Copilot Chat. Tool execution may require user approval in the IDE. Not all models may invoke tools reliably; use a model that supports tool/function calling. Known limitations: tool choice behavior can vary by model; if the agent does not call RLM tools, check `.cursorrules` and MCP server connection.

---

## Security

**Enforced:** Bounded reading, root boundaries, handle-based access, metadata-only listing, search references only, sandbox limits, budgets, provenance.

**Blocked:** Full-file reads, path traversal outside roots, network/process from sandbox, unbounded operations.

---

## Troubleshooting

| Issue | Checks |
|-------|--------|
| MCP server not loading | Valid JSON in MCP config; `make install-gateway` (or `uv run python --version`); restart IDE; IDE logs. |
| Tools not available | MCP server running; run `make mcp-server` or ensure `scripts/rlm_mcp_gateway.py` exists; PYTHONPATH includes workspace. |
| Permission errors | Set roots with `rlm.roots.set`; use paths relative to repo root. |
| Budget exceeded | New session with larger budgets or narrower scope. |
