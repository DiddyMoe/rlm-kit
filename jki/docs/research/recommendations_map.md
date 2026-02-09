# Recommendations map

Sources to repo areas. Append with datestamps.

## RLM paper

- Completion loop, max_iterations, max_depth: rlm/core/rlm.py
- Sub-call prompt bound: rlm/core/constants.py, rlm/mcp_gateway/constants.py
- REPL and context: rlm/environments/base_env.py, local_repl.py
- Socket protocol: rlm/core/comms_utils.py, lm_handler.py

## VS Code and Cursor

- Chat Participant: vscode-extension/src/rlmParticipant.ts
- MCP server: rlm/mcp_gateway/server.py, scripts/rlm_mcp_gateway.py
- Config: configService.ts, .cursor/mcp.json, .vscode/settings.json
- Backend: backendBridge.ts, rlm_backend.py

## Sandbox

- MCP exec: rlm/core/sandbox (ast_validator, restricted_exec, safe_builtins), exec_tools.py
- REPL: local_repl.py. Paths: validation.py. Limits: mcp_gateway/constants.py

## Observability

- Types: rlm/core/types.py. Logger: rlm_logger.py, logger.ts. Orchestrator: orchestrator.ts. Debug: call_history.py, graph_tracker.py
