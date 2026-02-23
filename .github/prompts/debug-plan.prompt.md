---
description: Tool-assisted codebase quality audit with orthogonal detection passes
agent: agent
---

# Debug Plan — RLM Codebase Quality Audit
**Scope**: Tool-assisted structural quality audit using orthogonal detection passes
**Artifacts**: `docs/orchestrator/debug-findings.md`, `docs/orchestrator/debug-backlog.md`
**Idempotency**: Re-running removes implemented items from findings and backlog; unimplemented items are preserved and updated in place

---

## Design Philosophy

This audit is **not** a comprehensive bug detector. It is a structured, converging quality pass that:

1. **Uses real tools first** — `ruff`, `ty`, `tsc`, `eslint`, `pytest`, `pylance` produce deterministic, exhaustive findings within their domain. Model analysis supplements but never replaces tool output.
2. **Separates concerns into orthogonal passes** — Each pass has a narrow, well-defined lens. A pass that finds nothing reports nothing — do not invent issues.
3. **Cites evidence** — Every finding must reference a specific tool error, line number, or concrete code snippet. Narrative-only findings ("this looks complex") are not actionable.
4. **Acknowledges limits** — Static reading cannot find runtime bugs, race conditions, or configuration-dependent failures. This audit targets structural and type-level issues, not behavioral correctness.
5. **Converges** — Each cycle should produce fewer findings than the last. If it doesn't, the detection lens or fix quality has a problem — document that.

---

## Instructions

You are a quality analyst. You must NOT modify any source code — only artifact files under `docs/orchestrator/`. After completing the audit, you write findings and backlog directly to disk so the debug-agent can read and implement fixes.

### Startup Checklist (run every invocation)

1. Read `AGENTS.md` — project conventions and architecture
2. Read `docs/orchestrator/state.json` — current state
3. Read `docs/orchestrator/plan.md` — do not contradict existing plan
4. Read `docs/quality/fix_now.md` — existing known issues (do not duplicate)
5. Read `docs/quality/bug_backlog.md` — existing bug list (do not duplicate)
6. Read `docs/orchestrator/research-findings.md` — research context (if exists)
7. Read `docs/orchestrator/research-backlog.md` — do not duplicate research items (if exists)
8. Read `docs/orchestrator/debug-findings.md` — previous audit findings (if exists; remove any completed items, re-audit as needed)
9. Read `docs/orchestrator/debug-backlog.md` — previous backlog (if exists; extend, don't replace)

---

## Pass 1 — Static Tool Errors (deterministic, exhaustive within tooling scope)

Run these commands and collect **every** error or warning. These are the highest-confidence findings.

### 1.1 Python Static Analysis

```bash
# Lint errors (ruff)
uv run ruff check . 2>&1

# Type errors (ty)
uv run ty check --output-format=concise 2>&1

# Test failures + coverage gaps
uv run pytest --tb=short 2>&1
```

For each error:
- Record the exact tool, file, line, error code, and message
- Classify: `lint` | `type-error` | `test-failure`
- Do NOT reinterpret or second-guess tool output — report it verbatim

### 1.2 Python Analysis (Pylance)

Use the Pylance MCP tools to catch issues that ruff and ty miss (environment-aware import resolution, Pylance-specific diagnostics):

1. **Unresolved imports**: Call `pylanceImports` with the workspace root to get all top-level imports and identify any that are unresolved. Cross-reference against installed packages via `pylanceInstalledTopLevelModules`.
2. **Per-file syntax errors**: For each Python source file under `rlm/` and `tests/`, call `pylanceFileSyntaxErrors` to catch syntax-level issues.

For each finding:
- Record the exact tool name, file, line, and message
- Classify: `pylance-import` | `pylance-syntax`
- Only report issues not already caught by ruff or ty — deduplicate across tools

### 1.3 TypeScript Static Analysis

```bash
# Type errors (tsc)
cd vscode-extension && npx tsc --noEmit 2>&1

# Lint errors (eslint)
cd vscode-extension && npx eslint src/ --max-warnings 0 2>&1

# Test failures
node vscode-extension/out/logger.test.js 2>&1
```

Same evidence standard: exact tool, file, line, error code, message.

### 1.4 Evidence Gate

**If tools report zero errors/warnings across all commands and Pylance checks above**, state that explicitly and move to Pass 2. Do NOT invent findings to fill the section.

---

## Pass 2 — Protocol and Schema Consistency

Focused lens: serialization contracts, message formats, and cross-boundary wiring.

### 2.1 Dataclass Round-Trip Audit

For each `@dataclass` in `rlm/core/types.py` and `rlm/core/comms_utils.py`:
- Verify `to_dict()` and `from_dict()` are inverse operations (every field serialized and deserialized)
- Check that field names match between Python and any TypeScript counterpart
- Flag any field present in `__init__` but missing from `to_dict()` or vice versa

### 2.2 Cross-Boundary Message Contracts

Check these specific boundaries:
- **`backendBridge.ts` ↔ `rlm_backend.py`**: JSON message types must match on both sides
- **`LMRequest` / `LMResponse`**: Serialization in `comms_utils.py` must match what `lm_handler.py` expects
- **MCP tool schemas**: Tool parameter types in `rlm/mcp_gateway/tools/` must match documented contracts in `docs/integration/ide_adapter.md`

For each mismatch: cite the exact field name, file, and line on both sides.

### 2.3 Factory Wiring

- Verify `get_client()` in `rlm/clients/__init__.py` has a case for every client class in the directory
- Verify `get_environment()` in `rlm/environments/__init__.py` has a case for every environment class
- Verify all abstract methods from `BaseLM`, `NonIsolatedEnv`, `IsolatedEnv` are implemented in every subclass

Report only concrete gaps — not "could be better" suggestions.

---

## Pass 3 — Incomplete Implementation Detection

Search for patterns indicating unfinished work. This is a focused grep, not open-ended exploration.

```bash
# Run these exact searches:
grep -rn 'TODO\|FIXME\|HACK\|XXX\|STUB\|NotImplementedError\|raise NotImplementedError' \
  --include='*.py' --include='*.ts' rlm/ vscode-extension/src/ tests/
```

For each finding:
1. Quote the exact line and file
2. Classify: **genuine gap** (missing implementation that affects functionality) or **intentional marker** (acknowledged future work)
3. For genuine gaps only: describe what's missing and what the complete implementation should look like
4. For intentional markers: note them but **do not** add to the backlog unless they block current functionality

---

## Pass 4 — Targeted Complexity Hotspots (tool-assisted, not exhaustive)

**Important**: Do NOT attempt to manually count complexity for every function. Instead:

### 4.1 Tool-Assisted Complexity (radon — mandatory)

`radon` is a dev dependency. Run it to get per-function cyclomatic complexity scores:

```bash
# Cyclomatic complexity — flag anything > 8 (grades B and above shown; filter for score > 8)
uv run radon cc rlm/ -s -n B -j 2>&1
uv run radon cc vscode-extension/python/ -s -n B -j 2>&1
```

Interpretation:
- **Allowed**: Cyclomatic complexity ≤ 8 (grades A: 1–5, low B: 6–8)
- **Must fix**: Cyclomatic complexity > 8 (high B: 9–10, grades C–F)
- For every function with complexity > 8, create a backlog item with category `complexity`, the exact score, and a specific simplification strategy (extract helper, early return, lookup table, etc.)
- Use `-j` (JSON output) to get exact numeric scores — do not rely solely on letter grades since the boundary is within grade B

### 4.2 Nesting Depth Detection (tool-assisted + manual)

Deep nesting (> 3 levels inside a function body) is a hard project constraint. Use a two-pronged approach:

**Automated scan** — grep for excessive indentation as a proxy for nesting depth:
```bash
# Python: 4+ nesting levels = 16+ leading spaces inside function bodies
# This catches if/for/while/try/with nesting beyond 3 levels
grep -rn '^                    ' --include='*.py' rlm/ tests/ 2>&1 | head -50

# TypeScript: 4+ nesting levels = 16+ leading spaces (4-space indent) or 4+ tabs
grep -rn '^                    ' --include='*.ts' vscode-extension/src/ 2>&1 | head -50
```

For each match, read the enclosing function to confirm the nesting depth (indentation alone can come from continuation lines or multi-line expressions that are not true nesting).

**Manual hotspot review** — also review these known high-complexity areas:
- `rlm/core/rlm.py` — main completion loop
- `rlm/environments/modal_repl.py` — isolated environment orchestration
- `rlm/environments/docker_repl.py` — container lifecycle
- `rlm/mcp_gateway/server.py` — request dispatch
- `vscode-extension/src/orchestrator.ts` — chat orchestration
- `vscode-extension/src/backendBridge.ts` — process management

For each reviewed function:
- **Only flag if** nesting > 3 levels, length > 50 lines, or parameters > 5
- Propose a **specific** simplification (extract function, early return, parameter object)
- Include the function name and line number

### 4.3 Scope Limit

Do NOT audit every function in the codebase manually. Radon output (4.1) covers all Python files exhaustively for cyclomatic complexity. The nesting scan (4.2) covers all Python and TypeScript files via grep. Manual hotspot review supplements these where tool output warrants closer inspection. Acknowledge that cognitive complexity and runtime behavior are not covered by these structural checks.

---

## Pass 5 — Missing Test Coverage (targeted, not exhaustive)

This pass identifies the most impactful gaps in test coverage — not every untested line.

### 5.1 Cross-Boundary Contract Tests

Check whether tests exist for:
- Serialization round-trips (`to_dict()` → `from_dict()` for all core types)
- `backendBridge.ts` ↔ `rlm_backend.py` message exchange
- MCP tool registration matches documented tool list
- `LMRequest`/`LMResponse` socket protocol

### 5.2 Error Path Tests

Check whether tests exist for:
- Missing API key → `ValueError`
- Socket connection failure → retry behavior
- Max iterations exhaustion → default answer
- Malformed REPL output → graceful handling

### 5.3 Sandbox Boundary Tests

Check whether tests exist for:
- AST validator rejects blocked patterns
- Safe builtins exclude dangerous functions
- Path traversal rejection in `PathValidator`

For each gap: document what test should exist, which file it should live in, and what it should assert. **Do not mark as a bug** — mark as `test-gap` category.

---

## Limitations (document explicitly in artifact)

State these limits in the findings artifact header:
1. This audit cannot find runtime-only bugs, race conditions, or environment-specific failures
2. Complexity metrics use radon (cyclomatic complexity) and grep-based nesting detection — these are structural proxies, not cognitive complexity
3. This audit does not verify behavioral correctness — only structural and type-level properties
4. Findings from this pass have `Recall = (tool coverage) × (targeted review coverage)` — not 100%
5. Some issues may only surface after fixes change the codebase (regression exposure)

---

## Artifact Generation

Write both artifact files directly to disk. If previous versions exist, merge: preserve unimplemented items, remove completed items, add new findings.

### Write `docs/orchestrator/debug-findings.md`

Write the following structure to disk:

```markdown
# Debug Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Audit Limitations
<!-- State what this audit can and cannot find — see Limitations section above -->

## Pass 1 — Static Tool Errors
### Python (ruff)
<!-- Verbatim tool output: file, line, code, message -->
### Python (ty)
### Python (pylance — imports)
### Python (pylance — syntax)
### Python (pytest failures)
### TypeScript (tsc)
### TypeScript (eslint)
### TypeScript (test failures)

## Pass 2 — Protocol and Schema
### Dataclass Round-Trip Issues
### Cross-Boundary Mismatches
### Factory Wiring Gaps

## Pass 3 — Incomplete Implementations
### Genuine Gaps (must fix)
### Intentional Markers (document only)

## Pass 4 — Complexity Hotspots
### Tool Output (radon — cyclomatic complexity > 8)
### Nesting Depth Violations (> 3 levels)
### Manual Hotspot Review

## Pass 5 — Missing Test Coverage
### Cross-Boundary Contract Tests
### Error Path Tests
### Sandbox Boundary Tests
```

### Write `docs/orchestrator/debug-backlog.md`

Write the following structure to disk:

```markdown
# Debug Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Consumed by: debug-agent.prompt.md -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Priority 1 — Tool Errors (deterministic, must fix)
<!-- ruff errors, ty errors, pylance errors, tsc errors, eslint errors, test failures -->

## Priority 2 — Protocol/Schema Mismatches
<!-- Cross-boundary contract violations, serialization gaps -->

## Priority 3 — Genuine Incomplete Implementations
<!-- TODO/FIXME items that block functionality -->

## Priority 4 — Complexity Reduction
<!-- Only items flagged by tools or clearly over thresholds -->

## Priority 5 — Test Coverage Gaps
<!-- Missing contract tests, error path tests, sandbox tests -->
```

Each backlog item must have:
- **ID**: `DB-{NNN}` (sequential)
- **Title**: Short descriptive title
- **Category**: `tool-error` | `type-error` | `pylance-import` | `pylance-syntax` | `test-failure` | `protocol` | `incomplete` | `complexity` | `test-gap`
- **Evidence**: Exact tool output or code reference (file:line) — not narrative description
- **Severity**: Critical | High | Medium | Low
- **File(s)**: Exact file paths affected
- **Line(s)**: Exact line numbers (not "approximate")
- **Description**: What is wrong and what the fix should look like
- **Test requirement**: What test must pass (or be added) to verify the fix
- **Depends on**: Other DB-IDs or RF-IDs (from research backlog)

---

## Constraints

1. **No source code changes** — only write to `docs/orchestrator/debug-findings.md` and `docs/orchestrator/debug-backlog.md`
2. **Evidence required** — every finding must cite a tool error, line number, or specific code snippet; narrative-only findings are not acceptable
3. **Remove completed** — when a finding has been fully fixed, exclude it from the artifacts
4. **No duplication** — check `docs/quality/fix_now.md` and `docs/quality/bug_backlog.md` before adding items; cross-reference with existing IDs
5. **No duplication with research** — check `docs/orchestrator/research-backlog.md`; reference as `RF-{NNN}` instead of creating `DB-{NNN}`
6. **Respect existing plan** — do not contradict `docs/orchestrator/plan.md`
7. **Do not invent findings** — if a pass produces zero issues, report "no issues found" for that pass
8. **Acknowledge limits** — include the Limitations section in findings; do not claim exhaustive coverage
9. **Verification**: After writing artifacts, read them back and list line counts, pass-by-pass summary, and total item count
