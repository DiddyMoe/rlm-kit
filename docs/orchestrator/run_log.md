# Run log

Append-only. Timestamp, phase, actions, verification results, idempotency notes.

---

## 2025-02-08 — Phases 0–2B (doc-only)

- **Phase 0**: Created docs/index/setup_matrix.md, docs/integration/ide_matrix.md, docs/orchestrator/state.json. Idempotent: new files.
- **Phase 1**: Created docs/INDEX.md, docs/index/project_index.json, docs/index/trajectory_logging_coverage.md, docs/integration/ide_touchpoints.md. Extended setup_matrix in Phase 0 (no duplicate).
- **Phase 2**: Created docs/orchestrator/proposal_prioritized.md with ranked proposal and options/recommendations per area.
- **Phase 2A**: Created docs/research/landscape.md, bibliography.md, recommendations_map.md, benchmarks_to_run.md. Idempotent: initial content; append with datestamps for updates.
- **Phase 2B**: Created docs/quality/bug_backlog.md, failure_modes.md, observability_gaps.md, fix_now.md. Top Fix Now 1–10 with file/line; 11–20 reserved.
- **State**: Updated docs/orchestrator/state.json with phases 0, 1, 2, 2a, 2b completed and last_run.
- **Verification**: No code changes; lint/format/test not run (doc-only). Commands for future verification: make lint, make format, make test, make ext-check.
- **Idempotency**: All artifacts new; state and run_log updated in place.

---

## 2025-02-08 — Phase 0–3 full run (index + docs + AUTO-APPLY)

- **Phase 0**: Validated setup_matrix.md, ide_matrix.md; updated state.json with env.ide_targets (vscode 1.99+, cursor mcp_only). Idempotent: in-place update.
- **Phase 1**: Created docs/INDEX.md, docs/index/project_index.json at repo root; trajectory_logging_coverage and ide_touchpoints validated. Idempotent: new files; state Phase 1 artifacts match.
- **Phase 2**: Created docs/orchestrator/proposal_prioritized.md (synced from jki content). Idempotent: new file.
- **Phase 2A**: Created docs/research/bibliography.md, recommendations_map.md, benchmarks_to_run.md; appended landscape.md with datestamp. Idempotent: new files + append.
- **Phase 2B**: Created docs/quality/bug_backlog.md (ranked 1–20); failure_modes, observability_gaps, fix_now unchanged. Idempotent: new file.
- **Phase 3 (AUTO-APPLY)**: (1) rlm/utils/parsing.py — docstring typo "trjaectories" → "trajectories" (fix_now #6). (2) rlm/core/types.py — REPLResult field llm_calls → rlm_calls and docstring (fix_now #2). No schema or dependency changes.
- **Verification**: make lint, make format, make test, make ext-check — all passed (135 passed, 8 skipped; ext-check 15 tests passed).
- **State**: recommendations.applied and recommendations.verified updated with fix_now#6 and fix_now#2.
- **Idempotency**: Detected existing docs; created only missing artifacts; state and run_log updated in place.

---

## 2025-02-08 — Build out plan findings (doc-only)

- **Playbooks**: Created docs/integration/playbooks.md — "Use from VS Code Agent Chat" and "Use from Cursor Agent Chat" with prerequisites, setup, config, MCP tool list, server modes. Proposal #8 recommendation A.
- **Trajectory**: docs/index/trajectory_logging_coverage.md — added "Run identity" section (how run_id is produced: filename timestamp + uuid prefix; no run_id in metadata line; schema change = approval). Proposal #6 recommendation A.
- **Research**: bibliography.md — added URLs (arXiv, blog, VS Code API, MCP); filled Sandbox and Trajectory with repo pointers. landscape.md — expanded with failure-mode refs, IDE version notes, sandbox two surfaces, trajectory run identity; dated append. recommendations_map.md — added playbooks, failure modes/reliability, testing/determinism with file refs. benchmarks_to_run.md — "How to run" filled with concrete commands (pytest exclusions, make ext-check, MCP start command).
- **Quality**: failure_modes.md — added file/line pointers (retry.py, comms_utils, constants, sandbox, validation). observability_gaps.md — run identity paragraph updated with pointer to trajectory_logging_coverage.md.
- **Index**: docs/INDEX.md — linked to playbooks.md.
- **Idempotency**: Append-only or in-place expansion; no schema or code changes.

---

## 2025-02-08 — Implementation (fix_now #1, #3, #4, #10)

- **fix_now #1**: Added `SnippetProvenance` dataclass to rlm/core/types.py (file_path, start_line, end_line, content_hash, source_type; to_dict()). Unblocks MCP provenance/session/exec_tools.
- **fix_now #3**: LMRequest.from_dict: depth default 0 (was -1), removed TODO. rlm/core/comms_utils.py.
- **fix_now #4**: complete_tools: stopped passing max_tokens and max_cost to RLM(); RLM does not support them. rlm/mcp_gateway/tools/complete_tools.py.
- **fix_now #10**: PathValidator class docstring: documented that when multiple allowed_roots are set, a path is valid if under any one of them. rlm/mcp_gateway/validation.py.
- **Verification**: make lint, make format, make test (135 passed, 8 skipped), make ext-check (15 passed). All gates passed.
- **State**: recommendations.applied and recommendations.verified updated with fix_now#1, #3, #4, #10.
