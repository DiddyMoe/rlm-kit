# Debug Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Produced by: .github/prompts/debug-plan.prompt.md -->
<!-- Consumed by: .github/prompts/debug-agent.prompt.md -->
<!-- Last updated: 2026-02-22 18:30:00 -->
<!-- Run 22: Re-audit after DB-146–DB-151 implemented. 3 minor test-gap findings. -->

## Audit Limitations

1. This audit cannot find runtime-only bugs, race conditions, or environment-specific failures
2. Complexity metrics use `radon` (cyclomatic complexity) and grep-based nesting detection — these are structural proxies, not cognitive complexity
3. This audit does not verify behavioral correctness — only structural and type-level properties
4. Findings from this pass have `Recall = (tool coverage) × (targeted review coverage)` — not 100%
5. Some issues may only surface after fixes change the codebase (regression exposure)

## Pass 1 — Static Tool Errors

### Python (ruff)

No errors. `ruff check .` passed clean.

### Python (ty)

8 diagnostics (1 error, 7 warnings). All relate to optional dependencies or redundant casts — none indicate real bugs:

| File | Line | Code | Message | Classification |
|------|------|------|---------|----------------|
| `rlm/clients/litellm.py` | 4 | `error[unresolved-import]` | Cannot resolve imported module `litellm` | Optional dep — `litellm` not installed in dev env; guarded by `pytest.importorskip` in tests |
| `rlm/debugging/graph_tracker.py` | 55 | `warning[possibly-missing-attribute]` | Attribute `DiGraph` may be missing on `ModuleType \| None \| Any` | Optional dep `networkx` — attribute access is runtime-guarded |
| `rlm/debugging/graph_tracker.py` | 185 | `warning[possibly-missing-attribute]` | Attribute `write_graphml` may be missing on `ModuleType \| None \| Any` | Same — runtime guard present |
| `rlm/environments/e2b_repl.py` | 352 | `warning[redundant-cast]` | Value is already of type `Any` | Defensive cast — harmless |
| `tests/test_mcp_gateway_prompts.py` | 131 | `warning[possibly-missing-attribute]` | Member `app` may be missing on module `rlm.mcp_gateway.server` | `app` is conditionally defined when FastAPI is available |
| `tests/test_mcp_gateway_prompts.py` | 171 | `warning[redundant-cast]` | Value is already of type `list[dict[str, Any]]` | Defensive cast — harmless |
| `tests/test_mcp_gateway_prompts.py` | 177 | `warning[redundant-cast]` | Value is already of type `list[dict[str, Any]]` | Defensive cast — harmless |
| `tests/test_mcp_gateway_prompts.py` | 522 | `warning[possibly-missing-attribute]` | Member `app` may be missing on module `rlm.mcp_gateway.server` | Same as line 131 |

**Assessment**: The `litellm` unresolved-import is the only `error`-level diagnostic. It's an optional dependency (`pytest.importorskip("litellm")` guards tests). The `ty` config already uses `--exit-zero`. These are **informational, not actionable** — no backlog items warranted.

### Python (pylance — imports)

All imports resolved. No findings.

### Python (pylance — syntax)

No syntax errors found across 24 key source files checked (`rlm/core/`, `rlm/clients/`, `rlm/environments/`, `rlm/mcp_gateway/server.py`, `rlm/utils/`, `rlm/core/sandbox/ast_validator.py`, `vscode-extension/python/rlm_backend.py`).

### Python (pytest failures)

368 passed, 15 skipped, 0 failures.

### TypeScript (tsc)

No errors. `tsc --noEmit` passed clean.

### TypeScript (eslint)

No errors. `eslint src/ --max-warnings 0` passed clean.

### TypeScript (test failures)

15 passed, 0 failed.

## Pass 2 — Protocol and Schema

### Dataclass Round-Trip Issues

No issues found. All 11 dataclasses (`ModelUsageSummary`, `UsageSummary`, `SnippetProvenance`, `RLMChatCompletion`, `REPLResult`, `CodeBlock`, `RLMIteration`, `RLMMetadata`, `QueryMetadata`, `LMRequest`, `LMResponse`) have consistent `to_dict()`/`from_dict()` round-trips with no field mismatches.

One minor note: `RLMChatCompletion.to_dict()` conditionally omits `metadata` key when `self.metadata is None` (line 176 of `rlm/core/types.py`), making `to_dict(from_dict(d))` not precisely identity when input contains `"metadata": None`. This is **semantically correct** (both represent absent metadata) and does not cause runtime issues.

### Cross-Boundary Mismatches

No issues found across all three boundaries:
- **backendBridge.ts ↔ rlm_backend.py**: All 7 outbound (`configure`, `completion`, `execute`, `llm_response`, `cancel`, `shutdown`, `ping`) and 9 inbound (`ready`, `configured`, `result`, `chunk`, `exec_result`, `progress`, `error`, `llm_request`, `pong`) message types match in field names and structure.
- **LMRequest/LMResponse**: Serialization/deserialization is consistent between `comms_utils.py` and `lm_handler.py`.
- **MCP tool schemas**: All 14 tool names and parameter schemas match between `_TOOL_SPECS` in `server.py` and documented contracts in `docs/integration/ide_adapter.md`.

### Factory Wiring Gaps

No issues found:
- `get_client()` covers all 8 client classes (11 backend names including OpenAI-compatible aliases).
- `get_environment()` covers all 6 environment classes (`local`, `modal`, `docker`, `daytona`, `prime`, `e2b`).
- All abstract methods from `BaseLM` (4 methods: `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`) are implemented in every client subclass.
- All abstract methods from `BaseEnv` (3 methods: `setup`, `load_context`, `execute_code`) are implemented in every environment subclass.

## Pass 3 — Incomplete Implementations

### Genuine Gaps (must fix)

None found.

### Intentional Markers (document only)

All `NotImplementedError` instances are intentional:
- **`rlm/environments/base_env.py`** (9 occurrences, lines 51–110): Abstract method stubs in `NonIsolatedEnv`, `IsolatedEnv`, `BaseEnv` — required by the ABC pattern.
- **`rlm/clients/base_lm.py`** (4 occurrences, lines 21–35): Abstract method stubs in `BaseLM` — same pattern.
- **Isolated environment `load_context()`** (5 occurrences in `modal_repl.py:196`, `e2b_repl.py:323`, `daytona_repl.py:402`, `docker_repl.py:179`, `prime_repl.py:343`): Deliberate "not supported" errors — isolated environments handle context via `setup()`, not `load_context()`.

No `TODO`, `FIXME`, `HACK`, `XXX`, or `STUB` markers found in the codebase.

## Pass 4 — Complexity Hotspots

### Tool Output (radon — cyclomatic complexity > 8)

No functions exceed the threshold. The maximum cyclomatic complexity across the entire Python codebase is **8** (grade B, low end). 14 functions sit at the boundary (complexity = 8):
- `GraphTracker.add_node` (graph_tracker.py:59)
- `GraphTracker.get_statistics` (graph_tracker.py:135)
- `CallHistory.get_statistics` (call_history.py:215)
- `count_tokens` (token_utils.py:148)
- `VerbosePrinter.print_code_execution` (verbose.py:211)
- `LocalREPL.setup` (local_repl.py:84)
- `_serialize_value` (types.py:35)
- `RLM._log_metadata` (rlm.py:123)
- `RLM._spawn_completion_context` (rlm.py:201)
- `_make_tool` (server.py:683)
- `_rpc_tools_call` (server.py:1733)
- `RLMMCPGateway.read_resource` (server.py:424)
- `SearchTools._iter_files` (search_tools.py:82)

All are at the boundary, not exceeding it. Extension Python backend max is 7 (`stdin_reader` in `rlm_backend.py:406`).

### Nesting Depth Violations (> 3 levels)

No violations found. All Python indentation at 20+ spaces is from multi-line expressions (dict literals, function call arguments, string continuations), not control flow nesting. All TypeScript grep returned zero matches. Manual verification of hotspot files confirmed max nesting depth of 3 (at boundary) in `rlm/core/rlm.py:_spawn_completion_context`.

### Manual Hotspot Review

No actionable manual hotspot findings. All previous items (DB-146 through DB-151) verified complete.

## Pass 5 — Missing Test Coverage

### Cross-Boundary Contract Tests

Mostly covered. 3 minor gaps:

1. **`ModelUsageSummary` / `UsageSummary` lack explicit roundtrip tests**: `tests/test_types.py` has separate `test_to_dict` and `test_from_dict` for both classes (lines 60–85 and 90–115), but no composed `from_dict(to_dict(x))` roundtrip assertion. All other 9 dataclasses have explicit roundtrip tests.

2. **Backend bridge protocol lacks shared schema contract**: `tests/test_rlm_backend_protocol.py` (Python) and `vscode-extension/src/backendBridge.protocol.test.ts` (TypeScript) independently verify message shapes, but there is no shared schema definition or test that asserts both sides agree on the complete message catalog. If one side adds/renames a field, the other won't detect the mismatch.

3. **MCP tool names not cross-checked against expected canonical set**: `test_list_tools_matches_declared_tool_specs` in `tests/test_mcp_gateway_prompts.py:154` only verifies internal consistency (published tools match `_TOOL_SPECS`). No test asserts the published tool name set equals an explicit expected set, so documentation drift won't be caught.

### Error Path Tests

All covered:
- Missing API key: `tests/clients/test_api_key_validation.py` — OpenAI, Anthropic, Azure, Portkey, Gemini
- Socket failure → retry: `test_retry.py` + `test_comms_utils.py` — retry logic, connection refused
- Max iterations exhaustion: `test_multi_turn_integration.py` — fallback answer returned
- Malformed REPL output: `test_parsing.py` + `test_local_repl.py` — unclosed parens, bare FINAL, code fences, syntax errors, binary output, timeouts

### Sandbox Boundary Tests

All covered:
- AST validator: `test_sandbox.py` — parametrized over all blocked modules and functions, bypass via `getattr`/subscript
- Safe builtins: `test_local_repl.py` + `test_sandbox.py` — eval/exec/compile blocked, strict vs REPL builtins, `__import__`/`open` in REPL
- Path traversal: `test_path_validator.py` — traversal, outside roots, restricted patterns, symlink escape
