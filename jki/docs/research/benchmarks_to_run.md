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

## How to run (placeholder)

- **Python**: Add a small benchmark script (e.g. scripts/benchmark_run.py) that runs N completions with mock or live LM; output JSON of metrics. Optional: pytest-benchmark or custom harness.
- **Extension**: Manual or automated “smoke” run: start backend, send one completion, assert result and no error.
- **MCP**: Start gateway in stdio; script or IDE triggers tools/list and tools/call; measure latency. Document commands in this file when available.
