# Docker sandbox

Use Docker for stronger isolation when running code via the RLM MCP Gateway (e.g. `rlm.exec.run`).

---

## Current behavior

The gateway’s sandbox today is **AST-based**:

- Blocks dangerous builtins (e.g. `eval`, `exec`, `compile`).
- Restricts operations to reduce bypass risk.
- Runs in the same process as the gateway.

For higher assurance, you can run execution in a **Docker container** (when implemented).

---

## Docker sandbox (optional enhancement)

A possible implementation:

- Add a `--sandbox-mode docker` option to the gateway.
- For `rlm.exec.run`, run user code in a short-lived container with:
  - No network.
  - Read-only root filesystem.
  - Limited CPU/memory and timeout.
  - Ephemeral `/tmp` if needed.

The project already has `DockerREPL` in `rlm/environments/docker_repl.py` for RLM completions; the gateway could adopt a similar pattern for MCP execution.

---

## Recommendation

- **Default (AST-based):** Sufficient for most use cases; no Docker required.
- **Docker:** Use when you need stronger isolation (e.g. production or untrusted code).

When Docker sandbox is implemented, enable it via gateway config (e.g. `--sandbox-mode docker`) and ensure Docker is available on the gateway host.
