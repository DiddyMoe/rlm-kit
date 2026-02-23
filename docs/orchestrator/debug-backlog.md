# Debug Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Produced by: .github/prompts/debug-plan.prompt.md -->
<!-- Consumed by: .github/prompts/debug-agent.prompt.md -->
<!-- Do NOT add research items here; use research-backlog.md instead -->
<!-- Last updated: 2026-02-22 18:30:00 -->
<!-- Run 22: Re-audit after DB-146–DB-151. 3 new test-gap items (DB-152–DB-154). -->

## Priority 1 — Tool Errors (deterministic, must fix)

No tool errors found.

## Priority 2 — Protocol/Schema Mismatches

No protocol or schema mismatches found.

## Priority 3 — Genuine Incomplete Implementations

No incomplete implementations found.

## Priority 4 — Complexity Reduction

No complexity items remain.

## Priority 5 — Test Coverage Gaps

### DB-152: Add roundtrip tests for ModelUsageSummary and UsageSummary
- **Category**: `test-gap`
- **Evidence**: `tests/test_types.py` lines 60–85 (`TestModelUsageSummary`) and 90–115 (`TestUsageSummary`) have separate `test_to_dict` and `test_from_dict` methods but no composed `from_dict(to_dict(x))` roundtrip assertion. All other 9 core dataclasses have explicit roundtrip tests.
- **Severity**: Low
- **File(s)**: `tests/test_types.py`
- **Line(s)**: 57–115
- **Description**: Add `test_roundtrip` methods to `TestModelUsageSummary` and `TestUsageSummary` that construct an instance, call `to_dict()`, then `from_dict()`, and assert all fields match the original. Pattern: `original = ModelUsageSummary(total_calls=10, total_input_tokens=1000, total_output_tokens=500); restored = ModelUsageSummary.from_dict(original.to_dict()); assert restored.total_calls == original.total_calls` (etc. for all fields). Same for `UsageSummary` with nested `ModelUsageSummary`.
- **Test requirement**: New roundtrip tests pass; `make test` passes.
- **Depends on**: None

### DB-153: Add shared backend bridge protocol message catalog assertion
- **Category**: `test-gap`
- **Evidence**: `tests/test_rlm_backend_protocol.py` (Python) and `vscode-extension/src/backendBridge.protocol.test.ts` (TypeScript) independently verify message shapes but have no shared schema definition. If one side adds/renames a field, the other won't detect the mismatch.
- **Severity**: Low
- **File(s)**: `tests/test_rlm_backend_protocol.py`
- **Line(s)**: N/A (new test to add)
- **Description**: Add a test in `tests/test_rlm_backend_protocol.py` that asserts the complete set of expected message types on both the outbound (TS→Python: `configure`, `completion`, `execute`, `llm_response`, `cancel`, `shutdown`, `ping`) and inbound (Python→TS: `ready`, `configured`, `result`, `chunk`, `exec_result`, `progress`, `error`, `llm_request`, `pong`) sides. This serves as a canary — if a message type is added to the Python handler without updating the expected set, the test fails. The TypeScript test file should have a similar canonical set assertion.
- **Test requirement**: New catalog test passes; `make test` passes.
- **Depends on**: None

### DB-154: Add MCP published tool name set assertion
- **Category**: `test-gap`
- **Evidence**: `tests/test_mcp_gateway_prompts.py:154` (`test_list_tools_matches_declared_tool_specs`) verifies internal consistency (published tools match `_TOOL_SPECS`) but does not assert the tool name set equals an explicit canonical list. Documentation drift (adding/removing tools) would not be caught.
- **Severity**: Low
- **File(s)**: `tests/test_mcp_gateway_prompts.py`
- **Line(s)**: 154 (extend existing test class)
- **Description**: Add a test that asserts the set of published MCP tool names (dot-notation, e.g., `rlm.session.create`) equals an explicit expected set containing all 14 tools. When a tool is added or removed, this test forces an explicit update to the expected set, preventing silent drift from documentation. Example: `assert tool_names == {"rlm.session.create", "rlm.session.close", "rlm.complete", "rlm.exec.run", "rlm.fs.list", "rlm.fs.manifest", "rlm.fs.handle.create", "rlm.search.query", "rlm.search.regex", "rlm.span.read", "rlm.chunk.create", "rlm.chunk.get", "rlm.provenance.report", "rlm.roots.set"}`.
- **Test requirement**: New canonical set test passes; `make test` passes.
- **Depends on**: None
