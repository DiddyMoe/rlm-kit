# Research landscape

Append with datestamps.

## RLM

- Paper: arXiv:2512.24601. Blog and upstream: alexzhang13. Design: REPL, recursive sub-calls, external context as inspectable object.
- Failure modes and design rationale: documented in docs/quality/failure_modes.md and docs/quality/bug_backlog.md (Phase 2B). Observed issues: provider errors, recursion runaway, cancellation not implemented, concurrency assumptions, context overflow, sandbox two surfaces, serialization (dill) lifecycle.

## VS Code

- Chat participants (vscode.chat), LM API (vscode.lm), MCP (optional in settings), SecretStorage for API keys. Minimum version 1.99+ (vscode-extension/package.json engines).
- Custom agents (.agent.md) and Language Model Tools: ecosystem docs; this extension uses Chat Participant + optional MCP.

## Cursor

- Plan/Agent/Ask/Debug modes; rules (.cursorrules); MCP from .cursor/mcp.json. No Chat Participant in Cursor (platform detection in vscode-extension/src/platform.ts). Primary integration: MCP tools; Cursor-as-outer-loop or rlm.complete with API key.

## Sandbox

- Two surfaces: LocalREPL (rlm/environments/local_repl.py) vs MCP exec (rlm/mcp_gateway/tools/exec_tools.py). AST validation and restricted builtins in rlm/core/sandbox/. Resource limits and constants in rlm/core/constants.py and rlm/mcp_gateway/constants.py. Isolation: process (local/docker) vs cloud (Modal, Prime, Daytona).

## Trajectory

- JSONL schema in docs/index/trajectory_logging_coverage.md. RLMLogger (rlm/logger/rlm_logger.py); run identity in filename (timestamp + uuid prefix). No schema change without approval.

---

_2025-02-08_: Phase 2A artifacts (bibliography, recommendations_map, benchmarks_to_run) created under docs/research/.

_2025-02-08_: Landscape expanded with failure-mode refs, IDE version notes, sandbox surfaces, trajectory run identity.

_2025-02-08_: Plan RLM-PLAN-20250208-1600 execution; research artifacts validated (landscape, bibliography, recommendations_map, benchmarks_to_run).
