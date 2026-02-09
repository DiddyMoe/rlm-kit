# Fix Now list

Top-20 with file/line pointers and low-risk resolutions. Update in place.

| # | Item | File | Location / note | Resolution |
|---|------|------|------------------|------------|
| 1 | SnippetProvenance missing | rlm/core/types.py | Not defined; imported by session.py, provenance.py, exec_tools.py | Done: Added dataclass SnippetProvenance with to_dict(). |
| 2 | REPLResult llm_calls vs rlm_calls | rlm/core/types.py | Type hint llm_calls; impl uses rlm_calls | Done: Aligned field to rlm_calls; docstring added. |
| 3 | LMRequest depth default -1 | rlm/core/comms_utils.py | from_dict depth=get("depth", -1) | Done: Default 0; TODO removed. |
| 4 | complete_tools unsupported kwargs | rlm/mcp_gateway/tools/complete_tools.py | RLM(max_tokens=..., max_cost=...) | Done: Stopped passing max_tokens/max_cost to RLM. |
| 5 | rlm_backend no progress | vscode-extension/python/rlm_backend.py | handle_completion | Emit progress messages in loop (design: callback or wrapper). |
| 6 | Parsing docstring typo | rlm/utils/parsing.py | Docstring "trjaectories" | Done: Fixed to "trajectories". |
| 7 | MCP deps not in pyproject | pyproject.toml | Missing mcp, fastapi, uvicorn | Add optional extra [mcp] (approval for deps). |
| 8 | No strict typecheck in CI | Makefile, .github/workflows | No ty/pyright step | Add ty check or pyright (optional at first). |
| 9 | REPLResult __init__ vs dataclass | rlm/core/types.py | Custom __init__, rlm_calls | Document or align field name. |
| 10 | PathValidator multiple roots | rlm/mcp_gateway/validation.py | normalized vs allowed_roots | Done: Class docstring documents multiple roots. |
| 11–20 | Reserved | — | Failure-mode and observability follow-ups | Fill from bug_backlog and observability_gaps. |
