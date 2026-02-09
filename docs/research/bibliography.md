# Bibliography

Append with datestamps.

## RLM

- Recursive Language Models — https://arxiv.org/abs/2512.24601
- Blog: RLM — https://alexzhang13.github.io/blog/2025/rlm/
- Upstream: https://github.com/alexzhang13/rlm

## VS Code

- VS Code API: Chat (Participants) — https://code.visualstudio.com/api/extension-guides/chat
- VS Code Language Model API — extension guide for `vscode.lm`
- MCP in VS Code — workspace/docs for configuring MCP servers in settings

## Cursor and MCP

- Cursor: Agent, Plan, Rules — Cursor product docs
- Model Context Protocol — https://modelcontextprotocol.io (or current spec repo)

## Sandboxing

- Python `restricted_exec` / restricted builtins: patterns in this repo (rlm/core/sandbox/).
- AST validation: rlm/core/sandbox/ast_validator.py; safe_builtins.py.
- Containerized execution: rlm/environments/docker_repl.py, modal_repl.py, prime_repl.py, daytona_repl.py.

## Trajectory

- Logging schema (this repo): docs/index/trajectory_logging_coverage.md; rlm/core/types.py (RLMMetadata, RLMIteration, REPLResult, to_dict).
- Trace visualization: rlm/debugging/graph_tracker.py (GraphTracker, DiGraph export); extension logger.ts (span-style entries).
