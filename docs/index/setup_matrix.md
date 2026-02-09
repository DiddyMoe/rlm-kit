# Setup matrix

Baseline environment and packaging for the RLM fork.

## Python

- **Version**: 3.11 (see `pyproject.toml` requires-python and `.python-version`).
- **Tool**: [uv](https://astral.sh/uv) for install/sync; lockfile: `uv.lock`.

## Packaging

- **Lockfile**: `uv.lock` at repo root.
- **Install**: `uv sync` (base); `uv sync --group dev --group test` for dev/test.
- **Editable**: `uv pip install -e .` or equivalent via uv sync.

## Optional extras

| Extra    | Purpose              | deps (from pyproject)      |
|----------|----------------------|----------------------------|
| `modal`  | Modal sandbox        | modal>=0.73.0, dill>=0.3.7 |
| `daytona`| Daytona sandbox      | daytona>=0.128.1, dill>=0.3.7 |
| `prime`  | Prime sandboxes      | prime-sandboxes>=0.2.0, dill>=0.3.7 |

## MCP gateway dependencies

The MCP gateway (`rlm/mcp_gateway/server.py`, entry `scripts/rlm_mcp_gateway.py`) requires:

- **`mcp`** — MCP SDK (Server, stdio_server, Tool, TextContent). Not listed in `pyproject.toml`. If missing, the gateway prints "MCP SDK not installed. Install with: pip install mcp" and exits.
- **HTTP mode only**: `fastapi`, `uvicorn` — for `--mode http`. Not in pyproject; gateway imports optionally and exits with install instructions if missing.

**Recommendation**: Add an optional extra (e.g. `[mcp]`) in `pyproject.toml` listing `mcp`, and for HTTP mode `fastapi` and `uvicorn`, so gateway deps are explicit. Phase 3 may implement this only if approved (dependency change = approval required).

## Setup variants

- **Local dev**: `uv sync --group dev --group test`, then `make check` (lint, format, test).
- **CI**: See `.github/workflows/test.yml` — Python 3.11/3.12 matrix, uv, pytest with exclusions (e.g. test_modal_repl, tests/clients).
- **Extension**: See `vscode-extension/` and Makefile `ext-*` targets; Node 20, npm ci, tsc, eslint.
