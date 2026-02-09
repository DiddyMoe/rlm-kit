# Fix Now list

Top-20 with file/line pointers and low-risk resolutions. Update in place.

| # | Item | File | Location / note | Resolution |
|---|------|------|------------------|------------|
| 1 | SnippetProvenance missing | rlm/core/types.py | Not defined; imported by session.py, provenance.py, exec_tools.py | Done: Added dataclass SnippetProvenance with to_dict(). |
| 2 | REPLResult llm_calls vs rlm_calls | rlm/core/types.py | Type hint llm_calls; impl uses rlm_calls | Done: Aligned field to rlm_calls; docstring added. |
| 3 | LMRequest depth default -1 | rlm/core/comms_utils.py | from_dict depth=get("depth", -1) | Done: Default 0; TODO removed. |
| 4 | complete_tools unsupported kwargs | rlm/mcp_gateway/tools/complete_tools.py | RLM(max_tokens=..., max_cost=...) | Done: Stopped passing max_tokens/max_cost to RLM. |
| 5 | rlm_backend no progress | vscode-extension/python/rlm_backend.py | handle_completion | Done: ProgressLogger emits progress each iteration; bridge/orchestrator already had progressHandler; participant already passes onProgress. |
| 6 | Parsing docstring typo | rlm/utils/parsing.py | Docstring "trjaectories" | Done: Fixed to "trajectories". |
| 7 | MCP deps not in pyproject | pyproject.toml | Missing mcp, fastapi, uvicorn | Done: Added optional extra [mcp] with mcp>=1.0.0; fastapi/uvicorn documented for HTTP mode in setup_matrix. |
| 8 | No strict typecheck in CI | Makefile, .github/workflows | No ty/pyright step | Done: make typecheck (ty check); CI already runs ty check in style.yml (--exit-zero). |
| 9 | REPLResult __init__ vs dataclass | rlm/core/types.py | Custom __init__, rlm_calls | Done: Documented in trajectory_logging_coverage.md (field rlm_calls; custom __init__ same effective shape). |
| 10 | PathValidator multiple roots | rlm/mcp_gateway/validation.py | normalized vs allowed_roots | Done: Class docstring documents multiple roots. |
| 11 | Run identity in trajectory | rlm/logger/rlm_logger.py | No run_id in metadata line; only in filename | Doc: trajectory_logging_coverage.md (Run identity). Code: optional run_id in RLMMetadata = schema change; REQUIRES APPROVAL (STEP-012). |
| 12 | No trajectory schema validation | tests/ | No validator for JSONL shape | Done (test-side): tests/test_trajectory_schema.py asserts metadata/iteration keys. Optional production validator = approval. |
| 13 | Log rotation multi-process | rlm/logger/rlm_logger.py | Per-instance; multi-process/session behavior | Doc: observability_gaps (Log rotation). Code: rotation/size limits = REQUIRES APPROVAL (STEP-013). |
| 14 | Provider metrics aggregation | — | Usage in usage_summary; no aggregate dashboard | Doc: observability_gaps (Provider metrics). Optional export script from JSONL; no write-path change. |
| 15 | MCP tool structured metrics | rlm/mcp_gateway/ | Gateway logs tool_call; no structured metrics | Doc: observability_gaps (MCP tool logging). Optional metrics export = approval. |
| 16 | Cancellation not implemented | rlm/core/rlm.py | No mid-completion abort | Doc: failure_modes.md (Cancellation). Design for abort = approval. |
| 17 | Concurrency assumptions | backendBridge.ts, rlm_backend.py | Session-scoped state; generation counter | Doc: failure_modes.md (Concurrency). No code change. |
| 18 | Serialization (dill) lifecycle | rlm/environments/ | Isolated env state load/save | Doc: failure_modes.md (Serialization). Persistence tests = optional. |
| 19 | Context overflow constants | rlm/core/constants.py, rlm/mcp_gateway/constants.py | MAX_SUB_CALL_PROMPT_CHARS alignment | Doc: failure_modes (Context overflow). Align constants = small approved patch. |
| 20 | Sandbox two surfaces doc | docs/quality | LocalREPL vs exec_tools | Done: docs/quality/security_surfaces.md (safe_builtins split, path validation). |
