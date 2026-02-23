---
description: Structural refactoring audit with tool-assisted detection across six orthogonal dimensions
agent: agent
---

# Refactor Plan — RLM Codebase Structural Audit
**Scope**: Architectural refactoring — module moves, API renames, directory restructuring, duplication elimination, dead code triage, convention alignment, dependency untangling, and API surface cleanup. No backward compatibility — refactored code replaces old code entirely; all call sites must be updated.
**Artifacts**: `docs/orchestrator/refactor-findings.md`, `docs/orchestrator/refactor-backlog.md`
**Idempotency**: Re-running removes implemented items from findings and backlog; unimplemented items are preserved and updated in place

---

## Design Philosophy

This audit identifies structural improvements, not bugs. It is a converging quality pass that:

1. **Uses real tools first** — `ruff`, `ty`, `radon`, `tsc`, `eslint`, `pylance` produce deterministic findings within their domain. Model analysis supplements but never replaces tool output.
2. **Operates across six orthogonal dimensions** — Each dimension has a narrow, well-defined lens. A dimension that finds nothing reports nothing — do not invent issues.
3. **Cites evidence** — Every finding must reference a specific tool output, file:line, import graph, or measurable metric. "This feels wrong" is not a finding.
4. **Requires intelligent dead code triage** — Dead code is not automatically removed. Each piece of dead code must be assessed: is it useful but unconnected? Is it a partial implementation worth completing? Only genuinely obsolete code gets removed.
5. **No backward compatibility** — When a refactoring is proposed, the old pattern is fully replaced. All call sites, imports, tests, and documentation must be updated to the new pattern. No shims, no deprecation wrappers, no dual paths.
6. **Converges** — Each cycle should produce fewer findings than the last. If it doesn't, the detection lens or fix quality has a problem — document that.

---

## Instructions

You are a structural analysis agent. You must NOT modify any source code — only artifact files under `docs/orchestrator/`. After completing the audit, you write findings and backlog directly to disk so the refactor-agent can read and implement changes.

### Startup Checklist (run every invocation)

1. Read `AGENTS.md` — project conventions and architecture
2. Read `docs/orchestrator/state.json` — current state
3. Read `docs/orchestrator/plan.md` — context (amendments may be needed for structural changes)
4. Read `docs/quality/fix_now.md` — existing known issues (do not duplicate)
5. Read `docs/quality/bug_backlog.md` — existing bug list (do not duplicate)
6. Read `docs/orchestrator/research-findings.md` — research context (if exists)
7. Read `docs/orchestrator/research-backlog.md` — do not duplicate research items (if exists)
8. Read `docs/orchestrator/debug-findings.md` — debug context (if exists; do not duplicate)
9. Read `docs/orchestrator/debug-backlog.md` — do not duplicate debug items (if exists)
10. Read `docs/orchestrator/refactor-findings.md` — previous refactor findings (if exists; remove any completed items, re-audit as needed)
11. Read `docs/orchestrator/refactor-backlog.md` — previous backlog (if exists; extend, don't replace)

---

## Dimension 1 — Code Duplication

Identify near-duplicate logic, copy-paste patterns, and DRY violations across the codebase.

### 1.1 Tool-Assisted Detection

```bash
# Unused imports and variables (ruff F401, F811, F841)
uv run ruff check . --select F401,F811,F841 2>&1

# Find structurally similar blocks across Python files
# Use grep to locate repeated patterns — function signatures, error handling blocks, serialization patterns
grep -rn 'def to_dict' --include='*.py' rlm/ tests/ 2>&1
grep -rn 'def from_dict' --include='*.py' rlm/ tests/ 2>&1
grep -rn 'socket_send\|socket_recv' --include='*.py' rlm/ 2>&1
grep -rn 'def completion' --include='*.py' rlm/clients/ 2>&1
grep -rn 'def execute_code' --include='*.py' rlm/environments/ 2>&1
```

### 1.2 Pattern-Based Detection

Manually inspect for these common duplication patterns:
- **Serialization boilerplate**: `to_dict()`/`from_dict()` implementations that share the same structure — could a base mixin or utility function reduce repetition?
- **Client initialization**: Similar `__init__` patterns across `rlm/clients/*.py` — is there duplicated setup logic?
- **Environment setup**: Similar `setup()`/`load_context()` patterns across `rlm/environments/*.py`
- **Error handling**: Identical try/except blocks repeated across files
- **Socket communication**: Repeated pack/unpack and send/recv patterns
- **Test boilerplate**: Repeated mock setup or assertion patterns in `tests/`

For each finding:
- Quote both duplicate locations (file:line for each)
- Measure the duplicate span (number of lines)
- Propose a specific consolidation strategy (extract function, base class method, utility module, etc.)
- Flag if consolidation would change public API (it must — no backward compat)

### 1.3 TypeScript Duplication

```bash
# Find repeated patterns in extension code
grep -rn 'sendRequest\|handleResponse' --include='*.ts' vscode-extension/src/ 2>&1
grep -rn 'dispose\|Disposable' --include='*.ts' vscode-extension/src/ 2>&1
grep -rn 'interface.*Request\|interface.*Response' --include='*.ts' vscode-extension/src/ 2>&1
```

---

## Dimension 2 — Cohesion and Coupling

Identify modules with mixed responsibilities, tangled dependencies, and circular imports.

### 2.1 Import Graph Analysis

```bash
# Map all intra-project imports to identify coupling hotspots
grep -rn '^from rlm\.' --include='*.py' rlm/ 2>&1 | sort
grep -rn '^import rlm\.' --include='*.py' rlm/ 2>&1 | sort

# Identify TYPE_CHECKING guards (existing decoupling)
grep -rn 'TYPE_CHECKING' --include='*.py' rlm/ 2>&1

# Find circular import candidates — modules that import each other
# Build a directed graph from the grep output above and check for cycles
```

### 2.2 Module Responsibility Audit

For each module under `rlm/`, assess whether it has a single, clear responsibility:

| Module | Expected Responsibility | Check |
|--------|------------------------|-------|
| `rlm/core/rlm.py` | RLM completion loop only | Does it also handle environment setup, logging, or client management? |
| `rlm/core/lm_handler.py` | TCP server for LM requests | Does it also do request parsing or response formatting? |
| `rlm/core/comms_utils.py` | Socket protocol utilities | Does it also define business logic types? |
| `rlm/core/types.py` | Data types and serialization | Does it also contain business logic? |
| `rlm/utils/parsing.py` | Code block extraction | Does it also handle prompt formatting? |
| `rlm/utils/prompts.py` | Prompt templates | Does it depend on runtime state? |
| `rlm/mcp_gateway/server.py` | MCP server dispatch | Does it also contain tool implementations? |
| `vscode-extension/src/orchestrator.ts` | Chat-to-backend boundary | Does it also handle UI, settings, or process management? |
| `vscode-extension/src/backendBridge.ts` | Process lifecycle | Does it also handle message routing or business logic? |

For each module that mixes concerns:
- List the distinct responsibilities found (with file:line evidence)
- Propose a specific split: which functions/classes move where
- Estimate the number of call sites that must be updated

### 2.3 Dependency Direction

Check that dependencies flow in the correct direction:
- `core/` should not import from `clients/`, `environments/`, or `mcp_gateway/`
- `clients/` should only import from `core/` (types, base classes)
- `environments/` should only import from `core/` (types, base classes, comms)
- `mcp_gateway/` can import from `core/` and `utils/`
- `utils/` should not import from `clients/` or `environments/`
- `vscode-extension/src/` — check for architecture layer violations per `docs/adr/001-extension-architecture.md`

```bash
# Check for reverse dependencies (e.g., core importing from clients)
grep -rn '^from rlm\.clients' --include='*.py' rlm/core/ 2>&1
grep -rn '^from rlm\.environments' --include='*.py' rlm/core/ 2>&1
grep -rn '^from rlm\.mcp_gateway' --include='*.py' rlm/core/ rlm/clients/ rlm/environments/ 2>&1
grep -rn '^from rlm\.clients' --include='*.py' rlm/utils/ 2>&1
grep -rn '^from rlm\.environments' --include='*.py' rlm/utils/ 2>&1
```

For each violation: cite the exact import line, explain why it's in the wrong direction, and propose a resolution (move code, introduce an interface, use dependency injection).

---

## Dimension 3 — Convention Drift

Identify code that does not follow the patterns documented in `AGENTS.md`.

### 3.1 Naming Convention Audit

```bash
# Find methods that don't use snake_case (Python)
grep -rn 'def [a-z]*[A-Z]' --include='*.py' rlm/ tests/ 2>&1

# Find classes that don't use PascalCase (Python)
grep -rn '^class [a-z]' --include='*.py' rlm/ tests/ 2>&1

# Find constants that aren't UPPER_CASE (look for module-level assignments that should be constants)
grep -rn '^[a-z_]* = .*#.*const\|^[a-z_]* = .*#.*CONST' --include='*.py' rlm/ 2>&1
```

### 3.2 Typing Convention Audit

```bash
# Type errors (ty)
uv run ty check --output-format=concise 2>&1

# Find functions missing return type annotations
grep -rn 'def .*):$' --include='*.py' rlm/ 2>&1 | grep -v '->.*:$' | grep -v '__pycache__'

# Find bare except or overly broad exception handling
grep -rn 'except:$\|except Exception:$' --include='*.py' rlm/ 2>&1

# Find Any usage
grep -rn 'Any' --include='*.py' rlm/ 2>&1 | grep -v '__pycache__' | grep -v 'TYPE_CHECKING'

# Find type: ignore without justification
grep -rn 'type: ignore' --include='*.py' rlm/ 2>&1
```

Use Pylance MCP tools for deeper type analysis:
1. Call `pylanceImports` to check for unresolved or incorrectly typed imports
2. Call `pylanceSyntaxErrors` for files with complex type annotations
3. Call `pylanceDocuments` to get a module-level overview of symbols and their types

### 3.3 Error Handling Convention Audit

The project convention is "fail fast, fail loud." Check for:
- Silent fallbacks (catch-and-ignore patterns)
- Defensive programming (excessive None checks where the type should guarantee non-None)
- Missing error context (bare `raise` without message, generic error messages)

```bash
# Silent swallowing — except blocks that pass or only log
grep -rn -A2 'except.*:' --include='*.py' rlm/ 2>&1 | grep -B1 'pass$\|continue$\|return None$'

# Functions returning None where they should raise
grep -rn 'return None' --include='*.py' rlm/ 2>&1
```

### 3.4 Dataclass Convention Audit

The project uses `@dataclass` with manual `to_dict()`/`from_dict()` — no Pydantic. Check:
- Are all data-carrying classes `@dataclass`?
- Do all dataclasses have `to_dict()` and `from_dict()`?
- Are there any Pydantic models or `dataclasses_json` imports?
- Are mutable default arguments used? (Must use `field(default_factory=...)`)

```bash
grep -rn '@dataclass' --include='*.py' rlm/ 2>&1
grep -rn 'class.*:' --include='*.py' rlm/core/types.py rlm/core/comms_utils.py 2>&1
grep -rn 'pydantic\|dataclasses_json\|BaseModel' --include='*.py' rlm/ 2>&1
grep -rn 'def to_dict\|def from_dict' --include='*.py' rlm/ 2>&1
```

### 3.5 TypeScript Convention Audit

```bash
# Check for any usage (ESLint should catch this, but verify)
cd vscode-extension && npx tsc --noEmit 2>&1
cd vscode-extension && npx eslint src/ --max-warnings 0 2>&1

# Find `as` type assertions (should be documented)
grep -rn ' as ' --include='*.ts' vscode-extension/src/ 2>&1 | grep -v 'import.*as'

# Find console.log (should use logger)
grep -rn 'console\.\(log\|warn\|error\)' --include='*.ts' vscode-extension/src/ 2>&1
```

---

## Dimension 4 — Dead Code Triage

**Critical**: Dead code is not automatically marked for deletion. Each piece of dead code must be intelligently assessed.

### 4.1 Tool-Assisted Dead Code Detection

```bash
# Unused imports (ruff F401)
uv run ruff check . --select F401 2>&1

# Unused variables (ruff F841)
uv run ruff check . --select F841 2>&1

# Unused function arguments (ruff ARG — if enabled, otherwise manual)
grep -rn 'def.*self.*unused\|def.*_[a-z]' --include='*.py' rlm/ 2>&1

# Functions defined but never called (search for function defs, then grep for call sites)
# Focus on rlm/ source — skip tests (they are call sites)
grep -rn '^    def \|^def ' --include='*.py' rlm/ 2>&1
```

### 4.2 Comprehensive Dead Code Search

For each function, class, or module-level symbol in `rlm/`:
1. Search for all call sites across `rlm/`, `tests/`, `vscode-extension/python/`, and `scripts/`
2. Classify the symbol into one of:
   - **Active**: Has call sites in production code — leave as-is
   - **Test-only**: Called only from tests — may indicate it's testing internal behavior that should be private, but keep it
   - **Unreachable**: No call sites anywhere — candidate for triage
   - **Partially implemented**: Has a function body that is incomplete (e.g., `pass`, `...`, `NotImplementedError`) — candidate for completion

### 4.3 Dead Code Intelligence Assessment

For each **unreachable** symbol, perform this assessment before recommending removal:

1. **Is it useful but unconnected?**
   - Does the code implement something described in `AGENTS.md`, the paper, or upstream?
   - Would connecting it to the call graph add value?
   - If YES → recommend **implementing/connecting** it (create an RT item with category `dead-code-activate`)

2. **Is it a partial implementation worth completing?**
   - Does it implement a feature that's in the research backlog or plan?
   - Is the implementation > 50% complete?
   - If YES → recommend **completing** it (create an RT item with category `dead-code-complete`)

3. **Is it already implemented differently elsewhere?**
   - Search for similar functionality in other modules
   - If YES → recommend **removal** (create an RT item with category `dead-code-remove`)

4. **Is it genuinely obsolete?**
   - Was it part of an old design that has been superseded?
   - Does it reference deprecated APIs or removed modules?
   - If YES → recommend **removal** (create an RT item with category `dead-code-remove`)

### 4.4 TypeScript Dead Code

```bash
# Unused exports/imports — tsc and eslint should catch some
cd vscode-extension && npx tsc --noEmit 2>&1

# Find exported symbols and check for consumers
grep -rn 'export ' --include='*.ts' vscode-extension/src/ 2>&1
```

Apply the same intelligence assessment (4.3) to TypeScript dead code.

---

## Dimension 5 — API Surface Hygiene

Identify inconsistent signatures, missing abstractions, leaky implementation details, and public API surface issues.

### 5.1 Public API Inventory

Build a map of the public API surface:

```bash
# Module-level exports
grep -rn '__all__' --include='*.py' rlm/ 2>&1

# Public functions and classes (not prefixed with _)
grep -rn '^def [a-z]\|^class [A-Z]' --include='*.py' rlm/__init__.py rlm/clients/__init__.py rlm/environments/__init__.py 2>&1

# Factory functions
grep -rn 'def get_client\|def get_environment' --include='*.py' rlm/ 2>&1
```

### 5.2 Signature Consistency

For related groups of functions, check that signatures are consistent:
- All `BaseLM` subclasses: `completion()`, `acompletion()`, `get_usage_summary()`, `get_last_usage()` — do they all have the same parameter names, types, and return types?
- All environment subclasses: `setup()`, `load_context()`, `execute_code()`, `cleanup()` — same check
- All `to_dict()`/`from_dict()` methods: consistent patterns?

For each inconsistency:
- Quote both signatures (file:line)
- Explain what the canonical signature should be
- List all files that must change

### 5.3 Abstraction Quality

Check for:
- **Leaky abstractions**: Implementation details exposed in public APIs (e.g., socket addresses in public method signatures, internal state in return types)
- **Missing abstractions**: Groups of related functions that should be a class, or parameters that should be a config object
- **Over-abstraction**: Abstract base classes with only one implementation (unless documented as extension points)

### 5.4 Extension TypeScript API

```bash
# Check exported types and interfaces
grep -rn 'export interface\|export type\|export class\|export function\|export const' --include='*.ts' vscode-extension/src/ 2>&1
```

Verify that:
- Types shared between modules are consistent
- No internal implementation types are exported
- The extension's public API (commands, settings, activation events) matches `package.json`

---

## Dimension 6 — Test Structure

Identify improvements to test organization, mock patterns, and assertion quality.

### 6.1 Test Organization Audit

```bash
# List all test files and their structure
find tests/ -name '*.py' -exec grep -l 'class Test\|def test_' {} \;

# Check test-to-source mapping — each rlm/ module should have corresponding tests
ls rlm/core/*.py | sed 's|rlm/||;s|\.py||;s|/|_|g' | while read mod; do
  echo "$mod: $(find tests/ -name "*${mod}*" 2>/dev/null | head -1 || echo 'NO TEST FILE')"
done

# Check for test files with no test functions
find tests/ -name '*.py' -exec grep -L 'def test_' {} \;
```

### 6.2 Mock Pattern Audit

The project pattern is `tests/mock_lm.py` + `unittest.mock.patch`, with direct object creation (no pytest fixtures). Check for:
- Inconsistent mock patterns across test files
- Tests that create real external connections instead of mocking
- Mock objects that are too tightly coupled to implementation details
- Fixtures being used (against convention)

```bash
# Find fixture usage (against convention)
grep -rn '@pytest.fixture\|@fixture' --include='*.py' tests/ 2>&1

# Find mock patterns
grep -rn 'mock_lm\|Mock\|patch\|MagicMock' --include='*.py' tests/ 2>&1

# Find tests making real network calls
grep -rn 'requests\.\|urllib\.\|httpx\.\|aiohttp\.' --include='*.py' tests/ 2>&1
```

### 6.3 Assertion Quality

Check for:
- Weak assertions (`assert result` instead of `assert result == expected`)
- Missing assertions in test functions (test runs code but doesn't verify anything)
- Overly brittle assertions (asserting on implementation details rather than behavior)

```bash
# Tests with no assert statement
for f in tests/test_*.py; do
  count=$(grep -c 'assert ' "$f" 2>/dev/null || echo 0)
  tests=$(grep -c 'def test_' "$f" 2>/dev/null || echo 0)
  if [ "$count" -lt "$tests" ]; then
    echo "LOW ASSERTIONS: $f ($count asserts vs $tests test functions)"
  fi
done
```

### 6.4 Extension Test Structure

```bash
# Check extension test coverage
find vscode-extension/ -name '*.test.*' -o -name '*_test.*' 2>/dev/null
grep -rn 'describe\|it(\|test(' --include='*.ts' --include='*.js' vscode-extension/ 2>&1
```

---

## Limitations (document explicitly in artifact)

State these limits in the findings artifact header:
1. This audit cannot find runtime-only issues, race conditions, or environment-specific failures
2. Dead code detection relies on static analysis — dynamically dispatched calls (string-based, reflection) may create false positives
3. Cohesion assessment involves subjective judgment — tool output provides structure, but responsibility boundaries require interpretation
4. API surface analysis does not cover backward compatibility (by design — no backward compat is a project decision)
5. Duplication detection uses grep and manual comparison, not AST-level clone detection
6. Some refactoring items may have cascading effects that are not fully enumerable upfront — the refactor-agent must track exposure during implementation

---

## Artifact Generation

Write both artifact files directly to disk. If previous versions exist, merge: preserve unimplemented items, remove completed items, add new findings.

### Write `docs/orchestrator/refactor-findings.md`

Write the following structure to disk:

```markdown
# Refactor Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Audit Limitations
<!-- State what this audit can and cannot find — see Limitations section above -->

## Dimension 1 — Code Duplication
### Python Duplication
### TypeScript Duplication
### Consolidation Opportunities

## Dimension 2 — Cohesion and Coupling
### Import Graph Issues
### Module Responsibility Violations
### Dependency Direction Violations

## Dimension 3 — Convention Drift
### Naming Violations
### Typing Violations
### Error Handling Violations
### Dataclass Convention Violations
### TypeScript Convention Violations

## Dimension 4 — Dead Code Triage
### Dead Code to Activate (useful but unconnected)
### Dead Code to Complete (partial implementations)
### Dead Code to Remove (obsolete or duplicated)
### Dead Code Assessment Summary

## Dimension 5 — API Surface Hygiene
### Signature Inconsistencies
### Leaky Abstractions
### Missing Abstractions
### Over-Abstractions

## Dimension 6 — Test Structure
### Organization Gaps
### Mock Pattern Inconsistencies
### Assertion Quality Issues
### Extension Test Gaps
```

### Write `docs/orchestrator/refactor-backlog.md`

Write the following structure to disk:

```markdown
# Refactor Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Consumed by: refactor-agent.prompt.md -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Priority 1 — Structural Integrity (coupling violations, dependency direction, circular imports)
<!-- Issues that affect the ability to reason about and maintain the codebase -->

## Priority 2 — Convention Alignment (naming, typing, error handling, dataclass patterns)
<!-- Drift from AGENTS.md conventions that makes the codebase inconsistent -->

## Priority 3 — Duplication Elimination (DRY violations, boilerplate consolidation)
<!-- Copy-paste patterns and repeated logic that should be consolidated -->

## Priority 4 — Dead Code Resolution (activate, complete, or remove)
<!-- Dead code items after intelligent triage — each with a specific resolution -->

## Priority 5 — API Surface Cleanup (signature consistency, abstraction quality)
<!-- Public API improvements that make the codebase more coherent -->

## Priority 6 — Test Structure Improvements (organization, mocks, assertions)
<!-- Test quality improvements that increase maintainability -->
```

Each backlog item must have:
- **ID**: `RT-{NNN}` (sequential)
- **Title**: Short descriptive title
- **Category**: `duplication` | `cohesion` | `coupling` | `convention` | `dead-code-remove` | `dead-code-activate` | `dead-code-complete` | `api-surface` | `test-structure`
- **Evidence**: Exact tool output or code reference (file:line for both sides of duplication, etc.)
- **Severity**: Critical | High | Medium | Low
- **File(s)**: Exact file paths affected
- **Line(s)**: Exact line numbers
- **Description**: What is wrong and what the refactored code should look like
- **Migration scope**: List of all call sites, imports, and tests that must be updated (since no backward compat)
- **Test requirement**: What test must pass (or be added) to verify the refactoring
- **Depends on**: Other RT-IDs, DB-IDs, or RF-IDs

---

## Constraints

1. **No source code changes** — only write to `docs/orchestrator/refactor-findings.md` and `docs/orchestrator/refactor-backlog.md`
2. **Evidence required** — every finding must cite a tool error, file:line, or specific code snippet; narrative-only findings are not acceptable
3. **Remove completed** — when a finding has been fully refactored, exclude it from the artifacts
4. **No duplication** — check `docs/quality/fix_now.md`, `docs/quality/bug_backlog.md`, `docs/orchestrator/debug-backlog.md`, and `docs/orchestrator/research-backlog.md` before adding items; cross-reference with existing IDs
5. **Respect existing plan scope** — the canonical plan says major refactors are out of scope; if a refactoring requires a plan amendment, note it in the backlog item as `⚠️ REQUIRES PLAN AMENDMENT` but still record the item
6. **Dead code intelligence** — never recommend removal without first checking if the code is useful, partially implemented, or implemented elsewhere. Document the assessment in the finding.
7. **No backward compatibility** — every refactoring item must include full migration scope (all call sites, imports, tests to update)
8. **Do not invent findings** — if a dimension produces zero issues, report "no issues found" for that dimension
9. **Acknowledge limits** — include the Limitations section in findings; do not claim exhaustive coverage
10. **Verification**: After writing artifacts, read them back and list line counts, dimension-by-dimension summary, and total item count
