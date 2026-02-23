# Observability gaps

Missing logs, metrics, or trace points.

## Run identity

No explicit run_id in RLMLogger metadata line; run identity is encoded in the **file name** only: `{file_name}_{timestamp}_{run_id}.jsonl` where run_id = first 8 chars of uuid.uuid4() (rlm/logger/rlm_logger.py). Documented in docs/index/trajectory_logging_coverage.md (Run identity section). Adding run_id to the metadata JSONL line = schema change (approval required).

## Progress visibility

Done: ProgressLogger in rlm_backend.py emits per-iteration progress; extension bridge/orchestrator/participant deliver it to chat stream.

## Trajectory validation

Done (test-side): tests/test_trajectory_schema.py asserts metadata/iteration keys. Optional production validator = approval.

## Log rotation

Done: RLMLogger accepts optional `max_file_bytes` for rotation. Document: observability_gaps.md reference.

## Provider metrics

Usage in usage_summary; no aggregate dashboard. Optional export script from JSONL; no write-path change.

## MCP tool logging

Gateway logs tool_call; no structured metrics. Optional metrics export; approval for new metrics.

## Quality pipeline observability

The orchestrator prompt pipeline now tracks convergence explicitly:
- Debug agent session summaries include item counts (fixed, blocked, remaining, newly added)
- `Convergence` field in session summaries flags whether the backlog is shrinking, stable, or growing
- Exposure tracking adds newly discovered issues as backlog items rather than silently dropping them
- Run log entries include tool output summaries, not just pass/fail
- These improvements address the recall bottleneck where plan misses → agent never fixes
