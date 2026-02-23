# RLM MCP Workflow Skill

Use this skill when working in Cursor Agent mode and you need repository-scale analysis with bounded context reads.

## Goal

Apply RLM MCP tools in a safe, efficient order to avoid large unbounded reads and produce explainable outputs.

## Workflow

1. `rlm_session_create`
2. `rlm_roots_set`
3. `rlm_search_query` / `rlm_search_regex` (use `include_patterns` for mixed-language repos)
4. `rlm_span_read` or `rlm_chunk_get` for bounded context retrieval
5. `rlm_complete` only after context is narrowed

## Guidance

- Prefer references/spans over full-file reads.
- Keep operations inside configured roots.
- Use `response_format: "structured"` or `"mcp_app"` when presenting final answers.
- For long tasks, surface progress and provenance (`rlm_provenance_report`).
