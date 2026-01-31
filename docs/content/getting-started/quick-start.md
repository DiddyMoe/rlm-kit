# Quick start

Get the RLM MCP Gateway running in three steps.

---

## 1. Update MCP configuration

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

**VS Code:** Add the same server under `mcp.servers` in `.vscode/settings.json` (see [IDE setup](guides/ide-setup.md)).

---

## 2. Restart IDE

Restart Cursor or VS Code so the new MCP server is loaded.

---

## 3. Test in chat

Open AI chat and ask:

```
What RLM tools are available?
```

You should see tools such as:

- `rlm.session.create`
- `rlm.fs.list`
- `rlm.span.read`
- `rlm.search.query`
- others listed in [Quick reference](reference/quick-reference.md)

---

## Example workflow

**User:** “Analyze the RLM core implementation”

**Agent (via MCP tools):**

1. `rlm.session.create()` → get `session_id`
2. `rlm.roots.set(session_id, roots=["rlm/core"])`
3. `rlm.fs.list(session_id, root="rlm/core")`
4. `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")`
5. `rlm.span.read(session_id, handle, start_line=1, end_line=200)`
6. Reason over the bounded context and respond

---

## What’s enforced

- **Bounded reading:** Max 200 lines / 8KB per span.
- **Handle-based access:** No raw file paths in content.
- **Root boundaries:** Path validation.
- **Provenance:** Audit trail.
- **Budgets:** Tool calls, bytes, timeouts.

---

## Next steps

- [IDE setup](../guides/ide-setup.md) — Full setup and tool usage.
- [Remote isolation](../guides/remote-isolation.md) — Production deployment with thin workspace.
- [Quick reference](../reference/quick-reference.md) — Commands and MCP tools.
