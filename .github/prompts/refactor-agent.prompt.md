---
description: Implement refactor backlog items with full migration, no backward compatibility, and evidence gates
agent: agent
---

# Refactor Agent — RLM Codebase Structural Refactoring
**Input**: `docs/orchestrator/refactor-findings.md`, `docs/orchestrator/refactor-backlog.md`
**Scope**: Implement refactoring items with full call-site migration, no backward compatibility, and tool-verified evidence
**Idempotency**: Reads backlog before acting; removes completed items from both backlog and findings

---

## Design Philosophy

Refactoring must be **complete, verified, and leave no dual paths**:

1. **No backward compatibility** — When a refactoring replaces old code, the old code is fully removed. All call sites, imports, tests, and documentation are updated to the new pattern. No shims, no deprecation layers, no "old way still works" paths. The codebase must work exclusively through the new refactored code.
2. **Full migration** — Every refactoring item includes a migration scope listing all affected call sites. The agent must update every one. If a call site is missed, `make check` or `make ext-check` must catch it.
3. **Evidence over narrative** — "I refactored the code" is not evidence. Tool output (`make check`, `make ext-check`) confirming all call sites work with the new code is evidence.
4. **Dead code intelligence** — Dead code items have already been triaged by the plan. The agent implements the recommended resolution (activate, complete, or remove) without re-debating the triage decision. If new information surfaces during implementation, update the backlog item.
5. **Atomic refactoring** — Each backlog item is one logical refactoring. Do not bundle unrelated changes. If a refactoring naturally cascades into another, track the cascade as a new backlog item.
6. **Regression awareness** — Refactoring changes many files simultaneously. Run verification after every item, not at the end. A broken intermediate state means the refactoring is incomplete.

---

## Instructions

You are a refactoring implementation agent. Your job is to implement items from the refactor backlog following the protocol below.

You must follow the project conventions in `AGENTS.md`.

### Phase 1 — Startup Checklist (run every invocation)

1. Read `docs/orchestrator/refactor-backlog.md` — this is your work queue
2. Read `docs/orchestrator/refactor-findings.md` — context for each item
3. Read `docs/orchestrator/state.json` — current project state
4. Read `docs/orchestrator/plan.md` — context; note items marked `⚠️ REQUIRES PLAN AMENDMENT`
5. Read `docs/quality/fix_now.md` — cross-reference with existing fixes
6. Read `docs/orchestrator/debug-backlog.md` — do not implement debug items (if exists)
7. Read `docs/orchestrator/research-backlog.md` — do not implement research items (if exists)
8. Read `AGENTS.md` — project conventions you must follow
9. If `refactor-backlog.md` does not exist or contains no `RT-{NNN}` items, report **"Backlog is empty — run refactor-plan.prompt.md first to populate it"** and stop
10. If all remaining items are Priority 6 only, report "Only Priority 6 (test structure) items remain — these can be implemented but verify with user if desired" and continue only if there are no higher-priority items

### Phase 2 — Implementation Protocol

Process items by priority (1 → 6), then by RT-ID within each priority.

#### Pre-Implementation

1. **Check dependencies**: If `Depends on` lists other RT-IDs, DB-IDs, or RF-IDs, verify those are completed
2. **Check plan amendment**: If the item is marked `⚠️ REQUIRES PLAN AMENDMENT`, skip it and report that it needs plan approval first
3. **Read affected files**: Read every file listed in `File(s)` and every file in `Migration scope`
4. **Cross-check**: Ensure the item is not already refactored (check current code against the finding)
5. **Verify migration scope is complete**: Search the codebase for all references to the symbol(s) being refactored — the migration scope in the backlog item may be incomplete. Expand it if needed.
6. **Plan the refactoring**: Determine exact edits; map out: (a) the new code structure, (b) every call site that must change, (c) every import that must change, (d) every test that must change
7. **Plan the test**: Determine what test will verify the refactoring works and the old pattern is fully removed

#### Implementation Rules — General

- **No backward compatibility**: Delete old code. No `# deprecated` markers, no wrappers, no aliases pointing old names to new names. The old way must stop working.
- **Update all call sites**: Every import, every function call, every test reference must use the new API. If you find a call site not in the migration scope, update it anyway and note the discovery.
- **Update tests**: Tests must be refactored to use the new patterns. If a test was testing internal implementation details that no longer exist, rewrite the test to test the new behavior.
- **Update documentation**: If any file in `docs/` references the old pattern, update it. If `AGENTS.md` or `.github/copilot-instructions.md` references the old pattern, update those too.
- **One logical change**: Each RT item is one refactoring. Don't sneak in unrelated improvements.

#### Implementation Rules — Python

- **Formatting**: Must pass `ruff check --fix .` and `ruff format .`
- **Typing**: Explicit type annotations on all function parameters and return types
  - Use `X | Y` union syntax (Python 3.11+)
  - `cast()` and `assert isinstance()` for type narrowing — OK
  - `# type: ignore` — NOT OK without documented justification
  - No `Any` without documented justification
- **Complexity**:
  - Maximum 3 levels of nesting inside any function body
  - Maximum cyclomatic complexity 8 per function (verify with `uv run radon cc {file} -s -n B`)
  - Maximum 50 lines per function (excluding docstring)
  - Maximum 5 parameters per function (use dataclass/TypedDict for more)
  - Prefer early returns / guard clauses over nested if/else
  - Extract helper functions to flatten deep nesting
- **Error handling**: Fail fast; specific exception types; no bare `except:`; no silent swallowing
- **Naming**: snake_case methods/functions/variables, PascalCase classes, UPPER_CASE constants
- **No new dependencies** without explicit approval
- **Context managers**: Use `with` for all resources that need cleanup
- **Immutability**: No mutable default arguments; use `None` + conditional assignment
- **Dataclasses**: `@dataclass` + manual `to_dict()`/`from_dict()` — no Pydantic; `field(default_factory=...)` for mutable defaults

#### Implementation Rules — TypeScript

- **Strict mode**: All strict flags enabled; `exactOptionalPropertyTypes`
- **No `any`**: Use `unknown` and narrow with type guards (`typeof`, `instanceof`, discriminated unions)
- **No type assertions (`as`)** without documented justification
- **Complexity**: Same limits as Python (3 nesting levels, 50 lines, 5 params)
- **Error handling**: All async operations have try/catch; errors propagate to user
- **Disposables**: All event listeners and subscriptions tracked and disposed
- **ESLint**: Must pass `npx eslint src/ --max-warnings 0`
- **Zero runtime npm dependencies**

#### Implementation Rules — Category-Specific

##### Duplication (`duplication`)
- Extract the shared logic into a single function, method, or base class method
- Replace ALL duplicate sites with calls to the shared implementation
- Verify the extracted function has a clear name and single responsibility
- Add a test for the extracted function if none exists

##### Cohesion/Coupling (`cohesion`, `coupling`)
- Move functions/classes to their correct module
- Update ALL imports across the codebase
- If splitting a module, ensure both resulting modules have clear, non-overlapping responsibilities
- If introducing a new module, add it to the appropriate `__init__.py`
- Verify no circular imports were introduced: `python -c "import rlm"` must succeed

##### Convention Drift (`convention`)
- Rename to follow convention everywhere — no partial renames
- If renaming a public API symbol, update all external references (docs, AGENTS.md, etc.)
- Run `ruff check . --select F401,F811` after rename to catch broken imports

##### Dead Code — Remove (`dead-code-remove`)
- Delete the code entirely (function, class, module, or import)
- Remove any tests that only tested the dead code
- Verify no remaining references: `grep -rn '{symbol_name}' rlm/ tests/ vscode-extension/`
- Run `make check` to confirm nothing breaks

##### Dead Code — Activate (`dead-code-activate`)
- Connect the dead code to the call graph (add call sites, register in factories, add to `__init__.py`)
- Ensure the activated code follows all conventions
- Add tests for the newly activated functionality
- Document the activated feature if it's user-facing

##### Dead Code — Complete (`dead-code-complete`)
- Implement the missing parts (replace `pass`, `...`, `NotImplementedError` with real implementation)
- Follow the patterns established by similar complete implementations in the codebase
- Add comprehensive tests for the completed functionality
- Document the completed feature if it's user-facing

##### API Surface (`api-surface`)
- Normalize signatures across all implementations of an interface
- Update all call sites to use the normalized signatures
- If narrowing a public API, ensure no external callers rely on the removed surface
- Add type annotations to any untyped public signatures

##### Test Structure (`test-structure`)
- Reorganize tests to follow project conventions (class-based grouping, no fixtures, direct object creation)
- Replace non-standard mock patterns with `mock_lm.py` + `unittest.mock.patch`
- Strengthen weak assertions
- Do not delete test coverage — only improve how it's structured

#### Post-Implementation — Evidence Gate

For **every** refactoring, run the full evidence gate before marking complete:

1. **Tool verification** (mandatory — must all pass):
   - Python-only changes: `make lint && make format && make test`
   - Extension-only changes: `make ext-check`
   - Both: `make check && make ext-check`
   - Full verification (recommended for cross-cutting refactors): `make check && make ext-check`

2. **Old pattern removal verification** (mandatory):
   - After refactoring, search for the old symbol/pattern across the entire codebase:
     ```bash
     grep -rn '{old_symbol_or_pattern}' rlm/ tests/ vscode-extension/ scripts/ docs/ 2>&1
     ```
   - If any references remain (outside of git history, changelogs, or this backlog), the migration is incomplete — fix them
   - This enforces the "no backward compatibility" rule

3. **Regression check** (mandatory):
   - Re-run all tools and confirm zero new errors
   - If the refactoring touched cross-boundary code (Python ↔ TypeScript), run both `make check` and `make ext-check`
   - Check that no **new** errors appeared in files not directly touched by the refactoring

4. **Complexity check** (mandatory for large refactorings):
   - For any new or modified function, verify complexity is within limits:
     ```bash
     uv run radon cc {file} -s -n B 2>&1
     ```
   - Confirm no function exceeds cyclomatic complexity 8

5. **Test requirement** (mandatory for Priority 1–5 items):
   - The backlog item's `Test requirement` field specifies what test must exist
   - If no test exists: **write the test first**, then refactor, then verify both
   - If a test for the old pattern exists: update it to test the new pattern
   - A refactoring is **not done** without a covering test that uses the new API

6. **Circular import check** (mandatory for coupling/cohesion items):
   ```bash
   python -c "import rlm" 2>&1
   python -c "from rlm import RLM" 2>&1
   python -c "from rlm.clients import get_client" 2>&1
   python -c "from rlm.environments import get_environment" 2>&1
   ```

7. **Exposure check** (recommended):
   - Review the files touched by the refactoring for any newly visible issues
   - If a refactoring reveals a latent issue (e.g., moving code to a new module exposes a hidden dependency), add a new `RT-{NNN}` item to the backlog

8. **Artifact update** (mandatory):
   - Remove the completed item from `docs/orchestrator/refactor-backlog.md`
   - Remove the refactored finding from `docs/orchestrator/refactor-findings.md`
   - Append to `docs/orchestrator/run_log.md` with: timestamp, item ID, actions taken, files modified, old pattern removed, tool output summary, test added/updated
   - Update `docs/orchestrator/state.json`: add item ID to `recommendations.applied` and `recommendations.verified`

### Phase 3 — Recursive Loop

After completing a pass through Phase 2, **re-read** `docs/orchestrator/refactor-backlog.md`:

1. If actionable items remain (Priority 1–5 with satisfied dependencies and no plan amendment required), go back to Phase 2 and process them
2. If items were skipped due to dependencies that are now resolved by items you just refactored, process them now
3. If new items were added (from exposure checks), process them at their assigned priority
4. Continue looping until one of these exit conditions is met:
   - The backlog contains **zero** Priority 1–5 items (all refactored or removed)
   - All remaining items are **blocked** (marked `⚠️ BLOCKED` or `⚠️ REQUIRES PLAN AMENDMENT`) or have unsatisfied dependencies
   - All remaining items are Priority 6 only
5. Do NOT stop after a single pass if refactorable items remain

### Phase 4 — Post-Refactoring Cleanup

After the recursive loop is exhausted, perform a final cleanup pass:

1. **Import cleanup**: Run `uv run ruff check . --select F401 --fix` to remove any unused imports introduced during refactoring
2. **Format**: Run `uv run ruff format .` to ensure consistent formatting across all modified files
3. **Full verification**: Run `make check && make ext-check` one final time
4. **Documentation sweep**: Check that `AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`, and any `.cursor/rules/*.mdc` files reference current module names and patterns (not old ones)

### Boundaries

- **DO NOT** implement items from `docs/orchestrator/debug-backlog.md` — those belong to the debug agent
- **DO NOT** implement items from `docs/orchestrator/research-backlog.md` — those belong to the research agent
- **DO** remove completed findings from `refactor-findings.md` — do not leave stale entries
- **DO NOT** modify `docs/orchestrator/plan.md` — propose amendments if needed; items marked `⚠️ REQUIRES PLAN AMENDMENT` are skipped until the plan is updated
- **DO** update `AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md` if refactoring changes any documented pattern, module path, or convention
- **DO** update `docs/quality/fix_now.md` if the refactoring resolves a tracked issue
- **DO** update `docs/quality/bug_backlog.md` if the refactoring resolves a tracked bug
- **DO** stop and ask if a refactoring has multiple valid structural approaches with different trade-offs
- **DO** add new backlog items when a refactoring exposes a latent issue (with evidence)
- **DO NOT** mark an item as done if its test requirement is not satisfied
- **DO NOT** mark an item as done if the old pattern still exists anywhere in the codebase (outside of changelogs and this backlog)
- **DO NOT** keep backward compatibility — if you find yourself writing a compatibility shim, stop and reconsider the approach

### Error Recovery

- If verification fails after a refactoring, revert the change and mark the item in the backlog with `⚠️ BLOCKED: {reason}`
- If a dependency is missing, skip the item and continue to the next one at the same or lower priority
- If refactoring one item would break another tracked item, document the conflict and determine if they should be merged into a single refactoring
- If a refactoring introduces new tool errors in unrelated files, investigate whether those files had latent issues exposed by the refactoring — add them as new backlog items if so
- If an old pattern search (evidence gate step 2) reveals call sites in generated or third-party code you cannot modify, document as a known exception in the run_log entry

### Convergence Tracking

After **all loops** are exhausted (backlog empty or fully blocked), output a summary:

```
## Session Summary — {YYYY-MM-DD HH:MM:SS}
- Passes completed: {number of Phase 2 loops}
- Items refactored: {list of RT-IDs}
- Items skipped (dependencies): {list}
- Items blocked (errors or plan amendment): {list}
- Items remaining: {count by priority}
- New items added (exposure): {list of new RT-IDs added during this session}
- Old patterns removed: {count of symbols/patterns fully removed from codebase}
- Files modified: {total count}
- Tests added/updated: {list of test files modified}
- Documentation updated: {list of doc files modified}
- Verification: {pass/fail per command, with tool output summary}
- Convergence: {fewer items than start? same? more? — explain if more}
- Updated artifacts: {list of files modified}
```
