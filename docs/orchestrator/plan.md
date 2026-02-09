# RLM Fork Orchestrator — Canonical Plan

**plan_id**: `RLM-PLAN-20250208-1200`
**scope**: IDE integration fidelity (VS Code Agent Chat + Cursor MCP), observability, safety, low-risk improvements. No core RLM re-architecture.

---

## Scope

**In scope**

- Docs and index under docs/ (Phases 0–2B artifacts)
- Additive, isolated code changes per step (AUTO-APPLY or approved only)
- Verification: `make lint`, `make format`, `make test`, `make ext-check`
- State and run log: docs/orchestrator/state.json, docs/orchestrator/run_log.md

**Out of scope**

- Core RLM loop/recursion strategy changes
- Trajectory/log schema changes without explicit approval
- New dependencies (beyond patch/minor) or Python version change without approval
- Major refactors or renames

---

## Phase 0 — Baseline (COMPLETED)

Artifacts: docs/index/setup_matrix.md, docs/integration/ide_matrix.md, docs/orchestrator/state.json.

- Python 3.11, uv, lockfile uv.lock; IDE targets: VS Code 1.99+, Cursor MCP-only.
- **No step to execute**; validate only if re-running.

---

## Phase 1 — Project Index (COMPLETED)

Artifacts: docs/INDEX.md, docs/index/project_index.json, docs/index/trajectory_logging_coverage.md, docs/index/setup_matrix.md, docs/integration/ide_touchpoints.md.

- **No step to execute**; idempotent refresh only if index is stale (docs/index/** and docs/INDEX.md).

---

## Phase 2 — Prioritized Proposal (COMPLETED)

Artifact: docs/orchestrator/proposal_prioritized.md. Recommendations 1–8 with options A/B/C and chosen recommendation per area.

---

## Phase 2A — Research (COMPLETED)

Artifacts: docs/research/landscape.md, docs/research/bibliography.md, docs/research/recommendations_map.md, docs/research/benchmarks_to_run.md. Append with datestamps for future updates.

---

## Phase 2B — Debugging / Future-Proofing (COMPLETED)

Artifacts: docs/quality/bug_backlog.md, docs/quality/failure_modes.md, docs/quality/observability_gaps.md, docs/quality/fix_now.md. Top-20 Fix Now list; 1–10 have resolutions (1–4, 6, 10 already applied/verified).

---

## Phase 3 — Build Mode (Plan-Driven Implementation)

**Trigger**: Only when user presses "Build" (Cursor) or explicitly requests implementation (VS Code).

**Mandatory first action**: Load this plan; restate plan_id, scope, next step, allowed files/dirs; confirm no edits outside step.

### Already applied (verified)

- fix_now #1: SnippetProvenance in rlm/core/types.py
- fix_now #2: REPLResult rlm_calls in rlm/core/types.py
- fix_now #3: LMRequest depth default 0 in rlm/core/comms_utils.py
- fix_now #4: complete_tools kwargs in rlm/mcp_gateway/tools/complete_tools.py
- fix_now #6: parsing typo in rlm/utils/parsing.py
- fix_now #10: PathValidator doc in rlm/mcp_gateway/validation.py

### Step 3.1 — Doc-only: REPLResult and run identity (AUTO-APPLY)

- **Allowed**: docs/index/trajectory_logging_coverage.md, docs/quality/fix_now.md
- **Action**: Document REPLResult field name and run_id behavior (fix_now #9 and #6 recommendation A); no schema change.
- **Verification**: No code change; `make lint` (unchanged).
- **Result**: fix_now #9 marked doc-only done; run identity already in trajectory_logging_coverage.

### Step 3.2 — IDE compatibility doc + smoke (AUTO-APPLY, proposal #1 option B)

- **Allowed**: docs/integration/ (new or updated doc only), .github/workflows/ (optional CI job)
- **Action**: Add or update single "IDE adapter" doc mapping both IDEs to tool/contract table and config matrix; add minimal CI: "MCP gateway starts" (e.g. `uv run python scripts/rlm_mcp_gateway.py --help` or short-lived stdio), "extension build" (existing ext-check).
- **Verification**: `make check`, `make ext-check`; CI passes if added.
- **Result**: No behavior change; clarity and verification only.

### Step 3.3 — Observability: run_id in docs + optional test-side schema check (AUTO-APPLY where test-only)

- **Allowed**: docs/index/trajectory_logging_coverage.md, tests/ (new test file or existing test module)
- **Action**: Ensure run identity and JSONL shape are documented; add optional test that loads a sample JSONL and asserts expected keys (no production write path change). Proposal #3 A+B.
- **Verification**: `make test`; new test must pass.
- **Result**: No schema or production log change.

### Step 3.4 — Sandbox: document two surfaces (AUTO-APPLY, proposal #4 option A)

- **Allowed**: docs/quality/ (e.g. new security_surfaces.md or section in failure_modes.md)
- **Action**: Document LocalREPL vs MCP exec_tools (safe_builtins split, path validation); no code change.
- **Verification**: None beyond doc presence.
- **Result**: fix_now #20 and proposal #4 A satisfied.

### Step 3.5 — fix_now #5: rlm_backend progress (REQUIRES APPROVAL)

- **Allowed**: vscode-extension/python/rlm_backend.py, vscode-extension/src/ (orchestrator/backendBridge if callback contract)
- **Action**: Emit progress messages during completion loop (design: callback or wrapper). IDE-facing behavior change.
- **Verification**: `make ext-check`, manual smoke in VS Code.
- **Do not execute** until explicitly approved and added to this step in plan.

### Step 3.6 — MCP optional extra [mcp] (REQUIRES APPROVAL)

- **Allowed**: pyproject.toml
- **Action**: Add optional dependency group or extra [mcp] with mcp; document fastapi/uvicorn for HTTP mode in setup_matrix. fix_now #7.
- **Verification**: `uv sync` (with/without extra), `make check`, MCP gateway starts.
- **Do not execute** until explicitly approved.

### Step 3.7 — Strict typecheck in CI (REQUIRES APPROVAL)

- **Allowed**: Makefile, .github/workflows/
- **Action**: Add ty or pyright step (e.g. make typecheck); optional at first. fix_now #8.
- **Verification**: `make typecheck` (or equivalent), CI green.
- **Do not execute** until explicitly approved.

### Step 3.8 — Reliability: retry usage in more call sites (AUTO-APPLY only where safe)

- **Allowed**: rlm/core/retry.py, rlm/core/comms_utils.py, LM client call sites under rlm/ that do not change public API
- **Action**: Apply retry_with_backoff only where (a) no API break, (b) documented in failure_modes. Proposal #5 option B.
- **Verification**: `make check`; existing tests must pass.
- **Result**: Same public API; fewer transient failures.

---

## Acceptance checks (verification gates)

After each Phase 3 step:

1. **Lint/format**: `make lint`, `make format`
2. **Tests**: `make test` (Python), `make ext-check` (extension)
3. **IDE smoke**: At least one of (a) MCP gateway starts and responds to a tool list, (b) Extension builds and typechecks
4. **State**: Update docs/orchestrator/state.json (step status: proposed/approved/applied/verified)
5. **Run log**: Append to docs/orchestrator/run_log.md with timestamp, step, actions, verification result

**Done criteria**: Step marked verified in state; run_log entry added; no unplanned file changes.

---

## Idempotency

- **state.json**: active_plan_id, active_plan_path, phases, recommendations (proposed/approved/applied/verified), last_run
- **run_log.md**: Append-only; never delete
- **plan.md**: This file; amend only via explicit Plan amendment (diff); do not implement amendments until plan is updated and approved

---

## Risk and follow-ups

- **Trajectory schema**: Any change to JSONL shape or metadata requires explicit approval and step amendment.
- **Sandbox tightening** (e.g. removing open from REPL): Approval required; high breakage risk.
- **Cancellation**: Mid-completion abort is out of scope until designed and approved.
- **fix_now #11–20**: Filled from bug_backlog; most are doc or optional (run_id in metadata, schema validation, log rotation, cancellation, etc.); implement only when approved and added as numbered steps.

---

## Next actions

1. **Save this plan**: Ensure full content is in docs/orchestrator/plan.md (create file if missing).
2. **Before Build**: Load plan.md; set active_plan_id and active_plan_path in state.json.
3. **Build execution**: Execute steps 3.1 → 3.2 → 3.3 → 3.4 in order; run verification after each; update state and run_log. Skip 3.5–3.7 unless approved; 3.8 only AUTO-APPLY patches.
4. **Stop and replan**: If any action is not in this plan, propose a plan amendment (diff to plan.md) and do not implement until approved.
