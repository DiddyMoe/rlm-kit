# RLM MCP Registry Checklist

Preparation checklist for submitting the RLM gateway to the GitHub MCP Registry.

## Server naming and metadata

- Use a stable camelCase server name: `rlmGateway`.
- Keep human-readable label: `rlm-gateway`.
- Provide icon metadata (`icons`) for server and tools.
- Ensure top-level description is concise and specific to code retrieval + recursive completion.

## Packaging options

- **Python package path**: publish the gateway as a pip-installable package exposing a console entry point.
- **Script path**: keep `scripts/rlm_mcp_gateway.py` usable for local stdio integrations.

## Contract and security checks

- Verify stdio launch works from clean clone with `uv run python scripts/rlm_mcp_gateway.py`.
- Verify HTTP mode enforces API key in remote mode.
- Verify path validation denies traversal/restricted paths.
- Verify `rlm_exec_run` enforces sandbox size/timeout/memory limits.

## Tool UX checks

- Ensure tool names and titles are stable.
- Verify tool sets are documented for VS Code (`retrieval`, `execution`, `session`).
- Verify MCP icons render in VS Code MCP server list/tool picker.

## Submission notes

- Registry submission itself is external/manual.
- Before submission, run `make check && make ext-check` and include release notes for tool contracts.
