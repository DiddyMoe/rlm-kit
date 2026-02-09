# Bug backlog

Ranked bugs; used to fill fix_now 11–20 and for prioritization. Update in place.

| Rank | Summary | Source | File / area | Notes |
|------|---------|--------|-------------|-------|
| 1 | SnippetProvenance missing | fix_now #1 | rlm/core/types.py | Blocker for MCP; add dataclass. |
| 2 | REPLResult llm_calls vs rlm_calls | fix_now #2 | rlm/core/types.py | Align type hint with impl. |
| 3 | LMRequest depth default -1 | fix_now #3 | rlm/core/comms_utils.py | Require depth or document. |
| 4 | complete_tools unsupported kwargs | fix_now #4 | rlm/mcp_gateway/tools/complete_tools.py | Stop passing or add RLM support. |
| 5 | rlm_backend no progress | fix_now #5 | vscode-extension/python/rlm_backend.py | Progress callback design. |
| 6 | Parsing docstring typo | fix_now #6 | rlm/utils/parsing.py | "trjaectories" → "trajectories". |
| 7 | MCP deps not in pyproject | fix_now #7 | pyproject.toml | Optional extra [mcp] (approval). |
| 8 | No strict typecheck in CI | fix_now #8 | Makefile, .github/workflows | Add ty/pyright (approval). |
| 9 | REPLResult __init__ vs dataclass | fix_now #9 | rlm/core/types.py | Document or align. |
| 10 | PathValidator multiple roots | fix_now #10 | rlm/mcp_gateway/validation.py | Document behavior. |
| 11 | Run identity in trajectory | observability_gaps | rlm/logger/rlm_logger.py | Optional run_id; schema = approval. |
| 12 | No trajectory schema validation | observability_gaps | tests/ | Optional validator in tests. |
| 13 | Log rotation multi-process | observability_gaps | rlm/logger/rlm_logger.py | Document; rotation = approval. |
| 14 | Provider metrics aggregation | observability_gaps | — | Optional export from JSONL. |
| 15 | MCP tool structured metrics | observability_gaps | rlm/mcp_gateway/ | Optional; approval for new metrics. |
| 16 | Cancellation not implemented | failure_modes | rlm/core/rlm.py | Document; design for abort. |
| 17 | Concurrency assumptions | failure_modes | backendBridge, rlm_backend | Document session-scoped state. |
| 18 | Serialization (dill) lifecycle | failure_modes | rlm/environments/ | Document; persistence tests. |
| 19 | Context overflow constants | failure_modes | rlm/core/constants.py, mcp_gateway | Document alignment. |
| 20 | Sandbox two surfaces doc | failure_modes | docs/quality | Document LocalREPL vs exec_tools. |
