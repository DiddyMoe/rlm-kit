# IDE adapter

Single reference mapping VS Code and Cursor to the same tool/contract table and config matrix. See also [ide_matrix.md](ide_matrix.md), [ide_touchpoints.md](ide_touchpoints.md), [playbooks.md](playbooks.md).

## Tool and contract table

| Contract / surface   | VS Code                    | Cursor                     |
|---------------------|----------------------------|----------------------------|
| **Primary entry**   | Chat Participant `@rlm`    | MCP tools (rlm-gateway)    |
| **Config file**     | `settings.json` (`rlm.*`)  | `.cursor/mcp.json`         |
| **MCP server**      | Optional (`mcp.servers`)   | Required (`mcpServers.rlm-gateway`) |
| **LLM source**     | `vscode.lm` or API key     | Cursor LLM or env API key for `rlm_complete` |
| **Backend process**| Extension spawns `rlm_backend.py` (stdio) | N/A (MCP server process) |

## MCP tool list (stable)

When using the RLM MCP server (Cursor or VS Code), these tools are available:

| Tool name               | Purpose                          |
|-------------------------|----------------------------------|
| `rlm_session_create`    | Start a new RLM session          |
| `rlm_session_close`    | Close current session            |
| `rlm_roots_set`        | Set allowed filesystem roots     |
| `rlm_fs_list`          | List files in workspace          |
| `rlm_fs_manifest`      | Get file manifest                |
| `rlm_fs_handle_create` | Create handle for file content   |
| `rlm_span_read`        | Read span from handle            |
| `rlm_chunk_create`     | Create chunk                     |
| `rlm_chunk_get`        | Get chunk by ID                  |
| `rlm_search_query`    | Semantic search                  |
| `rlm_search_regex`    | Regex search                     |
| `rlm_exec_run`         | Execute Python code (sandboxed)  |
| `rlm_complete`         | Full RLM completion (recursive)  |
| `rlm_provenance_report`| Report provenance                |

## Config matrix

| Setting / concept      | VS Code location           | Cursor location              |
|------------------------|----------------------------|------------------------------|
| MCP server command     | `mcp.servers.rlm-gateway.command` (optional) | `mcpServers.rlm-gateway.command` |
| MCP server args        | `args`, `cwd`, `env`       | `args`, `cwd`, `env`         |
| Typical command        | `uv run --extra mcp python scripts/rlm_mcp_gateway.py` | Same                         |
| Env for repo           | `PYTHONPATH` in env        | `PYTHONPATH: ${workspaceFolder}` |
| API key (RLM complete) | RLM: Set API Key (SecretStorage) | Env vars (e.g. OPENAI_API_KEY) |

## Search pattern options

- `rlm_search_query` and `rlm_search_regex` now accept optional `include_patterns` (array of globs).
- Default behavior remains Python-focused (`*.py`) when `include_patterns` is omitted.
- Recommended multi-language examples:
	- `include_patterns: ["*.py", "*.ts", "*.tsx", "*.md"]`
	- `include_patterns: ["**/*.py", "**/*.md"]`

## Verification (CI)

- **MCP gateway starts**: `uv run --extra mcp python scripts/rlm_mcp_gateway.py --help` (or short-lived stdio run) — see test workflow.
- **Extension build**: Extension CI runs typecheck, lint, build, and unit tests — see `.github/workflows/extension.yml`.
