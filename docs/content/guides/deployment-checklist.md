# Production deployment checklist

Use this checklist when deploying the RLM MCP Gateway in production (remote HTTP mode). Aligned with upstream governance/production concerns (e.g. [alexzhang13/rlm#17](https://github.com/alexzhang13/rlm/issues/17)).

---

## Authentication

- [ ] API key required for HTTP mode; no anonymous access.
- [ ] Store API key in environment variable (`RLM_GATEWAY_API_KEY`) on the gateway host and IDE host; do not commit to repo.
- [ ] Use `Authorization: Bearer <key>` in MCP client config; document rotation in runbook.

---

## TLS

- [ ] Serve the gateway over HTTPS (reverse proxy with TLS termination, or gateway with TLS).
- [ ] Use valid certificates; avoid self-signed in production unless internal CA is trusted.

---

## Rate limits and budgets

- [ ] Per-session limits are enforced (max_tool_calls, max_output_bytes, timeout_ms); see [Limits and budgets](../reference/quick-reference.md#limits-and-budgets).
- [ ] Consider reverse-proxy or gateway-level rate limits (requests per IP / per API key) if needed.
- [ ] Document budget defaults and how to tune session config for your workload.

---

## Provenance and logging

- [ ] Provenance is recorded per session; use `rlm.provenance.report(session_id, export_json=true)` for audit export.
- [ ] Enable structured logging on the gateway (session create/close, tool invocations, errors); see [Logging](#logging) below.
- [ ] Retain logs per your compliance requirements; consider forwarding to SIEM.

---

## Logging

- [ ] Gateway uses structured logging (logger `rlm.mcp_gateway`): each tool call logs `tool` and `session_id`; errors log `tool_error` with tool, session_id, error. No full file content or prompt bodies are logged.
- [ ] Configure logging level (e.g. `logging.basicConfig(level=logging.INFO)`) and optional JSON/formatter for parsing and retention. See [Logging](https://docs.python.org/3/library/logging.html).

---

## Repository access

- [ ] Gateway has read-only access to the repo (e.g. read-only mount or clone).
- [ ] `--repo-path` (or `REPO_PATH`) points to the repo root on the gateway host; roots in tool calls are relative to that.

---

## Network and firewall

- [ ] Restrict gateway port to trusted networks (VPN, firewall, or SSH tunnel).
- [ ] IDE host can reach gateway over HTTPS; gateway does not need outbound access to IDE.

---

## Sandbox (rlm.exec.run)

- [ ] Exec runs in restricted environment: **network and process access denied** (socket, subprocess, os, sys, etc. blocked). Only safe builtins (e.g. `print`, `len`, `str`, `int`, `list`, `dict`, `range`, `min`, `max`); **no** `eval`, `exec`, `compile`, `open`, `__import__`, `globals`, `locals`.
- [ ] Time and memory limits are applied from gateway constants (MAX_EXEC_TIMEOUT_MS, MAX_EXEC_MEMORY_MB, MAX_EXEC_CODE_SIZE). See [Limits and budgets](../reference/quick-reference.md#limits-and-budgets).
- [ ] For full list of safe builtins and REPL vs strict split, see `rlm/core/sandbox/safe_builtins.py` and `rlm/core/sandbox/__init__.py` (REPL uses `get_safe_builtins_for_repl()`; MCP exec uses `get_safe_builtins()` only).

---

## Optional

- [ ] Thin workspace on IDE host: only config and docs; no source. See [Cursor thin workspace](cursor-thin-workspace.md) and [Remote isolation](remote-isolation.md).
- [ ] Monitor gateway health (`/health`); set up alerts on failure or high error rate.
