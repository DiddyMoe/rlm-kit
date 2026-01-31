# Installation

This guide covers installing the RLM library and, optionally, deploying the RLM MCP Gateway with remote isolation.

---

## Library installation

### With uv (recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init && uv venv --python 3.12
source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
uv pip install -e .
```

### Optional extras

```bash
# Modal sandbox support
make install-modal
modal setup

# Prime sandbox support (beta)
uv sync --extra prime
export PRIME_API_KEY=...
```

### Verify

```bash
make install        # install base deps
make check          # lint, format, tests
make quickstart     # run a quick RLM query (needs OPENAI_API_KEY)
```

### IDE setup (MCP gateway)

```bash
make install-gateway   # install MCP gateway deps (mcp, fastapi, uvicorn)
make ide-setup        # one-click: gateway deps + .cursor/mcp.json and .vscode/settings.json
```

See [IDE setup](../guides/ide-setup.md) for full instructions. To run the MCP server manually: `make mcp-server`.

### Windows

The gateway and scripts are developed on Linux/macOS. On **Windows**, use WSL or Docker for the MCP gateway and `uv`; native Windows may work for library use but is not regularly tested. If you hit path or script issues, run the gateway in WSL or in a container. See [RLM upstream #51](https://github.com/alexzhang13/rlm/issues/51) for compatibility notes.

---

## MCP Gateway installation (remote isolation)

For production use, deploy the gateway on a separate host and use a thin workspace on the IDE host.

### 1. Deploy remote gateway

**Docker (recommended):**

```bash
python scripts/install_deploy_gateway.py \
  --mode docker \
  --repo-path /repo/rlm-kit \
  --host 0.0.0.0 \
  --port 8080
```

**Systemd:**

```bash
sudo python scripts/install_deploy_gateway.py \
  --mode systemd \
  --repo-path /opt/rlm-kit \
  --host 0.0.0.0 \
  --port 8080
```

**Direct (testing):**

```bash
python scripts/install_deploy_gateway.py \
  --mode direct \
  --repo-path /path/to/repo \
  --host 0.0.0.0 \
  --port 8080
```

Save the API key for the next steps.

### 2. Create thin workspace

On the **IDE host** (not the gateway):

```bash
python scripts/install_thin_workspace.py \
  --output-dir ~/rlm-kit-thin \
  --gateway-url https://your-gateway-host:8080 \
  --api-key YOUR_API_KEY \
  --ide both
```

This creates a workspace with config and docs only — no `rlm/`, `scripts/`, `examples/`, or `tests/`.

### 3. Configure IDE

```bash
python scripts/install_ide_config.py \
  --gateway-url https://your-gateway-host:8080 \
  --api-key YOUR_API_KEY \
  --ide both \
  --set-env
```

For manual config, see [Remote isolation](../guides/remote-isolation.md) and the example files in `.cursor/` and `.vscode/`.

### 4. Optional: monitoring

```bash
python scripts/install_monitoring.py \
  --gateway-url https://your-gateway-host:8080 \
  --api-key YOUR_API_KEY \
  --watch-dir ~/rlm-kit-thin \
  --mode both
```

---

## Verification

### Gateway health

```bash
curl https://your-gateway-host:8080/health
# Expected: {"status": "ok", "service": "rlm-mcp-gateway"}
```

### IDE connection

1. Open the thin workspace in Cursor or VS Code.
2. Open AI chat and ask: “What RLM tools are available?”
3. You should see tools such as `rlm.session.create`, `rlm.fs.list`, `rlm.span.read`.

### Repository access

In chat, ask to list the repository structure. The agent should use MCP tools (`rlm.session.create`, `rlm.roots.set`, `rlm.fs.list`) and **not** read files directly.

---

## Scripts reference

| Script | Purpose | Key options |
|--------|---------|-------------|
| `install_deploy_gateway.py` | Deploy gateway | `--mode`, `--repo-path`, `--api-key` |
| `install_thin_workspace.py` | Create thin workspace | `--output-dir`, `--gateway-url`, `--api-key` |
| `install_ide_config.py` | Configure IDE | `--gateway-url`, `--api-key`, `--ide` |
| `install_monitoring.py` | Monitor bypass attempts | `--gateway-url`, `--watch-dir`, `--mode` |

---

## Security

- Store API keys in environment variables, not in config files.
- Use HTTPS/TLS for the gateway; restrict access with firewall or VPN.
- Give the gateway read-only access to the repository (e.g. read-only mount).
- Rotate keys periodically and enable monitoring in production.
