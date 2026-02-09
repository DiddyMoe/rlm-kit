# Observability gaps

Missing logs, metrics, or trace points.

## Run identity

No explicit run_id in RLMLogger metadata line; run identity is encoded in the **file name** only: `{file_name}_{timestamp}_{run_id}.jsonl` where run_id = first 8 chars of uuid.uuid4() (rlm/logger/rlm_logger.py). Documented in docs/index/trajectory_logging_coverage.md (Run identity section). Adding run_id to the metadata JSONL line = schema change (approval required).

## Progress visibility

Backend does not emit progress during completion; extension cannot show per-iteration updates. Suggest progress callback or wrapper; design required.

## Trajectory validation

No schema validation of JSONL. Suggest optional validator in tests; document schema.

## Log rotation

RLMLogger per instance; multi-process/session behavior. Document; rotation = approval.

## Provider metrics

Usage in usage_summary; no aggregate dashboard. Optional export script from JSONL; no write-path change.

## MCP tool logging

Gateway logs tool_call; no structured metrics. Optional metrics export; approval for new metrics.
