# Trajectory and logging coverage

Where trajectory/trace data is produced and consumed. No schema changes without explicit approval.

## Python — core types

- **rlm/core/types.py**
  - RLMIteration: prompt, response, code_blocks, final_answer, iteration_time; to_dict().
  - RLMMetadata: root_model, max_depth, max_iterations, backend, environment_type, etc.; to_dict().
  - CodeBlock: code, result (REPLResult); to_dict().
  - REPLResult: stdout, stderr, locals, execution_time, rlm_calls (list of RLMChatCompletion); to_dict().
  - RLMChatCompletion: root_model, prompt, response, usage_summary, execution_time; to_dict().

## Python — logger

- **rlm/logger/rlm_logger.py**
  - RLMLogger: Writes JSONL to a file under log_dir. First line: metadata (type metadata, RLMMetadata.to_dict()). Subsequent lines: iterations (type iteration, iteration count, timestamp, RLMIteration.to_dict()).
  - File name pattern: file_name + timestamp + run_id + .jsonl (e.g. rlm_2025-02-08_12-00-00_abc12345.jsonl).

### Run identity (determinism; proposal #6)

- **How run_id is produced today**: In `RLMLogger.__init__`, `run_id` is the first 8 characters of `uuid.uuid4()` (e.g. `abc12345`). The log file name is `{file_name}_{timestamp}_{run_id}.jsonl` with `timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")`. So each logger instance gets one run_id; it is **not** written as a field in the metadata JSONL line — only embedded in the filename. To correlate a run with a file: use the filename. Adding an explicit `run_id` field to the metadata line would require a schema change (approval required).

## Python — debugging

- **rlm/debugging/call_history.py**
  - CallHistoryEntry: call_id, timestamp, model, prompt, response, input/output/total tokens, execution_time, metadata; to_dict().
  - CallHistory: list of entries; add_call(), to_json(), export. Not wired into RLM by default.

- **rlm/debugging/graph_tracker.py**
  - GraphNode: node_id, parent_id, depth, iteration, model, prompt_preview, response_preview, tokens, execution_time, metadata; optional networkx DiGraph.
  - GraphTracker: add_node(), to_dict(), export. For recursive call visualization.

## Extension — TypeScript

- **vscode-extension/src/logger.ts**
  - Structured JSONL logger; output path configurable (e.g. workspace logs/trace.jsonl or global storage).
  - Rolling at configurable size (default 10 MB); redaction patterns for secrets/API keys.
  - Toggle: rlm.tracingEnabled.

- **vscode-extension/src/orchestrator.ts**
  - Emits span-style log entries (spanId, durationMs, stepsUsed, etc.) via logger. Does not duplicate Python trajectory; wraps backend call with budget and observability.

## JSONL paths (summary)

| Source        | Location |
|---------------|----------|
| RLMLogger     | log_dir / file_name + timestamp + run_id + .jsonl |
| Extension     | logs/trace.jsonl (workspace) or global storage |

## Schema summary (do not change without approval)

- Metadata line: type, timestamp, root_model, max_depth, max_iterations, backend, backend_kwargs, environment_type, environment_kwargs, other_backends.
- Iteration line: type, iteration, timestamp, prompt, response, code_blocks (each: code, result with stdout/stderr/locals/execution_time/rlm_calls), final_answer, iteration_time.
