# Cursor thin workspace

Use Cursor with a **thin workspace**: **config and docs only, no full repo.** The thin workspace does **not** contain `rlm/`, `scripts/`, `examples/`, or `tests/`. **All codebase access goes through the RLM MCP Gateway** (session → roots → list → handle → span read, search, etc.). The repository lives on the gateway host; the IDE only has MCP config and documentation.

- **Create thin workspace:** `python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin` (see [Remote isolation](remote-isolation.md) for deploy steps).
- **Deploy gateway:** See [Remote isolation](remote-isolation.md) and [Quick reference](../reference/quick-reference.md) for Docker/Python/systemd.

---

## Prerequisites

- Remote gateway running and reachable over HTTPS.
- Cursor with Agent Chat and MCP enabled.

---

## Step 1: Create thin workspace

```bash
python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin --ide cursor
```

Or manually:

```bash
mkdir -p ~/rlm-kit-thin
cd ~/rlm-kit-thin
mkdir -p .cursor
cp /path/to/rlm-kit/.cursor/mcp.json .cursor/
cp /path/to/rlm-kit/.cursorrules .cursorrules
cp /path/to/rlm-kit/README.md README.md
cp -r /path/to/rlm-kit/docs docs/
# Do NOT copy: rlm/, scripts/, examples/, tests/
```

---

## Step 2: Configure MCP for remote gateway

Edit `~/rlm-kit-thin/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "rlm-gateway": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-gateway-host:8080/mcp",
        "-H", "Authorization: Bearer ${RLM_GATEWAY_API_KEY}",
        "-H", "Content-Type: application/json",
        "--data-binary", "@-"
      ],
      "env": {
        "RLM_GATEWAY_API_KEY": "${env:RLM_GATEWAY_API_KEY}"
      }
    }
  }
}
```

---

## Step 3: Cursor rules

Ensure `.cursorrules` in the thin workspace states:

- The repository is **not** in the workspace; all access must go through MCP tools.
- Use `rlm.session.create`, `rlm.roots.set`, `rlm.fs.list`, `rlm.fs.handle.create`, `rlm.span.read`, `rlm.search.query`, etc.
- Do not use direct file reads (`open()`, `read_file()`, etc.).
- Respect bounds (e.g. max 200 lines / 8KB per span).

---

## Step 4: Environment variable

```bash
export RLM_GATEWAY_API_KEY=your-secret-api-key
```

Or set it in `~/rlm-kit-thin/.env` if your setup loads it. Restart Cursor after changing env vars.

---

## Step 5: Open and verify

```bash
cursor ~/rlm-kit-thin
```

In Agent Chat:

1. “What RLM tools are available?” → should list RLM MCP tools.
2. “List the repository structure” → should use `rlm.session.create` → `rlm.roots.set` → `rlm.fs.list`.
3. “Read the first 100 lines of rlm/core/rlm.py” → should use `rlm.fs.handle.create` and `rlm.span.read` with bounded span.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Gateway not accessible | `curl https://gateway-host:8080/health`, firewall, API key. |
| 401 Unauthorized | `RLM_GATEWAY_API_KEY` set and matching gateway; Bearer format in MCP config. |
| Tool errors | Gateway logs, repo path on remote host, file permissions. |
| Agent reads files directly | `.cursorrules` and MCP config; confirm thin workspace has no source. |

---

## Local development (no thin workspace)

To use the gateway in the same repo (no remote isolation), run the gateway in stdio mode and point MCP at it (see [IDE setup](ide-setup.md)). The repo remains on disk; only the *contract* is MCP-only.
