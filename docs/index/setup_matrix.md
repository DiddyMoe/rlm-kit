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
| `mcp`    | MCP gateway (stdio)  | mcp>=1.0.0                 |

## MCP gateway dependencies

The MCP gateway (`rlm/mcp_gateway/server.py`, entry `scripts/rlm_mcp_gateway.py`) requires:

- **Stdio mode**: Install with `uv pip install -e ".[mcp]"` (or `uv sync --extra mcp`). The `[mcp]` extra provides the `mcp` package.
- **HTTP mode** (`--mode http`): Additionally requires `fastapi` and `uvicorn`. Install with `uv pip install fastapi uvicorn` (or add to your environment). Not included in the `[mcp]` extra to keep the default install minimal.

## Setup variants

- **Local dev**: `uv sync --group dev --group test`, then `make check` (lint, format, test).
- **CI**: See `.github/workflows/test.yml` — Python 3.11/3.12 matrix, uv, pytest with exclusions (e.g. test_modal_repl, tests/clients).
- **Extension**: See `vscode-extension/` and Makefile `ext-*` targets; Node 20, npm ci, tsc, eslint.
