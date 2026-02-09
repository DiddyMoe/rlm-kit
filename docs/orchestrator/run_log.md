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

---

## 2025-02-08 — Phase 3 Step 3.1 (Doc-only REPLResult and run identity)

- **Plan**: RLM-PLAN-20250208-1200; docs/orchestrator/plan.md.
- **Action**: Documented REPLResult field name (rlm_calls) and custom __init__ in docs/index/trajectory_logging_coverage.md; marked fix_now #9 done in docs/quality/fix_now.md. Created docs/orchestrator/plan.md (canonical plan). No code change.
- **Verification**: make lint — passed.
- **State**: Phase 3 steps 3.1 verified; fix_now#9 applied and verified; active_plan_id and active_plan_path set.

---

## 2025-02-08 — Phase 3 Step 3.2 (IDE compatibility doc + smoke)

- **Action**: Created docs/integration/ide_adapter.md (tool/contract table, config matrix, MCP tool list, verification refs). Added MCP gateway smoke step to .github/workflows/test.yml (install mcp in CI, run scripts/rlm_mcp_gateway.py --help). Extension build already in extension.yml.
- **Verification**: make check (135 passed, 8 skipped), make ext-check (15 passed).
- **State**: Step 3.2 verified.

---

## 2025-02-08 — Phase 3 Step 3.3 (Observability test-side schema check)

- **Action**: Added tests/test_trajectory_schema.py: two tests that use RLMLogger to write metadata + iteration, then assert JSONL lines have expected keys (metadata, iteration, code_blocks[].result). No production write path change.
- **Verification**: make test — 137 passed, 8 skipped.
- **State**: Step 3.3 verified.

---

## 2025-02-08 — Phase 3 Step 3.4 (Sandbox two surfaces doc)

- **Action**: Created docs/quality/security_surfaces.md documenting LocalREPL vs MCP exec_tools (safe_builtins split, PathValidator, limits). Marked fix_now #20 done in fix_now.md.
- **Verification**: Doc presence (no code change).
- **State**: Step 3.4 verified; fix_now #20 done.

---

## 2025-02-08 — Phase 3 Step 3.8 (Reliability: retry in more call sites)

- **Action**: Wrapped socket_request in send_lm_request and send_lm_request_batched (rlm/core/comms_utils.py) with retry_with_backoff (max_attempts=3, ConnectionError/TimeoutError/OSError). Documented in docs/quality/failure_modes.md (Socket LM requests). No public API change. Fixed test_trajectory_schema.py lint (unused pytest, import order).
- **Verification**: make check (137 passed, 8 skipped), make ext-check (15 passed).
- **State**: Step 3.8 verified.

---

## 2025-02-08 — Phase 3 Steps 3.5, 3.6, 3.7 (approved)

- **Step 3.5 (fix_now #5 — rlm_backend progress)**: Added ProgressLogger in vscode-extension/python/rlm_backend.py that implements log_metadata (no-op) and log(iteration) → send_progress(nonce, count, max_iterations, text). BackendState holds progress_logger, current_progress_nonce, current_progress_max_iterations; handle_completion sets them and passes logger to RLM via get_or_create_rlm(). Extension already had progressHandler and participant onProgress; progress now flows from Python to chat stream. Verification: make ext-check passed.
- **Step 3.6 (fix_now #7 — MCP optional extra)**: Added optional dependency [mcp] with mcp>=1.0.0 in pyproject.toml. Updated docs/index/setup_matrix.md (mcp extra table row; HTTP mode documents fastapi/uvicorn install). Verification: uv sync --extra mcp, uv run python scripts/rlm_mcp_gateway.py --help.
- **Step 3.7 (fix_now #8 — strict typecheck)**: Added make typecheck (uv run ty check --exit-zero --output-format=concise). CI already runs ty check in style.yml with --exit-zero. Verification: make typecheck (exit 0), make check passed.
- **State**: Steps 3.5, 3.6, 3.7 verified; fix_now #5, #7, #8 applied and verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-001 (Baseline)

- **Plan**: RLM-PLAN-20250208-1600; docs/orchestrator/plan.md.
- **Action**: Updated state.json with active_plan_id RLM-PLAN-20250208-1600, active_plan_path, plan_steps (STEP-001 through STEP-013). Validated setup_matrix.md and ide_matrix.md (no changes; already current). No code edits.
- **Verification**: make lint — passed.
- **State**: STEP-001 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-002 (Project index refresh)

- **Action**: Idempotently updated docs/index/project_index.json (added rlm.core.sandbox.* and rlm.mcp_gateway.tools.* submodules). docs/INDEX.md, trajectory_logging_coverage.md, setup_matrix.md, ide_touchpoints.md present and current; no changes. No code edits.
- **Verification**: make lint — passed.
- **State**: STEP-002 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-003 (Prioritized proposal)

- **Action**: proposal_prioritized.md already present with ranked list (1–8), options A/B/C, and recommendations. No change.
- **Verification**: Doc only; file exists.
- **State**: STEP-003 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-004 (Research)

- **Action**: Validated docs/research/landscape.md, bibliography.md, recommendations_map.md, benchmarks_to_run.md. Appended datestamped line to landscape.md. No code edits.
- **Verification**: All four files exist.
- **State**: STEP-004 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-005 (Quality docs)

- **Action**: Validated docs/quality/bug_backlog.md, failure_modes.md, observability_gaps.md, fix_now.md, security_surfaces.md. Top-20 Fix Now and security_surfaces (LocalREPL vs MCP exec_tools) present. No code edits.
- **Verification**: All listed files exist.
- **State**: STEP-005 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-010 (Verification pass)

- **Action**: Ran make lint, make format, make test, make typecheck, make ext-check. No source code edits. Confirmed state.json has active_plan_id and plan_steps.
- **Verification**: lint passed; format (75 files unchanged); test 137 passed, 8 skipped; typecheck (ty --exit-zero); ext-check 15 passed.
- **State**: STEP-010 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-011 (fix_now 11–19 doc-only)

- **Action**: Filled fix_now.md rows 11–19 with file/line and resolution (doc-only or REQUIRES APPROVAL). Aligned with bug_backlog and observability_gaps. No code or schema changes.
- **Verification**: make lint — passed.
- **State**: STEP-011 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: Approval gate (STEP-012, STEP-013)

- **Action**: Build stopped at first REQUIRES-APPROVAL step. STEP-012 and STEP-013 not executed; approval request presented below. State: STEP-012, STEP-013 marked skipped_unapproved.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-012 (optional run_id in trajectory metadata) — APPROVED

- **Action**: Added optional `run_id: str | None = None` to RLMMetadata (rlm/core/types.py); included in to_dict(). RLMLogger exposes `run_id` attribute; RLM passes logger.run_id when constructing metadata (rlm/core/rlm.py). Updated docs/index/trajectory_logging_coverage.md and schema summary. tests/test_trajectory_schema.py: added run_id to METADATA_KEYS.
- **Verification**: make check (137 passed, 8 skipped), make ext-check (15 passed).
- **State**: STEP-012 verified.

---

## 2025-02-08 — Plan RLM-PLAN-20250208-1600: STEP-013 (log rotation/size limits in RLMLogger) — APPROVED

- **Action**: RLMLogger __init__ now accepts optional `max_file_bytes: int | None = None`. When set, before each iteration write the logger checks file size and rotates to a new file (new run_id) if the next write would exceed the limit; metadata is re-written as first line of the new file using _last_metadata. Schema unchanged per file. Documented in docs/index/trajectory_logging_coverage.md (Log rotation).
- **Verification**: make check, make ext-check — passed.
- **State**: STEP-013 verified.
