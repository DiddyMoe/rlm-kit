# IDE adapter

Single reference mapping VS Code and Cursor to the same tool/contract table and config matrix. See also [ide_matrix.md](ide_matrix.md), [ide_touchpoints.md](ide_touchpoints.md), [playbooks.md](playbooks.md).

## Tool and contract table

| Contract / surface   | VS Code                    | Cursor                     |
|---------------------|----------------------------|----------------------------|
| **Primary entry**   | Chat Participant `@rlm`    | MCP tools (rlm-gateway)    |
| **Config file**     | `settings.json` (`rlm.*`)  | `.cursor/mcp.json`         |
| **MCP server**      | Optional (`mcp.servers`)   | Required (`mcpServers.rlm-gateway`) |
| **LLM source**     | `vscode.lm` or API key     | Cursor LLM or env API key for `rlm.complete` |
| **Backend process**| Extension spawns `rlm_backend.py` (stdio) | N/A (MCP server process) |

## MCP tool list (stable)

When using the RLM MCP server (Cursor or VS Code), these tools are available:

| Tool name               | Purpose                          |
|-------------------------|----------------------------------|
| `rlm.session.create`    | Start a new RLM session          |
| `rlm.session.close`    | Close current session            |
| `rlm.roots.set`        | Set allowed filesystem roots     |
| `rlm.fs.list`          | List files in workspace          |
| `rlm.fs.manifest`      | Get file manifest                |
| `rlm.fs.handle.create` | Create handle for file content   |
| `rlm.span.read`        | Read span from handle            |
| `rlm.chunk.create`     | Create chunk                     |
| `rlm.chunk.get`        | Get chunk by ID                  |
| `rlm.search.query`    | Semantic search                  |
| `rlm.search.regex`    | Regex search                     |
| `rlm.exec.run`         | Execute Python code (sandboxed)  |
| `rlm.complete`         | Full RLM completion (recursive)  |
| `rlm.provenance.report`| Report provenance                |

## Config matrix

| Setting / concept      | VS Code location           | Cursor location              |
|------------------------|----------------------------|------------------------------|
| MCP server command     | `mcp.servers.rlm-gateway.command` (optional) | `mcpServers.rlm-gateway.command` |
| MCP server args        | `args`, `cwd`, `env`       | `args`, `cwd`, `env`         |
| Typical command        | `uv run python scripts/rlm_mcp_gateway.py` | Same                         |
| Env for repo           | `PYTHONPATH` in env        | `PYTHONPATH: ${workspaceFolder}` |
| API key (RLM complete) | RLM: Set API Key (SecretStorage) | Env vars (e.g. OPENAI_API_KEY) |

## Verification (CI)

- **MCP gateway starts**: `uv run python scripts/rlm_mcp_gateway.py --help` (or short-lived stdio run) — see test workflow.
- **Extension build**: Extension CI runs typecheck, lint, build, and unit tests — see `.github/workflows/extension.yml`.
