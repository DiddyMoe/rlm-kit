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
- Playbooks: docs/integration/playbooks.md

## Sandbox

- MCP exec: rlm/core/sandbox (ast_validator, restricted_exec, safe_builtins), rlm/mcp_gateway/tools/exec_tools.py
- REPL: rlm/environments/local_repl.py. Paths: rlm/mcp_gateway/validation.py. Limits: rlm/mcp_gateway/constants.py, rlm/core/sandbox

## Observability

- Types: rlm/core/types.py. Logger: rlm/logger/rlm_logger.py, vscode-extension/src/logger.ts. Orchestrator: vscode-extension/src/orchestrator.ts. Debug: rlm/debugging/call_history.py, graph_tracker.py. Run identity: docs/index/trajectory_logging_coverage.md (run identity section).

## Failure modes and reliability

- Provider retries: rlm/core/retry.py (retry_with_backoff). Client errors: rlm/clients/*. LMResponse.error: rlm/core/comms_utils.py. Taxonomy: docs/quality/failure_modes.md.

## Testing and determinism

- Tests: tests/ (test_parsing, test_types, test_local_repl*, test_multi_turn_integration, repl/, clients/). Mock LM: tests/mock_lm.py. Determinism: run_id in RLMLogger filename (rlm/logger/rlm_logger.py); doc in trajectory_logging_coverage.md.
