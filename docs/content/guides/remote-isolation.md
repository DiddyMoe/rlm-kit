# Remote isolation

Run the RLM MCP Gateway on a separate host so IDE AI agents **cannot** read the repository directly. All access goes through the gateway over HTTP/TLS.

---

## Architecture

```
IDE (Thin Workspace) → HTTP/TLS → Remote Gateway → Repository
```

The **thin workspace** has no source code — only config and docs (e.g. `.cursor/`, `.vscode/`, `README.md`, `docs/`). It does **not** contain `rlm/`, `scripts/`, `examples/`, or `tests/`. All codebase access goes through MCP; the repo lives on the gateway host. See [Cursor thin workspace](cursor-thin-workspace.md) and `scripts/setup_thin_workspace.py` for creating the thin workspace.

**Roots and paths in remote mode:** The repository root on the gateway host is set by `--repo-path` (e.g. `/repo/rlm-kit`). All roots and paths in MCP tool calls are **relative to that repo root**. Example: `rlm.roots.set(session_id, roots=["rlm/core"])` restricts access to the `rlm/core` directory under the repo; `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")` and `rlm.fs.list(session_id, root="rlm/core")` use the same relative paths. Do not pass absolute host paths (e.g. `/repo/rlm-kit/...`) in tool parameters.

---

## Prerequisites

- **Remote host:** Python 3.11+, repo cloned/mounted, reachable from the IDE host.
- **IDE host:** Cursor or VS Code, network access to the gateway.

---

## Step 1: Deploy remote gateway

### Docker (recommended)

```bash
docker build -t rlm-gateway -f Dockerfile.gateway .
docker run -d \
  --name rlm-gateway \
  -p 8080:8080 \
  -v /path/to/repo:/repo/rlm-kit:ro \
  -e RLM_GATEWAY_API_KEY=your-secret-api-key \
  rlm-gateway \
  python scripts/rlm_mcp_gateway.py \
    --mode http \
    --host 0.0.0.0 \
    --port 8080 \
    --repo-path /repo/rlm-kit \
    --api-key your-secret-api-key
```

### Direct Python

```bash
uv pip install -e ".[gateway]"
export RLM_GATEWAY_API_KEY=your-secret-api-key
python scripts/rlm_mcp_gateway.py \
  --mode http \
  --host 0.0.0.0 \
  --port 8080 \
  --repo-path /path/to/repo/rlm-kit \
  --api-key your-secret-api-key
```

### Systemd

Create `/etc/systemd/system/rlm-gateway.service` with `ExecStart` pointing at the same `rlm_mcp_gateway.py` command, then:

```bash
sudo systemctl enable rlm-gateway
sudo systemctl start rlm-gateway
```

---

## Step 2: Create thin workspace

On the **IDE host**:

```bash
python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin
```

The thin workspace contains config and docs only — no `rlm/`, `scripts/`, `examples/`, or `tests/`.

---

## Step 3: Configure IDE

Edit `~/rlm-kit-thin/.cursor/mcp.json` (Cursor) or `~/rlm-kit-thin/.vscode/settings.json` (VS Code) so the MCP server uses the gateway URL and `RLM_GATEWAY_API_KEY`. Examples are in [Cursor thin workspace](cursor-thin-workspace.md) and [Quick reference](../reference/quick-reference.md).

Set the API key:

```bash
export RLM_GATEWAY_API_KEY=your-secret-api-key
```

Open the thin workspace:

```bash
cursor ~/rlm-kit-thin   # or: code ~/rlm-kit-thin
```

---

## Step 4: Verify

1. **Health:** `curl https://your-gateway-host:8080/health` → `{"status": "ok", "service": "rlm-mcp-gateway"}`.
2. **Chat:** Ask “What RLM tools are available?” — you should see `rlm.session.create`, `rlm.fs.list`, etc.
3. **Repo access:** Ask to list the repository structure; the agent should use MCP tools only, not direct file reads.

---

## Authentication

- **API key required:** HTTP mode requires an API key. Pass it via the `Authorization: Bearer <key>` header; the gateway validates it on each request.
- **Environment variable:** Set `RLM_GATEWAY_API_KEY` on the IDE host (e.g. `export RLM_GATEWAY_API_KEY=your-secret-api-key`). Do **not** store the key in config files committed to the repo.
- **Rotation:** Rotate the key periodically; update the env var and gateway `--api-key` (or env) together. Document rotation in your runbook.
- **Gateway side:** Start the gateway with `--api-key <key>` or `RLM_GATEWAY_API_KEY`; the same key must be used by the IDE client.

## Security

- Use API keys in environment variables; use HTTPS/TLS.
- Restrict gateway access (firewall, VPN, or SSH tunnel).
- Give the gateway read-only access to the repo (e.g. read-only mount).
- Rotate keys and monitor logs.

---

## One gateway, many IDE clients

To have one gateway process serve many IDE clients over the network, use stdio-to-SSE wrappers (e.g. [mcp-server-server](https://github.com/modelcontextprotocol/servers)) to expose the stdio gateway over HTTP/SSE, or run the gateway in `--mode http` and point multiple IDE hosts at it (with auth and rate limits).

---

## Local development (no remote isolation)

For local use only:

```bash
python scripts/rlm_mcp_gateway.py --mode stdio
```

Configure MCP to run this command in the workspace. The IDE can still read the repo directly; remote isolation does not apply.
