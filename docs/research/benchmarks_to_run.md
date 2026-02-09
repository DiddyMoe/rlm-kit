# Benchmarks to run

Proposed latency, cost, success, and IDE UX metrics. Append with datestamps.

## Latency and cost

- **End-to-end completion time**: Single RLM completion (fixed prompt + context size) from request to final answer; p50/p95.
- **Sub-call latency**: Time per llm_query from REPL; distribution over a run.
- **Token usage**: Input/output tokens per run (and per model if multiple); map to cost where applicable.
- **MCP tool call latency**: Time per tool call (e.g. rlm.span.read, rlm.complete) in stdio mode.

## Success metrics

- **Completion success rate**: Fraction of runs that terminate with FINAL/FINAL_VAR (no max_iterations exhaustion or crash).
- **Correctness**: On a small set of golden tasks, exact or semantic match of final answer (optional).
- **Stability**: No crash or hang; clean shutdown of backend and MCP server.

## IDE UX metrics

- **Time to first token / first progress**: For extension, time from user send to first progress or result chunk (if streaming/progress is added).
- **Session stability**: Multiple consecutive completions in one session (persistent backend); no leaks or stale state.
- **MCP discovery**: Time for Cursor to list tools after MCP server start; tool call round-trip latency.

## How to run

- **Python / RLM core**: `uv run pytest tests/ -v --ignore=tests/repl/test_modal_repl.py --ignore=tests/clients/` (same exclusions as CI). For custom benchmark script: add scripts/benchmark_run.py that runs N completions with mock or live LM and outputs JSON of metrics; optional pytest-benchmark or harness.
- **Extension**: `make ext-check` (typecheck, lint, logger tests). Manual smoke: launch Extension Development Host (F5), open Chat, send one `@rlm` message, assert response and no backend crash.
- **MCP**: Start gateway: `uv run python scripts/rlm_mcp_gateway.py` (stdio, from repo root with PYTHONPATH). Or via Cursor: ensure .cursor/mcp.json is configured; Cursor lists tools on MCP server start. To measure tool latency: use IDE or a script that invokes MCP tools/call (e.g. rlm.session.create, then rlm.complete) and record round-trip time.
