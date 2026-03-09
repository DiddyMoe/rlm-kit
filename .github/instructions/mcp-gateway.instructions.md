# MCP Gateway

The MCP gateway (`rlm/mcp_gateway/`) exposes RLM tools for IDE integration. Entry point: `scripts/rlm_mcp_gateway.py`.

## Tool List

| Tool | Purpose |
|------|---------|
| `rlm.session.create` | Start a new RLM session |
| `rlm.session.close` | Close current session |
| `rlm.roots.set` | Set allowed filesystem roots |
| `rlm.fs.list` | List files in workspace |
| `rlm.fs.manifest` | Get file manifest |
| `rlm.fs.handle.create` | Create handle for file content |
| `rlm.span.read` | Read span from handle |
| `rlm.chunk.create` | Create chunk |
| `rlm.chunk.get` | Get chunk by ID |
| `rlm.search.query` | Semantic search |
| `rlm.search.regex` | Regex search |
| `rlm.exec.run` | Execute Python code (sandboxed) |
| `rlm.complete` | Full RLM completion (recursive) |
| `rlm.provenance.report` | Report provenance |

Tool names use dot notation as MCP names (e.g., `rlm.fs.list`). Internally, `server.py` maps these to underscore handler names (e.g., `rlm_fs_list`) via `_TOOL_NAME_ALIASES`. Both forms are accepted.

## Server Modes

- **Stdio (default)**: Local; `uv run python scripts/rlm_mcp_gateway.py`
- **HTTP (optional)**: Remote; `--mode http --repo-path <path> --api-key <key>`

## Configuration

### VS Code (`~/.vscode/mcp.json` or workspace `.vscode/mcp.json`)

```json
{
  "servers": {
    "rlmGateway": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--extra", "mcp", "python", "scripts/rlm_mcp_gateway.py"],
      "cwd": "${workspaceFolder}",
      "env": { "PYTHONPATH": "${workspaceFolder}" }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "rlm-gateway": {
      "command": "uv",
      "args": ["run", "python", "scripts/rlm_mcp_gateway.py"],
      "cwd": "${workspaceFolder}",
      "env": { "PYTHONPATH": "${workspaceFolder}" }
    }
  }
}
```

## Security

- **PathValidator**: Blocks traversal and restricted patterns (`.git`, `__pycache__`, `.venv`, `node_modules`, `.env`, `secrets`, `credentials`)
- **Sandboxed execution**: `rlm_exec_run` uses strict `get_safe_builtins()` — blocks `__import__`, `open`, `eval`, `exec`
- **AST validation**: `rlm/core/sandbox/ast_validator.py` blocks dangerous modules (`os`, `subprocess`, `socket`)
- **Resource limits**: See numeric constants below
- **API key auth**: `RLM_GATEWAY_API_KEY` env var for HTTP mode (simple string match)
- **OAuth auth**: Optional RFC 7662 token introspection via `GatewayAuth` in `auth.py` — introspects tokens via HTTP POST, caches validated tokens with TTL from `exp` claim, supports well-known endpoint discovery

## Numeric Constants

All defined in `rlm/mcp_gateway/constants.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_SPAN_LINES` | 200 | Max lines per span read |
| `MAX_SPAN_BYTES` | 8192 | Max bytes per span read |
| `MAX_CHUNK_LINES` | 200 | Max lines per chunk |
| `MAX_CHUNK_BYTES` | 8192 | Max bytes per chunk |
| `MAX_FS_LIST_ITEMS` | 1000 | Max items in file listing |
| `MAX_SEARCH_RESULTS` | 10 | Max search results returned |
| `MAX_EXEC_CODE_SIZE` | 10240 | Max code size for exec (10KB) |
| `MAX_EXEC_TIMEOUT_MS` | 5000 | Max exec timeout (5s) |
| `MAX_EXEC_MEMORY_MB` | 256 | Max exec memory |
| `MAX_SESSION_OUTPUT_BYTES` | 10485760 | Max session output (10MB) |
| `MAX_SUB_CALL_PROMPT_CHARS` | 100000 | Max prompt chars for sub-LM calls |

## Internal Components

### HandleManager (`handles.py`)

Manages file handles and chunk IDs with bounded LRU cache:
- `max_handles=1000` with FIFO eviction (removes oldest 50% when full)
- `create_file_handle()` / `get_file_handle()` / `list_file_handle_ids()`
- `create_chunk_id()` with metadata (chunk_index, start/end line, strategy)

### FileMetadataCache (`tools/file_cache.py`)

LRU cache with TTL for file metadata:
- Default TTL: 60s, max entries: 1000
- Caches: size, hash, line count, mtime
- Detects file modifications via mtime comparison

### SearchScorer (`tools/search_scorer.py`)

Term frequency-based relevance scoring with phrase boost and start-word boost for search results ranking.

### SessionManager (`session.py`)

- `SessionConfig`: `max_depth`, `max_iterations`, `max_tool_calls`, `timeout_ms=300000`, `max_output_bytes`
- Session tracks: tool_call_count, output_bytes, provenance list, accessed spans (deduplication)
- **Cancellation**: `cancel_session()`, `cancel_by_request_id()` via request ID → session mapping
- `check_budget()`: checks cancellation, tool call count, output bytes, timeout
- Automatic cleanup of expired sessions (60s interval)

## Search Tool Patterns

`rlm_search_query` and `rlm_search_regex` accept optional `include_patterns` for multi-language retrieval:
- Default: `*.py` when omitted
- Multi-language: `["*.py", "*.ts", "*.tsx", "*.md"]`

## Gateway Module Structure

| File | Purpose |
|------|---------|
| `server.py` | MCP server dispatch, tool/resource/prompt registration |
| `session.py` | Session lifecycle management |
| `validation.py` | Path validation (PathValidator) |
| `handles.py` | File handle management |
| `provenance.py` | Snippet provenance tracking |
| `auth.py` | Authentication (API key, OAuth) |
| `constants.py` | Gateway-specific constants |
| `tools/` | Tool implementations (session, fs, span, chunk, search, exec, complete, provenance) |
| `tools/helpers.py` | Shared helpers (`load_canary_token`) |
| `tools/file_cache.py` | `FileMetadataCache` (LRU+TTL) |
| `tools/search_scorer.py` | `SearchScorer` (TF scoring) |

## Dependencies

MCP support is an optional extra: `uv pip install -e ".[mcp]"` or `uv sync --extra mcp`. The `mcp` package is imported via try/except with `mcp_available` flag.
