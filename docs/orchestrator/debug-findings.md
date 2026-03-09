# Debug Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Produced by: .github/prompts/debug-plan.prompt.md -->
<!-- Consumed by: .github/prompts/debug-agent.prompt.md -->
<!-- Last updated: 2026-03-02 -->
<!-- Run 25: Multi-pass deep review (6 passes, all source modules). DB-156 through DB-220. -->

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

All checks passed (exit-zero, concise output). No new diagnostics.

### Python (pytest failures)

435 passed, 0 skipped, 0 failures.

### TypeScript (tsc)

No errors. `tsc --noEmit` passed clean.

### TypeScript (eslint)

No errors. `eslint src/ --max-warnings 0` passed clean.

### TypeScript (test failures)

15 passed, 0 failed.

## Pass 2 — Deep Code Review (6 Module Passes)

### Core Module (`rlm/core/`)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-156 | High | Dead Code | `rlm/core/rlm.py` | 50, 127 | `max_errors` declared and stored but never enforced — no error counting anywhere |
| DB-157 | High | Dead Code | `rlm/core/rlm.py` | 55, 128 | `enable_recursive_subcalls` stored but never checked |
| DB-158 | High | Dead Code | `rlm/core/rlm.py` | 56-57, 129-130 | `on_subcall_start`/`on_subcall_complete` callbacks stored but never invoked |
| DB-159 | Medium | Security | `rlm/core/sandbox/ast_validator.py` + `restricted_exec.py` | — | Blocked module lists diverge: runtime misses 7 modules (`__builtin__`, `builtins`, `imp`, `pkgutil`, `pydoc`, `runpy`, `zipimport`) vs AST validator |
| DB-160 | Medium | Bug | `rlm/core/rlm.py` | 141 | `_cumulative_cost` never resets between `completion()` calls; inflates across calls on same instance |
| DB-161 | Medium | Bug | `rlm/core/lm_handler.py` | 129-141 | Batched response shares single `UsageSummary` from `get_last_usage()` — only last prompt's usage |
| DB-162 | Medium | Bug | `rlm/core/comms_utils.py` | 200-203 | `socket_recv` doesn't handle partial 4-byte length prefix reads |
| DB-163 | Medium | Bug | `rlm/core/rlm.py` | 648-652 | `_default_answer` uses `"role": "assistant"` for a prompt cue — should be `"user"` |
| DB-164 | Medium | Resource | `rlm/core/rlm.py` | 668-681 | `_fallback_answer` creates a new `BaseLM` client without cleanup or budget tracking |
| DB-165 | Medium | Security | `rlm/core/sandbox/restricted_exec.py` | 83-131 | `__getattr__` blocks 9 builtins, `__getitem__` only blocks 6 — `input`/`globals`/`locals` accessible via dict syntax |
| DB-166 | Medium | Bug | `rlm/core/rlm.py` | 622 | `_compact_history` hardcodes `message_history[:2]` assuming [system, assistant] structure |
| DB-167 | Medium | Bug | `rlm/core/lm_handler.py` | 121 | `asyncio.run()` in `_handle_batched` within a thread can conflict with existing event loops |
| DB-168 | Medium | Bug | `rlm/core/lm_handler.py` | 382-398 | `get_usage_summary()` iterates default + other + all clients, but default is already in `self.clients` — potential double-counting |
| DB-169 | Low | Bug | `rlm/core/rlm.py` | 560-574 | Prefix cache key uses `hash()` (non-deterministic across restarts) and collides on same-length histories |
| DB-170 | Low | Dead Code | `rlm/core/sandbox/ast_validator.py` | 61-62 | `BLOCKED_MODULES`/`BLOCKED_FUNCTIONS` frozenset constants exported but never imported anywhere |

### Clients Module (`rlm/clients/`)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-171 | High | Bug | `openai.py`, `anthropic.py`, `azure_openai.py`, `litellm.py` | `__init__` | `last_prompt_tokens`/`last_completion_tokens` not initialized — `AttributeError` before first `completion()` call via `get_last_usage()` |
| DB-172 | High | Bug | `ollama.py` | 196-204 | `get_last_usage()` returns cumulative tokens, not last-call tokens — inflating per-iteration counts |
| DB-173 | High | Performance | `ollama.py` | 164-176 | `acompletion()` blocks event loop with sync `requests.post` — serializes all "concurrent" batch requests |
| DB-174 | Medium | Bug | `azure_openai.py` | 102-106 | `self.kwargs` (temperature, top_p, etc.) silently dropped — never passed to API call |
| DB-175 | Medium | Bug | All clients + `lm_handler.py` | — | Batched `get_last_usage()` returns only last asyncio task's tokens — shared across all batch results |
| DB-176 | Medium | API Misuse | `gemini.py` | 76-85 | System instruction injected as user message instead of native `system_instruction` API param |
| DB-177 | Medium | API Contract | All clients | `completion()` | `model` param not on `BaseLM.completion()` — requires `cast(Any)` hack in `stream_completion()` |
| DB-178 | Medium | Dead Code | All 7 non-vscode clients | `__init__` | `model_total_tokens` dict tracked but never read anywhere |
| DB-179 | Medium | Incomplete | `ollama.py` | 95-98 | Uses `/api/generate` instead of `/api/chat` — flattens message lists, loses multi-turn structure |
| DB-180 | Low | Dead Code | `vscode_lm.py` | 59 | `self._lock = threading.Lock()` created but never used |
| DB-181 | Low | Consistency | `openai.py` | 120-130 | `stream_completion()` skips Prime Intellect `extra_body` check |
| DB-182 | Low | Consistency | `__init__.py` | 73-77 | Docstring says only `['openai']` supported — stale |

### Environments Module (`rlm/environments/`)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-183 | High | Bug | `prime_repl.py` | 612 | `json.loads()` result parsing has no `try/except JSONDecodeError` — crashes on malformed sandbox stdout |
| DB-184 | High | Bug | `daytona_repl.py` | 675-676 | stdout/stderr conflation — same `response.result` assigned to one or the other based on exit code; stderr lost on success, JSON payload lost on failure |
| DB-185 | Medium | Bug | `modal_repl.py` | 244 | Fixed `time.sleep(2)` instead of broker health check — first `execute_code` may fail on cold sandbox |
| DB-186 | Medium | Bug | `prime_repl.py` | 339-343 | `super().__init__` called before `persistent` guard — inconsistent with Docker/Modal/E2B |
| DB-187 | Medium | Bug | `prime_repl.py` | 38 | `load_dotenv()` at module import — contaminates env vars on any `import prime_repl` |
| DB-188 | Medium | Bug | `modal_repl.py`, `prime_repl.py`, `daytona_repl.py`, `e2b_repl.py` | `load_context` | Manual string escaping for `context_payload` — fails on payloads with nested quotes or special chars |
| DB-189 | Medium | Bug | `docker_repl.py` | 237-240 | `pip install` result never checked — failure silently ignored |
| DB-190 | Medium | Incomplete | `daytona_repl.py` | 94-130 | `get_default_image()` duplicates package lists from `constants.py` inline — won't track updates |
| DB-191 | Medium | Race | `local_repl.py` | 406-415 | `_capture_output` replaces process-global `sys.stdout`/`sys.stderr` — multiple instances or threads corrupt output |
| DB-192 | Medium | Security | `local_repl.py` | 454-461 | `except Exception` doesn't catch `SystemExit` — sandbox code can call `sys.exit()` to crash RLM loop |
| DB-193 | Low | Bug | `modal_repl.py`, `prime_repl.py`, `daytona_repl.py`, `e2b_repl.py` | `_poll_broker` | All poll loops silently swallow all exceptions — no logging, no backoff |
| DB-194 | Low | Bug | `local_repl.py` | 273-274 | `_recursive_completion` silently swallows all errors and returns `None` |

### MCP Gateway (`rlm/mcp_gateway/`)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-195 | Critical | Bug | `exec_tools.py` | 64-73 | `RLIMIT_AS` applied to entire process, not just sandbox — never restored after execution |
| DB-196 | Critical | Security | `exec_tools.py` | 156-173 | `setup_runtime_blocking` modifies global `sys.modules` — not thread-safe in HTTP server mode |
| DB-197 | High | Resource | `exec_tools.py` | 87-102 | Timed-out daemon thread continues running indefinitely — no kill mechanism |
| DB-198 | Medium | Bug | `validation.py` | 93-97 | `is_restricted_path` uses substring matching — `"env"` pattern blocks `development/`, `inventory.py`, etc. |
| DB-199 | High | Incomplete | `session.py` + `server.py` | 187-193 | `register_active_request`/`unregister_active_request`/`cancel_by_request_id` are never called from server — MCP cancellation infrastructure exists but is not wired |
| DB-200 | Medium | Protocol | `server.py` | 543-557 | `_COMPLETE_OUTPUT_SCHEMA` marks `answer` as required but error responses omit it |
| DB-201 | Medium | Incomplete | `filesystem_tools.py` | 68-87 | `fs_list` accepts `depth` param but never recurses into subdirectories |
| DB-202 | Medium | Resource | `handles.py` | 72-92 | `_chunks` dict grows unbounded — no size limit, no eviction, no session-scoped cleanup |
| DB-203 | Medium | Resource | `session.py` | 117-120 | Session close doesn't clean up associated handles or chunks |
| DB-204 | Medium | Resource | `server.py` | 1268-1277 | `_sampling_create_message` creates `LMHandler` (TCP server) per call without cleanup |
| DB-205 | Medium | Bug | `server.py` | 535-536 | Two global gateway variables (`gateway` vs `gateway_instance`) — `_rpc_completion_complete` only checks `gateway_instance`, broken in stdio mode |
| DB-206 | Medium | Bug | `span_tools.py` | 154-158 | Span size check off-by-one: `end_line - start_line` undercounts by 1, allows reading 201 lines when max is 200 |
| DB-207 | Medium | Bug | `filesystem_tools.py` | 64-69 | `relative_to()` raises `ValueError` if file is under an `allowed_root` outside `repo_root` |
| DB-208 | Medium | Bug | `server.py` | — | `_stream_events`/`_pending_elicitations` dicts accumulate per-session entries, never cleaned |
| DB-209 | Low | Dead Code | `server.py` | 246-248 | `_resolve_repo_root` tries to import nonexistent `path_utils` module — always falls through |
| DB-210 | Low | Dead Code | `search_scorer.py` | 94-129 | `score_search_results` function defined but never imported/called |

### VS Code Extension (`vscode-extension/`)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-211 | High | Race | `rlm_backend.py` | 424-428 | `completion`/`execute` run in threads without shared `STATE` locking — concurrent calls corrupt `current_progress_nonce`, `cancel_requested` |
| DB-212 | Medium | Bug | `extension.ts` | 31-41 | `KNOWN_BACKENDS` missing `"ollama"` — can't set/clear API keys |
| DB-213 | Medium | Dead Code | `rlm_backend.py` | 168, 187 | `max_output_chars` stored but never forwarded to `RLMConfig` |
| DB-214 | Medium | Security | `rlm_backend.py` | 343-349 | `handle_execute` creates unsandboxed `LocalREPL` when no RLM instance exists |
| DB-215 | Medium | Security | `backendBridge.ts` | 464-470 | `buildChildEnv` doesn't block `*_KEY` suffix — `OPENAI_API_KEY` etc. leaks to child |
| DB-216 | Medium | Bug | `rlm_backend.py` | 232-234 | `get_or_create_rlm()` ignores `persistent` flag changes after first creation |
| DB-217 | Medium | Race | `rlmParticipant.ts` | 568-583 | `ensureBackend()` TOCTOU — concurrent calls create orphan Python processes |
| DB-218 | Low | Bug | `extension.ts` | 67-75 | Every config change restarts backend — even non-backend settings like `logLevel` |

### Utils, Logger, Debugging

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-219 | High | Bug | `rlm/utils/parsing.py` | 150-153 | `_extract_final_payload` regex DOTALL + greedy `(.*)` over-matches across lines — corrupts FINAL() capture when commentary follows |
| DB-220 | Medium | Dead Code | `rlm/utils/token_counter.py` | entire | All 4 functions unused — `rlm/core/rlm.py` imports from `token_utils.py` instead |
| DB-221 | Low | Dead Code | `rlm/utils/parsing.py` | 107-111 | `check_for_final_answer` legacy wrapper never called anywhere |

## Test Coverage Gaps

| Source Module | Coverage | Key Gap |
|---|---|---|
| `rlm/logger/verbose.py` | **None** | 426 lines, 14 public methods, 0 functional tests |
| `rlm/utils/rlm_utils.py` | **None** | `filter_sensitive_keys` has 0 behavioral tests |
| `rlm/utils/prompts.py` / `build_user_prompt` | **None** | 4 branches untested (iteration>0, context_count>1, history_count>0, all) |
| `rlm/environments/exec_script_templates.py` | **None** | Template generation logic entirely untested |
| Isolated environments (Docker, Modal, Prime, Daytona, E2B) | Config only | No execution tests (mock-based tests would be valuable) |
| All `rlm/clients/` `acompletion()` | **None** | No per-client async method tests |

## Pass 3 — Focused Orthogonal Audit (Run 26, 6 passes)

<!-- Run 26: Cross-boundary, concurrency, security, error handling, state, API contracts -->
<!-- DB-222 through DB-261 -->

### Security — Sandbox Escape (Critical)

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-222 | Critical | Sandbox Escape | `rlm/core/sandbox/ast_validator.py` + `safe_builtins.py` | — | Object subclass hierarchy escape: `object.__subclasses__()` → `__init__.__globals__` → `os.system()`. AST validator has no checks for `__subclasses__`, `__bases__`, `__globals__`, `__init__` dunder chains. `object`, `type`, `getattr`, `hasattr` all provided in safe builtins |
| DB-223 | Critical | Sandbox Escape | `rlm/core/sandbox/restricted_exec.py` | 65-79, 98 | `RestrictedBuiltins._safe` accessible via direct attribute access (bypasses `__getattr__`); `__setattr__` allows setting any `_`-prefixed attribute. Attacker can replace `_safe` dict to restore full builtins |
| DB-224 | Critical | Protocol | `vscode-extension/python/rlm_backend.py` | 123-155 | `ProgressLogger` missing `clear_iterations()` and `get_trajectory()` methods required by `RLM.completion()` at `rlm.py:302,513`. Will crash with `AttributeError` on every VS Code extension completion |

### Security — Additional Vectors

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-225 | High | Security | `rlm/core/sandbox/ast_validator.py` | 141-175 | No AST checks for dunder attribute chains (`__class__`, `__bases__`, `__subclasses__`, `__globals__`, `__code__`, `__mro__`). Root cause enabling DB-222 |
| DB-226 | High | Security | `rlm/environments/local_repl.py` | 85-90, 456 | No AST validation on REPL code; `__import__` and `open` available. LLM-generated code can `import os; os.environ` to extract API keys and exfiltrate via network |
| DB-227 | Medium | Security | `rlm/environments/local_repl.py` | 93-102 | Bound methods (`llm_query.__self__`) expose full `LocalREPL` instance — attacker can modify `execution_timeout_seconds`, access `lm_handler_address`, read `globals`/`locals` |
| DB-228 | Medium | Security | `rlm/environments/exec_script_templates.py` | 58-73 | `dill.load()` for state persistence uses predictable paths (`/tmp/rlm_state.dill`). REPL code in iteration N can write malicious pickle to poison iteration N+1 |
| DB-229 | Low | Security | `rlm/core/sandbox/restricted_exec.py` | 62-70 | `vars(__builtins__)` reveals `_safe` attribute, making DB-223 trivially discoverable by sandbox code |

### Cross-Boundary Contracts

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-230 | Medium | Schema | `rlm/mcp_gateway/tools/complete_tools.py` + `server.py` | 72-84, 547, 680 | `elicitation_request` key in tool result vs `elicitation` in `_COMPLETE_OUTPUT_SCHEMA`. Schema field always null; actual data goes to undeclared key |
| DB-231 | Medium | Schema | `rlm/mcp_gateway/tools/complete_tools.py` | 280-284 | Cancellation response includes undeclared `is_cancelled` field and omits required `answer`/`usage`/`response_format` |
| DB-232 | Medium | Config | `rlm/core/rlm.py` | 204-219 | `recursive_rlm_config` omits `max_budget`, `max_timeout`, `custom_system_prompt`. Recursive sub-RLM calls run with no budget/timeout constraints |
| DB-233 | Low | Encoding | `rlm/environments/modal_repl.py`, `daytona_repl.py`, `e2b_repl.py` | `load_context` | Context strings ending in `"` produce `SyntaxError` — triple-quote closing merges with trailing quote to form `""""` |
| DB-234 | Low | Type | `rlm/core/comms_utils.py` | 163-165 | `LMResponse.from_dict` coerces non-string `error` to `None`, turning `{"error": 500}` into crash via `__post_init__` ValueError |

### Concurrency & Resource Leaks

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-235 | High | Race | `vscode-extension/python/rlm_backend.py` | 430 | Thread references discarded — no tracking, no join, no concurrency limit. Rapid cancel+complete creates competing threads; partial JSON on `os._exit(0)` |
| DB-236 | Medium | Race | `rlm/clients/openai.py` | 56-58 | `model_call_counts`/`model_input_tokens`/`model_output_tokens` `defaultdict(int)` unsynchronized across `ThreadingTCPServer` handler threads |
| DB-237 | Medium | Resource | `rlm/environments/docker_repl.py` | 331-337 | `proxy_thread` never joined in `cleanup()` despite `proxy_server.shutdown()`. Thread may hold socket when next instance binds |
| DB-238 | Medium | Resource | `rlm/mcp_gateway/server.py` | 1731, 1762 | `_session_toolset_fingerprints` dict grows unbounded — entries added per session, never removed on close |
| DB-239 | Medium | Resource | `rlm/mcp_gateway/session.py` | 78, 95-103 | `_active_requests` entries orphaned when `_cleanup_expired_sessions` removes sessions |

### Error Handling

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-240 | High | Bug | `rlm/core/lm_handler.py` | 119-121 | `asyncio.gather(*tasks)` without `return_exceptions=True` — one failed prompt discards all successful batch results |
| DB-241 | High | Bug | `rlm/core/rlm.py` | 530-545 | `_completion_turn` has zero error handling around `lm_handler.completion()` and `environment.execute_code()`. API error crashes entire completion with no partial result |
| DB-242 | High | Bug | `rlm/core/comms_utils.py` | 258-266 | `send_lm_request` outer `except Exception` converts programming bugs (ValueError, TypeError) into error response strings instead of raising |
| DB-243 | Medium | Bug | `rlm/environments/docker_repl.py` | 301-306 | `subprocess.run` in `execute_code` has no `timeout`. Infinite-loop Docker code hangs RLM process forever |
| DB-244 | Medium | Bug | `rlm/environments/docker_repl.py` | 224-244 | `docker run` and `pip install` in `setup()` have no timeout. Docker init blocks indefinitely if Docker is unresponsive |
| DB-245 | Medium | Bug | `rlm/environments/docker_repl.py` | 217-249 | If `pip install` fails after `docker run` succeeds, container is leaked — `setup()` is in `__init__`, so `cleanup()` never fires |
| DB-246 | Medium | Bug | `rlm/clients/openai.py` | 244-250 | `_track_cost` raises `ValueError` when `response.usage is None`, discarding a successful LLM response. Same in `azure_openai.py` |
| DB-247 | Medium | Bug | `rlm/clients/ollama.py` | 122-136 | HTTP 4xx errors (`requests.HTTPError`) retried 3× via `retry_with_backoff` — non-retryable errors waste time with exponential backoff |
| DB-248 | Medium | Bug | `vscode-extension/python/rlm_backend.py` | 355-381 | `handle_execute` vs `handle_completion` return different error shapes: `{"error": True}` (bool) vs `{"error": "<string>"}` |
| DB-249 | Medium | Resource | `vscode-extension/python/rlm_backend.py` | 344-353 | Ephemeral `LocalREPL` in `handle_execute` never calls `cleanup()` — leaks temp directory per call |
| DB-250 | Medium | Bug | `rlm/core/rlm.py` | 604-624 | `_compact_history` has no error handling around `lm_handler.completion()`. Failed compaction LM call crashes entire completion |
| DB-251 | Low | Bug | `rlm/core/lm_handler.py` | 47-50 | `LMRequestHandler.handle()` silently drops successful LLM results on socket errors — tokens consumed but result lost |
| DB-252 | Low | Bug | `rlm/environments/local_repl.py` | 439-447 | `_execution_timeout` silently skipped in non-main threads. Extension backend runs completions in daemon threads → no timeout enforcement |
| DB-253 | Low | Bug | `vscode-extension/python/rlm_backend.py` | 413-425 | `stdin_reader` silently discards `JSONDecodeError` for corrupted messages — extension hangs waiting for reply |
| DB-254 | Low | Bug | `rlm/environments/docker_repl.py` | 330-338 | `cleanup()` calls `docker stop` without timeout — blocks indefinitely if Docker is unresponsive |

### State Management

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-255 | Critical | Bug | `rlm/environments/local_repl.py` | 94, 143-146, 472 | `_final_answer` not cleared between persistent-mode completions. Stale answer from prior completion can terminate next completion prematurely with wrong result |
| DB-256 | High | Resource | `rlm/core/rlm.py` | 232-260 | `_spawn_completion_context`: if `_create_environment()` raises after `_create_lm_handler()` starts TCP server, the handler is never stopped. Leaks TCP server thread + port per failed call |
| DB-257 | Medium | Bug | `rlm/core/rlm.py` | 121, 567-573 | `_prefix_prompt_cache` never cleared between completions. Shallow cache key can collide, serving wrong cached prefix |
| DB-258 | Low | Bug | `rlm/debugging/call_history.py` | 278-286 | `from_dict()` doesn't restore `_call_counter` — subsequent `add_call()` generates duplicate `call_id` values |

### API Contract Mismatches

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-259 | Medium | Schema | `rlm/mcp_gateway/server.py` + `complete_tools.py` | 1029-1042, 99-104 | `budgets.max_depth`, `max_tool_calls`, `max_output_bytes` accepted by schema but silently ignored by implementation |
| DB-260 | Medium | Schema | `rlm/mcp_gateway/tools/complete_tools.py` + `server.py` | 35-43, 1207-1219 | `backend_config_map` only has "openai" and "anthropic" — 9 of 11 supported backends unusable via MCP gateway |
| DB-261 | Low | Schema | `rlm/mcp_gateway/server.py` + `exec_tools.py` | 1009-1014, 63-64 | `timeout_ms` schema declares no maximum but implementation rejects >30000ms. Undocumented ceiling |

## Previous Passes (all resolved)

All items from DB-001 through DB-155 (runs 1–24) were implemented and verified. See `docs/orchestrator/state.json` for the full verified list.

---

## Pass 4 — Focused Orthogonal Audit (Run 27, 4 passes)

Run 27 added 4 more orthogonal lenses to supplement Run 26: data flow integrity, configuration/defaults, logging/observability, and protocol correctness. Findings start at DB-262.

### Data Flow Integrity

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-262 | High | Bug | `rlm/environments/local_repl.py` | 397-462 | Unbounded StringIO stdout/stderr capture — `print("x" * 10**9)` OOMs host. No size cap on capture buffers |
| DB-263 | Medium | Bug | `rlm/mcp_gateway/tools/complete_tools.py` | 265-280 | `complete()` never updates `session.output_bytes` — completions bypass output budget tracking |
| DB-264 | Medium | Bug | `rlm/mcp_gateway/tools/exec_tools.py` | 134-141 | `_truncate_output` uses byte threshold but character-count truncation. Multi-byte UTF-8 exceeds 1MB limit. Hardcoded return value |
| DB-265 | Medium | Bug | `rlm/core/rlm.py` | 672-677 | `_fallback_answer` converts dict prompt via `str()` — lossy Python repr instead of JSON |
| DB-266 | Medium | Bug | `rlm/clients/anthropic.py` | 196-201 | `get_last_usage()` drops `cache_creation_input_tokens` and `cache_read_input_tokens`; intermediate sub-LM usage inaccurate |
| DB-267 | Medium | Bug | `rlm/environments/local_repl.py` | 303-324 | `add_context` discards `execute_code()` return value — context loading errors silently lost; NameError downstream |
| DB-268 | Medium | Bug | `rlm/clients/vscode_lm.py` | 115-125 | VsCodeLM flattens structured messages to `[role]: content` text — loses multi-turn role structure for all builtin-mode iterations |
| DB-269 | Low | Bug | `vscode-extension/python/rlm_backend.py` | 295-296 | `_completion_payload` truthiness check treats empty collections as absent — `context=[]` becomes prompt |
| DB-270 | Low | Bug | `rlm/core/types.py` | 186-196 | `RLMChatCompletion.to_dict()` passes `prompt` raw without `_serialize_value` — non-JSON-serializable nested objects crash `json.dumps` |
| DB-271 | Low | Perf | `rlm/core/rlm.py` + `rlm/logger/rlm_logger.py` | 524-548, 98-117 | `RLMIteration.prompt` stores full message history per iteration — O(n²) memory in logger over 30 iterations |

### Configuration & Defaults

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-272 | Medium | Bug | `rlm/environments/base_env.py` | 26-34 | `FINAL` missing from `RESERVED_TOOL_NAMES` — user code can overwrite `FINAL()` function, `_restore_scaffold` won't restore it |
| DB-273 | Medium | Bug | `rlm/core/rlm.py` | 40-69, 95-140 | No validation of `RLMConfig` numeric fields — `max_iterations=-1`, `compaction_threshold_pct=5.0` silently accepted |
| DB-274 | Medium | Config | `rlm/clients/openai.py` vs `vscode-extension/package.json` | 37, 206 | Default model mismatch: OpenAI client→`gpt-4o-mini`, extension→`gpt-4o`. Undocumented divergence |
| DB-275 | High | Bug | `rlm/clients/anthropic.py` | 23 | Default model `claude-3-5-sonnet` is invalid Anthropic API identifier (requires dated suffix). Every no-model call fails |
| DB-276 | Medium | Config | `rlm/clients/anthropic.py` + `portkey.py` | 16, 18 | Anthropic/Portkey require `api_key` as positional arg — inconsistent with OpenAI/Gemini/Azure which auto-resolve from env vars |
| DB-277 | Medium | Bug | `rlm/clients/portkey.py` | 24 | Default model is empty string — constructs OK but every `completion()` raises ValueError. Delayed failure |
| DB-278 | Medium | Config | `rlm/core/rlm.py` | 355-370 | `_update_handler_cost` uses hardcoded $0.00001/token rate identical for all models — max_budget enforcement off by up to 100x |
| DB-279 | Medium | Bug | `rlm/core/rlm.py` | 108-114, 174-176 | `other_backends`/`other_backend_kwargs` desync not validated — setting backends without kwargs silently skips sub-backend |
| DB-280 | Medium | Bug | `rlm/core/rlm.py` + `local_repl.py` | 55, 239-248 | `enable_recursive_subcalls` flag never checked — recursion gated only by `max_depth` via different code path |
| DB-281 | Low | Config | `rlm/mcp_gateway/session.py` vs `rlm/core/rlm.py` | 24, 46 | MCP default `max_depth=10` vs core `max_depth=1` — naming collision with different semantics |
| DB-282 | Low | Config | `rlm/clients/__init__.py`, `openai.py`, etc. | 9, 15, 13, 12, 18 | Multiple `load_dotenv()` at import time — first import wins, env vars frozen at import, no override |
| DB-283 | Low | Config | `rlm/clients/anthropic.py` vs `openai.py` | 25, 39 | Anthropic prompt cache defaults `True` (opt-out), OpenAI prefix cache defaults `False` (opt-in) — inconsistent |
| DB-284 | Low | Config | `vscode-extension/python/rlm_backend.py` | 210-228 | `_apply_litellm_backend_aliases` only maps 3 of 11 backends — extension vs SDK routing divergence |

### Logging & Observability

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-285 | High | Bug | `rlm/environments/modal_repl.py` | 265-270 | Poller thread silently swallows all exceptions (both `RequestException` and generic `Exception`) — sub-LM calls hang forever |
| DB-286 | High | Bug | `rlm/environments/prime_repl.py` | 497-500 | Same silently-swallowed poller pattern as Modal |
| DB-287 | High | Bug | `rlm/environments/daytona_repl.py` | 514-517 | Same silently-swallowed poller pattern as Modal/Prime |
| DB-288 | High | Bug | `rlm/logger/rlm_logger.py` | 128-131 | `log()` file write has no I/O error handling — disk full/permission error crashes entire RLM completion loop |
| DB-289 | Medium | Bug | `rlm/core/lm_handler.py` | 48-55 | `LMRequestHandler.handle()` catches connection errors and generic Exception without logging on server side |
| DB-290 | Medium | Gap | `rlm/core/lm_handler.py` | 26-56 | Zero request/response logging in LMHandler — model, prompt size, latency, errors all invisible |
| DB-291 | Medium | Bug | `rlm/logger/rlm_logger.py` | 102-107 | `log_metadata()` file write has no I/O error handling — same crash risk as DB-288 |
| DB-292 | Medium | Bug | `rlm/environments/local_repl.py` | 280-281 | `_build_nested_rlm_function` catches all exceptions and returns `None` — recursive sub-call failures invisible |
| DB-293 | Medium | Bug | `rlm/environments/daytona_repl.py` | 487-489 | `get_preview_link` failure silently sets `broker_url=None` — poller never starts, sub-LM calls fail with no error |
| DB-294 | Medium | Bug | `rlm/environments/modal_repl.py` + `docker_repl.py` + `daytona_repl.py` | 391-393, 275-276, 636-637 | `_parse_execution_payload` returns `None` on JSON decode failure — no diagnostic of raw output |
| DB-295 | Medium | Bug | `rlm/environments/exec_script_templates.py` | 67-68, 189-190 | `load_state()` silently swallows dill deserialization errors — all REPL variables lost with no warning |
| DB-296 | Medium | Bug | `rlm/core/comms_utils.py` | 265-266, 316-317 | `send_lm_request`/`send_lm_request_batched` converts failures to error response without logging — server-side diagnosis impossible |
| DB-297 | Medium | Gap | All `rlm/core/` and `rlm/environments/` | — | Zero `import logging` usage — no structured logging framework; no way to enable debug-level diagnostics without code changes |
| DB-298 | Medium | Bug | `rlm/utils/rlm_utils.py` | 4-12 | `filter_sensitive_keys` only matches `api`+`key` — misses `token`, `secret`, `password`, `auth`. No redaction in RLMLogger |
| DB-299 | Low | Bug | `rlm/environments/exec_script_templates.py` | 79-80, 198-199 | `save_state()` silently drops unserializable variables — no warning of which variables were lost |
| DB-300 | Low | Bug | Various `cleanup()` methods | — | Modal/Prime/Daytona/LocalREPL cleanup silently swallows all exceptions — leaked cloud resources invisible |
| DB-301 | Low | Gap | `rlm/debugging/__init__.py` | 6-7 | `CallHistory`/`GraphTracker` not wired into core — dead code from integration perspective |

### Protocol & Compatibility

| ID | Severity | Category | File | Lines | Description |
|----|----------|----------|------|-------|-------------|
| DB-302 | Medium | Gap | All protocol boundaries | — | No protocol version field on any boundary (socket, stdin/stdout bridge, MCP). Adding fields is breaking with no detection |
| DB-303 | Medium | Schema | `rlm/mcp_gateway/tools/complete_tools.py` + `server.py` | 201-218, 536-551 | `rlm.complete` success output missing schema-required `response_format` field; undeclared `resource_link` and `instructions` |
| DB-304 | Medium | Schema | `rlm/mcp_gateway/tools/complete_tools.py` | 53-57, 263-277 | All error paths violate output schema `required` fields — return only `{success, error}` but schema requires `answer`, `usage`, `response_format` |
| DB-305 | Low | Bug | `rlm/core/comms_utils.py` | 109-149 | `LMResponse.to_dict()` always emits explicit `None` values; `from_dict()` crashes if all 3 fields omitted (asymmetric contract) |
| DB-306 | Low | Schema | `rlm/core/types.py` | 217-244 | `RLMChatCompletion.to_dict()` conditionally omits `metadata` key — non-deterministic schema unlike all other dataclasses |
| DB-307 | Low | Config | `vscode-extension/python/rlm_backend.py` + `src/types.ts` | 177-189, 64-76 | `ConfigureMessage` camelCase field matching is manual and fragile — rename on either side silently falls back to defaults |
| DB-308 | Low | Bug | `rlm/clients/vscode_lm.py` + bridge protocol | 85, 113-121 | `llm_request` message only carries `prompt: string` — structured message arrays destroyed on bridge crossing |
| DB-309 | Low | Bug | `rlm/mcp_gateway/session.py` | 107 | `SessionConfig(**config)` crashes on unknown keys from MCP input — opaque `TypeError` instead of validation error |
| DB-310 | Low | Bug | `rlm/core/types.py` | 343, 363 | `RLMMetadata.to_dict()` serializes callables to repr strings via `_serialize_value` — `from_dict()` roundtrip semantically different |
