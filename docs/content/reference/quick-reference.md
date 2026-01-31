# Quick reference

Commands, config snippets, MCP tools, and verification for the RLM MCP Gateway.

---

## Commands

### Deploy remote gateway

**Direct Python:**

```bash
python scripts/rlm_mcp_gateway.py \
  --mode http \
  --host 0.0.0.0 \
  --port 8080 \
  --repo-path /repo/rlm-kit \
  --api-key your-secret-api-key
```

**Deployment script:**

```bash
export RLM_GATEWAY_API_KEY=your-secret-api-key
export REPO_PATH=/repo/rlm-kit
bash scripts/deploy_gateway.sh
```

**Docker (recommended for production):**

```bash
docker build -t rlm-gateway -f Dockerfile.gateway .
docker run -d \
  --name rlm-gateway \
  -p 8080:8080 \
  -v /path/to/repo:/repo/rlm-kit:ro \
  -e RLM_GATEWAY_API_KEY=your-secret-api-key \
  rlm-gateway
```

**Deploy script:** `scripts/deploy_gateway.sh` (with `REPO_PATH`, `RLM_GATEWAY_API_KEY`) or `scripts/install_deploy_gateway.py` — standard deploy path for the RLM MCP Gateway. Railway or other platforms can use the same Docker image.

### Thin workspace

```bash
python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin
```

### Local (stdio) mode

```bash
python scripts/rlm_mcp_gateway.py --mode stdio
```

---

## Configuration

### Remote gateway (Cursor `.cursor/mcp.json`)

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

### Environment variables

```bash
export RLM_GATEWAY_API_KEY=your-secret-api-key   # Required for HTTP mode; do not commit to repo
export REPO_PATH=/repo/rlm-kit
export GATEWAY_HOST=0.0.0.0
export GATEWAY_PORT=8080
```

**Auth (remote gateway):** API key is required for HTTP mode. Set `RLM_GATEWAY_API_KEY` in the environment on the IDE host; use HTTPS and rotate keys periodically. See [Remote isolation](../guides/remote-isolation.md#authentication).

---

## MCP tools

| Category | Tool | Purpose |
|----------|------|---------|
| Session | `rlm.session.create` | Create session |
| Session | `rlm.session.close` | Close session |
| Session | `rlm.roots.set` | Set allowed roots |
| Filesystem | `rlm.fs.list` | List directory (metadata only) |
| Filesystem | `rlm.fs.manifest` | Get file manifest |
| Filesystem | `rlm.fs.handle.create` | Create file handle |
| Reading | `rlm.span.read` | Read bounded span (max 200 lines / 8KB) |
| Reading | `rlm.chunk.create` | Create chunks |
| Reading | `rlm.chunk.get` | Get chunk |
| Search | `rlm.search.query` | Semantic search (references only) |
| Search | `rlm.search.regex` | Regex search (references only) |
| Execution | `rlm.exec.run` | Execute code in sandbox |
| Execution | `rlm.complete` | RLM orchestration (plan). Optional `response_format: "structured"` returns `structured_answer` with `summary`, `citations`, `confidence`. |
| Provenance | `rlm.provenance.report` | Get audit trail |

### Tool selection

- **rlm.span.read** — Bounded line ranges (e.g. lines 1–200 of a file). Use when you know the file and range.
- **rlm.chunk.get** — Pre-created chunks by ID. Use after `rlm.chunk.create` when you need repeated access by chunk.
- **rlm.search.query** — Semantic search; returns references (path, line range) only. Use to find relevant spots, then `span.read` or `chunk.get` for content.
- **rlm.fs.list** — Metadata only (names, types); no file content. Set roots first with `rlm.roots.set`.

See [repl-format](repl-format.md) for FINAL / FINAL_VAR format (how RLM extracts the final answer; balanced-paren parsing).

---

## Limits and budgets

Exceeding these returns an error with a clear message (e.g. "Tool call budget exceeded").

| Limit | Value | Applies to |
|-------|--------|------------|
| MAX_SPAN_LINES / MAX_SPAN_BYTES | 200 lines / 8KB | `rlm.span.read`, `rlm.chunk.get` |
| MAX_CHUNK_* | 200 lines / 8KB | Chunk creation and retrieval |
| MAX_FS_LIST_ITEMS | 1000 | `rlm.fs.list` |
| MAX_SEARCH_RESULTS | 10 | `rlm.search.query`, `rlm.search.regex` |
| MAX_EXEC_CODE_SIZE / TIMEOUT_MS / MEMORY_MB | 10KB / 5s / 256MB | `rlm.exec.run` |
| MAX_SESSION_OUTPUT_BYTES | 10MB | Per-session output budget |
| Per-session | max_tool_calls (default 100), timeout_ms (default 300000) | Session config |

**Sub-call prompt bound:** Sub-LM calls (REPL `llm_query`, AgentRLM, RLM iterations) should keep prompts under **MAX_SUB_CALL_PROMPT_CHARS** (100k chars, ~25k tokens). Exceeding this logs a warning and may cause ContextWindowExceededError (upstream #42).

---

## Cost awareness

Many `rlm.span.read`, `rlm.exec.run`, or `rlm.complete` calls can increase LM and compute cost. Use per-session budgets (max_tool_calls, max_output_bytes) and bounded spans to control cost. The RLM library exposes usage via `cost_calculator` and `get_usage_summary()` on clients; `rlm.complete` returns a `usage` object. See examples and [Limits and budgets](#limits-and-budgets).

---

## Compliance / audit

**Provenance export:** Call `rlm.provenance.report(session_id, export_json=true)` to get an `export_payload` field containing a JSON string of the full provenance graph. Write this to a file for SIEM or compliance (e.g. `echo $export_payload > audit-session-<id>.json`). All tool calls are logged in the session; the report includes spans, file access stats, and tool call counts.

---

## Verification

### Health check

```bash
curl https://gateway-host:8080/health
# Expected: {"status": "ok", "service": "rlm-mcp-gateway"}
```

### IDE connection

1. Open IDE chat (Copilot / Cursor).
2. Ask: “What RLM tools are available?”
3. You should see `rlm.session.create`, `rlm.fs.list`, etc.

### Smoke test (gateway tools)

From repo root, run: `uv run python scripts/test_mcp_gateway.py --smoke`. This runs session.create → roots.set → fs.list → handle.create → span.read and asserts success. Use to confirm the gateway and tools work before relying on the IDE agent.

### Thin workspace

```bash
ls ~/rlm-kit-thin/
# Should NOT see: rlm/, scripts/, examples/, tests/
# Should see: .cursor/, .vscode/, README.md, docs/
```

---

## Troubleshooting

| Issue | Checks |
|-------|--------|
| Gateway not starting | Dependencies (`pip install fastapi uvicorn`), port free, logs. |
| Authentication errors | `echo $RLM_GATEWAY_API_KEY`; test with `curl -H "Authorization: Bearer $RLM_GATEWAY_API_KEY" https://gateway-host:8080/health`. |
| IDE not connecting | MCP config, env var, restart IDE, IDE logs. |
