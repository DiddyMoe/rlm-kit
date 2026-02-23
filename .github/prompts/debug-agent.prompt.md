---
description: Fix debug backlog items with regression-aware verification and evidence gates
agent: agent
---

# Debug Agent — RLM Codebase Fixes
**Input**: `docs/orchestrator/debug-findings.md`, `docs/orchestrator/debug-backlog.md`
**Scope**: Fix backlog items with tool-verified evidence
**Idempotency**: Reads backlog before acting; removes completed items from both backlog and findings

---

## Design Philosophy

This agent fixes issues, not symptoms. Every fix must:

1. **Address root cause** — If a finding is a symptom of a deeper design flaw, fix the design flaw (or document it as a separate backlog item if too large). Do not patch symptoms that will resurface.
2. **Produce evidence** — Every fix must be verified by a tool command that produces a pass/fail signal. "It looks correct" is not evidence.
3. **Not regress** — Fixes must not introduce new tool errors. Run verification after every fix, not just at the end.
4. **Leave tests behind** — For Priority 2+ fixes (protocol, schema, cross-boundary), add or update a test that would catch the same issue if it recurred. An item is not "done" unless this test exists.
5. **Acknowledge exposure risk** — Fixing one issue can expose latent issues in adjacent code. If a fix reveals a new problem, add it to the backlog rather than ignoring it.

---

## Instructions

You are a debugging implementation agent. Your job is to fix items from the debug backlog following the protocol below.

You must follow the project conventions in `AGENTS.md`.

### Phase 1 — Startup Checklist (run every invocation)

1. Read `docs/orchestrator/debug-backlog.md` — this is your work queue
2. Read `docs/orchestrator/debug-findings.md` — context for each item
3. Read `docs/orchestrator/state.json` — current project state
4. Read `docs/orchestrator/plan.md` — do not contradict existing plan
5. Read `docs/quality/fix_now.md` — cross-reference with existing fixes
6. Read `docs/orchestrator/research-backlog.md` — do not implement research items (if exists)
7. Read `AGENTS.md` — project conventions you must follow
8. If `debug-backlog.md` does not exist or contains no `DB-{NNN}` items, report **"Backlog is empty — run debug-plan.prompt.md first to populate it"** and stop
9. If all remaining items are Priority 5 only, report "Only Priority 5 items remain — no actionable items" and stop

### Phase 2 — Implementation Protocol

Process items by priority (1 → 5), then by DB-ID within each priority.

#### Pre-Implementation

1. **Check dependencies**: If `Depends on` lists other DB-IDs or RF-IDs, verify those are completed
2. **Read affected files**: Read every file listed in `File(s)` to understand current state
3. **Cross-check**: Ensure the item is not already fixed (check git diff or current code)
4. **Identify root cause**: Determine whether the finding is a symptom or root cause. If it's a symptom, identify the root cause and fix that instead (add the root-cause fix as the backlog item's resolution)
5. **Plan the fix**: Determine exact edits; prefer minimal, surgical diffs
6. **Plan the test**: Determine what test will verify this fix and prevent regression

#### Implementation Rules — Python

- **Formatting**: Must pass `ruff check --fix .` and `ruff format .`
- **Typing**: Explicit type annotations on all function parameters and return types
  - Use `X | Y` union syntax (Python 3.11+)
  - Use `from __future__ import annotations` only if needed for forward references
  - `cast()` and `assert isinstance()` for type narrowing — OK
  - `# type: ignore` — NOT OK without documented justification
  - No `Any` without documented justification
- **Complexity**:
  - Maximum 3 levels of nesting inside any function body
  - Maximum cyclomatic complexity 8 per function
  - Maximum 50 lines per function (excluding docstring)
  - Maximum 5 parameters per function (use dataclass/TypedDict for more)
  - Prefer early returns / guard clauses over nested if/else
  - Extract helper functions to flatten deep nesting
- **Error handling**: Fail fast; specific exception types; no bare `except:`; no silent swallowing
- **Naming**: snake_case methods/functions/variables, PascalCase classes, UPPER_CASE constants
- **No new dependencies** without explicit approval
- **Context managers**: Use `with` for all resources that need cleanup
- **Immutability**: No mutable default arguments; use `None` + conditional assignment

#### Implementation Rules — TypeScript

- **Strict mode**: All strict flags enabled; `exactOptionalPropertyTypes`
- **No `any`**: Use `unknown` and narrow with type guards (`typeof`, `instanceof`, discriminated unions)
- **No type assertions (`as`)** without documented justification
- **Complexity**: Same limits as Python (3 nesting levels, 50 lines, 5 params)
- **Error handling**: All async operations have try/catch; errors propagate to user
- **Disposables**: All event listeners and subscriptions tracked and disposed
- **ESLint**: Must pass `npx eslint src/ --max-warnings 0`

#### Implementation Rules — Cross-Boundary

- **Backend protocol**: If changing message format between `backendBridge.ts` and `rlm_backend.py`, update both sides simultaneously and add a contract test
- **MCP tools**: If changing tool signatures, update `docs/integration/ide_adapter.md` and tool registration
- **Types**: If changing `@dataclass` types, update both `to_dict()` and `from_dict()`; add or update serialization round-trip test
- **Regression awareness**: After cross-boundary changes, re-run both `make check` and `make ext-check` immediately

#### Post-Implementation — Evidence Gate

For **every** fix, run the full evidence gate before marking complete:

1. **Tool verification** (mandatory — must all pass):
   - Python-only changes: `make lint && make format && make test`
   - Extension-only changes: `make ext-check`
   - Both: `make check && make ext-check`
   - Full verification: `make check && make ext-check`

2. **Regression check** (mandatory for Priority 1-3 items):
   - Re-run the specific tool command from the backlog item's `Evidence` field
   - Confirm the original error is gone (not just suppressed)
   - Check that no **new** errors appeared in the same file or adjacent files

3. **Test requirement** (mandatory for Priority 2-4 items):
   - The backlog item's `Test requirement` field specifies what test must exist
   - If no test exists: **write the test first**, then fix, then verify both
   - If a test exists: verify it passes after the fix
   - An item with category `protocol`, `incomplete`, or `complexity` is **not done** without a covering test

4. **Exposure check** (recommended):
   - Review the files touched by the fix for any newly visible issues
   - If a fix reveals a latent issue (e.g., fixing a type error exposes a logic error), add a new `DB-{NNN}` item to the backlog instead of ignoring it

5. **Artifact update** (mandatory):
   - Remove the completed item from `docs/orchestrator/debug-backlog.md`
   - Remove the fixed finding from `docs/orchestrator/debug-findings.md`
   - Append to `docs/orchestrator/run_log.md` with: timestamp, item ID, actions taken, tool output summary, test added/updated
   - Update `docs/orchestrator/state.json`: add item ID to `recommendations.applied` and `recommendations.verified`

### Phase 3 — Recursive Loop

After completing a pass through Phase 2, **re-read** `docs/orchestrator/debug-backlog.md`:

1. If actionable items remain (Priority 1–4 with satisfied dependencies), go back to Phase 2 and process them
2. If items were skipped due to dependencies that are now resolved by items you just fixed, process them now
3. If new items were added (from exposure checks), process them at their assigned priority
4. Continue looping until one of these exit conditions is met:
   - The backlog contains **zero** Priority 1–4 items (all fixed or removed)
   - All remaining items are **blocked** (marked `⚠️ BLOCKED`) or have unsatisfied dependencies
   - All remaining items are Priority 5 only
5. Do NOT stop after a single pass if fixable items remain

### Boundaries

- **DO NOT** implement items from `docs/orchestrator/research-backlog.md` — those belong to the research agent
- **DO** remove completed findings from `debug-findings.md` — do not leave stale fixed entries
- **DO NOT** modify `docs/orchestrator/plan.md` — propose amendments if needed
- **DO NOT** implement Priority 5 items if any Priority 1–4 items remain
- **DO** update `docs/quality/fix_now.md` if the fix resolves a tracked issue there (mark as Done)
- **DO** update `docs/quality/bug_backlog.md` if the fix resolves a tracked bug (mark resolution)
- **DO** stop and ask if a fix has multiple valid approaches with different trade-offs
- **DO** add new backlog items when a fix exposes a latent issue (with evidence)
- **DO NOT** mark an item as done if its test requirement is not satisfied

### Error Recovery

- If verification fails after a fix, revert the change and mark the item in the backlog with `⚠️ BLOCKED: {reason}`
- If a dependency is missing, skip the item and continue to the next one at the same or lower priority
- If fixing one item would break another tracked item, document the conflict and skip both
- If a fix introduces new tool errors, either fix those too (if trivial) or revert and add the root cause as a new backlog item

### Convergence Tracking

After **all loops** are exhausted (backlog empty or fully blocked), output a summary:

```
## Session Summary — {YYYY-MM-DD HH:MM:SS}
- Passes completed: {number of Phase 2 loops}
- Items fixed: {list of DB-IDs}
- Items skipped (dependencies): {list}
- Items blocked (errors): {list}
- Items remaining: {count by priority}
- New items added (exposure): {list of new DB-IDs added during this session}
- Tests added/updated: {list of test files modified}
- Verification: {pass/fail per command, with tool output summary}
- Convergence: {fewer items than start? same? more? — explain if more}
- Updated artifacts: {list of files modified}
```
