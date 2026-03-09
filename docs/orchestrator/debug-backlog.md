# Debug Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Produced by: .github/prompts/debug-plan.prompt.md -->
<!-- Consumed by: .github/prompts/debug-agent.prompt.md -->
<!-- Do NOT add research items here; use research-backlog.md instead -->
<!-- Last updated: 2026-03-02 -->
<!-- Run 26: Orthogonal deep review (6 focused passes). DB-222 through DB-261 added. -->
<!-- Run 27: Four more orthogonal passes (data flow, config, logging, protocol). DB-262 through DB-310 added. -->

## Priority 1 — Critical / Process-Breaking Bugs

### DB-222: Sandbox escape via object subclass hierarchy
- **File**: `rlm/core/sandbox/ast_validator.py` + `safe_builtins.py`
- **Impact**: Full arbitrary code execution as gateway process user. `object.__subclasses__()` → `__init__.__globals__` → `os.system()` bypasses all sandbox restrictions. `object`, `type`, `getattr`, `hasattr` are all in safe builtins; AST validator has no dunder chain checks.
- **Fix**: Block `__subclasses__`, `__bases__`, `__globals__`, `__init__`, `__code__`, `__mro__`, `__dict__` attribute access in AST validator. Consider removing `object`/`type` from safe builtins.
- **Test**: Verify `validate_ast("object.__subclasses__()")` returns error.

### DB-223: RestrictedBuiltins _safe dict directly accessible and replaceable
- **File**: `rlm/core/sandbox/restricted_exec.py:65-79,98`
- **Impact**: `__builtins__._safe` bypasses `__getattr__`; `__setattr__` allows replacing `_safe` dict entirely (any `_`-prefixed attribute settable). Combined with DB-222, allows restoring full builtins.
- **Fix**: Store safe builtins in a closure or use `__slots__`; reject all attribute setting in `__setattr__`.
- **Test**: Verify `__builtins__._safe` raises; verify `setattr(__builtins__, '_x', 1)` raises.

### DB-224: ProgressLogger missing clear_iterations() and get_trajectory()
- **File**: `vscode-extension/python/rlm_backend.py:123-155`
- **Impact**: `RLM.completion()` calls `self.logger.clear_iterations()` (rlm.py:302) and `self.logger.get_trajectory()` (rlm.py:513). ProgressLogger has neither method → `AttributeError` on every VS Code extension completion.
- **Fix**: Add `clear_iterations()` and `get_trajectory()` methods to ProgressLogger.
- **Test**: Add test calling both methods on ProgressLogger.

### DB-255: _final_answer stale in persistent mode
- **File**: `rlm/environments/local_repl.py:94,143-146,472`
- **Impact**: `_final_answer` not cleared between persistent completions. If first completion sets `_final_answer` via `FINAL_VAR()` and second completion's first iteration has no FINAL(), the stale value is returned as the answer. Silent wrong-answer bug.
- **Fix**: Clear `_final_answer` at start of each `execute_code()` call, or expose a `reset_final_answer()` called from `RLM.completion()`.
- **Test**: Two sequential completions on persistent LocalREPL; verify second doesn't return first's answer.

### DB-195: RLIMIT_AS applied process-wide, never restored
- **File**: `rlm/mcp_gateway/exec_tools.py:64-73`
- **Impact**: Memory limit applied to entire Python process (not just sandbox thread) — never restored after execution. Can crash the gateway.
- **Fix**: Save old RLIMIT_AS, restore in `finally` block. Or apply only in subprocess.
- **Test**: Add test that RLIMIT_AS is restored after `safe_exec()`.

### DB-196: setup_runtime_blocking modifies global sys.modules without thread safety
- **File**: `rlm/mcp_gateway/exec_tools.py:156-173`
- **Impact**: In HTTP server mode, concurrent exec calls race on `sys.modules` — one thread's blocking can break another thread's normal imports.
- **Fix**: Use per-thread module overrides or subprocess isolation.
- **Test**: Add concurrent exec test verifying sys.modules isolation.

## Priority 2 — High-Severity Bugs

### DB-171: Client last_prompt_tokens/last_completion_tokens uninitialized
- **Files**: `openai.py`, `anthropic.py`, `azure_openai.py`, `litellm.py` (`__init__` methods)
- **Impact**: `get_last_usage()` before first `completion()` raises `AttributeError`.
- **Fix**: Initialize `self.last_prompt_tokens = 0` and `self.last_completion_tokens = 0` in each `__init__`.
- **Test**: Add test calling `get_last_usage()` before any `completion()`.

### DB-172: Ollama get_last_usage returns cumulative tokens
- **File**: `rlm/clients/ollama.py:196-204`
- **Impact**: Per-iteration usage tracking inflated — `total_prompt_tokens` and `total_completion_tokens` grow monotonically but should be per-call.
- **Fix**: Track delta between calls (store previous cumulative, subtract).
- **Test**: Two completions, assert `get_last_usage()` reflects only second call.

### DB-173: Ollama acompletion blocks event loop
- **File**: `rlm/clients/ollama.py:164-176`
- **Impact**: Batched requests serialize instead of running concurrently. Performance regression for multi-query batches.
- **Fix**: Use `aiohttp` or `asyncio.to_thread()` to avoid blocking.
- **Test**: Verify concurrent `acompletion` calls overlap in wall time.

### DB-219: FINAL() regex DOTALL greedy overmatch
- **File**: `rlm/utils/parsing.py:150-153`
- **Impact**: `re.DOTALL` + `(.*)` captures too much when multiple FINAL() calls or trailing commentary exists — corrupts extracted answer.
- **Fix**: Remove `re.DOTALL` or use non-greedy `(.*?)` or anchor to line boundary.
- **Test**: Test with `FINAL("answer")\nsome commentary` — should only capture `"answer"`.

### DB-197: Daemon thread leak on sandbox timeout
- **File**: `rlm/mcp_gateway/exec_tools.py:87-102`
- **Impact**: Timed-out exec threads run indefinitely — resource leak under repeated timeouts.
- **Fix**: Run sandbox code in subprocess (can be killed) or use `ctypes.pythonapi.PyThreadState_SetAsyncExc`.
- **Test**: Timeout test, verify no lingering threads.

### DB-199: MCP cancellation infrastructure not wired
- **Files**: `rlm/mcp_gateway/session.py:187-193`, `server.py`
- **Impact**: `register_active_request`/`unregister_active_request`/`cancel_by_request_id` exist but are never called — MCP `$/cancelRequest` is silently ignored.
- **Fix**: Wire `register_active_request` in `_rpc_tools_call` and `_rpc_completion_complete`; call `cancel_by_request_id` from notification handler.
- **Test**: Test that cancellation sets `cancel_event`.

### DB-211: Backend STATE race condition
- **File**: `vscode-extension/python/rlm_backend.py:424-428`
- **Impact**: `completion`/`execute` handlers run in `threading.Thread` without `STATE` locking — concurrent calls corrupt `current_progress_nonce`, `cancel_requested`.
- **Fix**: Add `threading.Lock` around STATE mutations.
- **Test**: Concurrent completion + cancel test.

### DB-183: PrimeREPL JSONDecodeError unhandled
- **File**: `rlm/environments/prime_repl.py:612`
- **Impact**: Malformed sandbox stdout crashes `json.loads()` — no recovery, no error message to user.
- **Fix**: Wrap in `try/except json.JSONDecodeError`, return error `REPLResult`.
- **Test**: Mock malformed JSON response, verify graceful `REPLResult` with error.

### DB-184: DaytonaREPL stdout/stderr conflation
- **File**: `rlm/environments/daytona_repl.py:675-676`
- **Impact**: On success, stderr is empty (lost); on failure, stdout (JSON result) is lost. Sub-LLM results can be silently dropped.
- **Fix**: Parse stdout as JSON separately from stderr; don't overwrite.
- **Test**: Test execute with both stdout and stderr content.

### DB-225: AST validator has no dunder chain checks
- **File**: `rlm/core/sandbox/ast_validator.py:141-175`
- **Impact**: Root cause of DB-222. No checks for `__class__`, `__bases__`, `__subclasses__`, `__globals__`, `__code__`, `__mro__`. All dunder attribute chains pass validation.
- **Fix**: Add `_check_dangerous_attribute_access()` that rejects dunder attribute access on non-builtin objects.
- **Test**: Verify AST rejects `x.__class__.__bases__`, `x.__globals__`, `x.__subclasses__()`.

### DB-226: REPL has no AST validation — credential exposure via prompt injection
- **File**: `rlm/environments/local_repl.py:85-90,456`
- **Impact**: LLM-generated REPL code can `import os; os.environ` to extract API keys; can exfiltrate via `urllib.request`. Prompt injection vector: poisoned context document instructs LLM to emit exfiltration code.
- **Fix**: Add optional AST validation in REPL mode; restrict `os.environ` access; consider env var filtering for REPL process.
- **Test**: Test that prohibited imports are blocked when AST validation is enabled.

### DB-235: Backend completion threads unmanaged
- **File**: `vscode-extension/python/rlm_backend.py:430`
- **Impact**: Thread references discarded (fire-and-forget). No concurrency limit, no join on shutdown. Rapid cancel+complete creates competing threads; partial JSON on `os._exit(0)`.
- **Fix**: Track active threads; limit to 1 concurrent completion; join before exit.
- **Test**: Verify only one completion thread runs at a time.

### DB-240: asyncio.gather without return_exceptions discards partial batch results
- **File**: `rlm/core/lm_handler.py:119-121`
- **Impact**: One failed prompt in batch causes all successful results to be discarded.
- **Fix**: Use `asyncio.gather(*tasks, return_exceptions=True)`; handle per-result errors.
- **Test**: Batch of 3 prompts where 1 fails — verify 2 successful results preserved.

### DB-241: _completion_turn has zero error handling
- **File**: `rlm/core/rlm.py:530-545`
- **Impact**: API error during any iteration crashes entire completion — no partial result returned, no error recovery.
- **Fix**: Wrap in try/except; on error, log and use `_default_answer` for best-effort result. Wire `max_errors` config.
- **Test**: Mock API failure on iteration 3; verify partial result returned.

### DB-242: send_lm_request converts programming bugs to error strings
- **File**: `rlm/core/comms_utils.py:258-266`
- **Impact**: Outer `except Exception` catches ValueError, TypeError, JSONDecodeError — returns as "Request failed" string instead of raising. Programming bugs become silent error responses.
- **Fix**: Only catch IOError/ConnectionError/TimeoutError in outer handler; let other exceptions propagate.
- **Test**: Verify ValueError from from_dict() raises, not silently converts.

### DB-256: LMHandler leak when environment creation fails
- **File**: `rlm/core/rlm.py:232-260`
- **Impact**: `_create_lm_handler()` starts TCP server before environment creation. If `_create_environment()` raises, handler never stopped — leaks thread + port per failed call.
- **Fix**: Move handler creation inside try, or add try/except around env creation that stops handler on failure.
- **Test**: Mock environment creation failure; verify handler port released.

### DB-262: Unbounded stdout/stderr capture in LocalREPL — OOM risk
- **File**: `rlm/environments/local_repl.py:397-462`
- **Impact**: LLM-generated `print("x" * 10**9)` causes unbounded StringIO growth. Executes within SIGALRM timeout (no loop needed). OOMs host.
- **Fix**: Use a size-limited StringIO wrapper that stops writing after N bytes (e.g., 1MB).
- **Test**: Verify large print output is truncated, not OOM.

### DB-275: Anthropic default model `claude-3-5-sonnet` is invalid API identifier
- **File**: `rlm/clients/anthropic.py:23`
- **Impact**: Every `AnthropicClient()` call without explicit `model_name` fails with API error. Requires dated suffix like `claude-sonnet-4-20250514`.
- **Fix**: Update default to a valid model identifier.
- **Test**: Verify default model string is a valid Anthropic API model.

### DB-285: Modal poller thread silently swallows all exceptions
- **File**: `rlm/environments/modal_repl.py:265-270`
- **Impact**: Any error in `_poll_broker` — network, JSON parsing, response forwarding — silently discarded. Sub-LM calls hang forever with zero diagnostic.
- **Fix**: Log exception to stderr before `pass`.

### DB-286: Prime poller thread silently swallows all exceptions
- **File**: `rlm/environments/prime_repl.py:497-500`
- **Impact**: Same as DB-285 for Prime sandboxes.
- **Fix**: Log exception to stderr before `pass`.

### DB-287: Daytona poller thread silently swallows all exceptions
- **File**: `rlm/environments/daytona_repl.py:514-517`
- **Impact**: Same as DB-285 for Daytona sandboxes.
- **Fix**: Log exception to stderr before `pass`.

### DB-288: RLMLogger.log() file write has no I/O error handling
- **File**: `rlm/logger/rlm_logger.py:128-131`
- **Impact**: Disk full or permission error crashes entire RLM completion loop. In-memory data is already saved; failure should be non-fatal.
- **Fix**: Wrap file write in `try/except OSError` and continue.

## Priority 3 — Medium-Severity Bugs and Issues

### DB-156: max_errors dead code
- **File**: `rlm/core/rlm.py:50,127`
- **Fix**: Remove parameter and attribute, or implement error counting.

### DB-157: enable_recursive_subcalls dead code
- **File**: `rlm/core/rlm.py:55,128`
- **Fix**: Remove or implement subcall depth gating.

### DB-158: on_subcall_start/on_subcall_complete dead callbacks
- **File**: `rlm/core/rlm.py:56-57,129-130`
- **Fix**: Remove or wire into subcall flow.

### DB-159: Sandbox blocked module lists diverge
- **Files**: `rlm/core/sandbox/ast_validator.py`, `restricted_exec.py`
- **Fix**: Extract single source-of-truth constant; import in both modules.
- **Test**: Add test asserting set equality.

### DB-160: _cumulative_cost never resets
- **File**: `rlm/core/rlm.py:141`
- **Fix**: Reset at start of `completion()`.

### DB-161: Batched response shares single UsageSummary
- **File**: `rlm/core/lm_handler.py:129-141`
- **Fix**: Capture per-task usage, sum after gather.

### DB-162: socket_recv partial length prefix read
- **File**: `rlm/core/comms_utils.py:200-203`
- **Fix**: Loop `recv` until 4 bytes received (like payload loop).

### DB-163: _default_answer wrong role
- **File**: `rlm/core/rlm.py:648-652`
- **Fix**: Change `"assistant"` to `"user"` for the prompt cue.

### DB-165: Sandbox dict access bypass
- **File**: `rlm/core/sandbox/restricted_exec.py:83-131`
- **Fix**: Add `input`, `globals`, `locals` to `__getitem__` blocklist.

### DB-174: Azure kwargs silently dropped
- **File**: `rlm/clients/azure_openai.py:102-106`
- **Fix**: Pass `**self.kwargs` to API call.

### DB-176: Gemini system instruction as user message
- **File**: `rlm/clients/gemini.py:76-85`
- **Fix**: Use `system_instruction` API parameter.

### DB-177: BaseLM.completion() missing model param
- **Files**: `rlm/clients/base_lm.py`, all clients
- **Fix**: Add `model: str | None = None` to abstract `completion()`.

### DB-185: Modal broker cold start race
- **File**: `rlm/environments/modal_repl.py:244`
- **Fix**: Replace `time.sleep(2)` with broker `/health` polling loop (max retries).

### DB-188: load_context string escaping fragility
- **Files**: `modal_repl.py`, `prime_repl.py`, `daytona_repl.py`, `e2b_repl.py`
- **Fix**: Use JSON serialization + `json.loads()` in template instead of f-string interpolation.

### DB-189: Docker pip install failure ignored
- **File**: `rlm/environments/docker_repl.py:237-240`
- **Fix**: Check exit code, raise or warn on failure.

### DB-191: LocalREPL stdout capture not thread-safe
- **File**: `rlm/environments/local_repl.py:406-415`
- **Fix**: Use `contextlib.redirect_stdout/stderr` or per-thread StringIO.

### DB-192: LocalREPL SystemExit propagation
- **File**: `rlm/environments/local_repl.py:454-461`
- **Fix**: Catch `SystemExit` in exec handler, return as error `REPLResult`.

### DB-198: PathValidator "env" substring false positives
- **File**: `rlm/mcp_gateway/validation.py:93-97`
- **Fix**: Use word boundary or prefix matching (`.env` not `env`).
- **Test**: Assert `development/foo.py` is NOT restricted.

### DB-200: _COMPLETE_OUTPUT_SCHEMA answer required but omitted on error
- **File**: `rlm/mcp_gateway/server.py:543-557`
- **Fix**: Make `answer` optional in schema, or always include it.

### DB-201: fs_list depth parameter ignored
- **File**: `rlm/mcp_gateway/filesystem_tools.py:68-87`
- **Fix**: Implement recursive listing up to `depth` levels.

### DB-202: Chunks dict unbounded growth
- **File**: `rlm/mcp_gateway/handles.py:72-92`
- **Fix**: Add size cap and LRU eviction, or scope to session.

### DB-203: Session close doesn't clean up handles/chunks
- **File**: `rlm/mcp_gateway/session.py:117-120`
- **Fix**: On session close, remove associated handles and chunks.

### DB-204: LMHandler resource leak in sampling
- **File**: `rlm/mcp_gateway/server.py:1268-1277`
- **Fix**: Use context manager for LMHandler; cleanup after sampling.

### DB-205: Dual gateway globals (gateway vs gateway_instance)
- **File**: `rlm/mcp_gateway/server.py:535-536`
- **Fix**: Consolidate to single global; check consistently across all RPCs.

### DB-206: Span size off-by-one
- **File**: `rlm/mcp_gateway/span_tools.py:154-158`
- **Fix**: Use `end_line - start_line + 1` for line count.

### DB-212: KNOWN_BACKENDS missing "ollama"
- **File**: `vscode-extension/src/extension.ts:31-41`
- **Fix**: Add `"ollama"` to the array.

### DB-214: Unsandboxed LocalREPL in handle_execute
- **File**: `vscode-extension/python/rlm_backend.py:343-349`
- **Fix**: Apply sandbox builtins or refuse execution without active RLM instance.

### DB-215: buildChildEnv leaks *_KEY env vars
- **File**: `vscode-extension/src/backendBridge.ts:464-470`
- **Fix**: Filter env vars ending in `_KEY`, `_SECRET`, `_TOKEN` from child process environment.

### DB-216: persistent flag ignored after first RLM creation
- **File**: `vscode-extension/python/rlm_backend.py:232-234`
- **Fix**: Check if `persistent` changed; recreate RLM instance if so.

### DB-217: ensureBackend TOCTOU race
- **File**: `vscode-extension/src/rlmParticipant.ts:568-583`
- **Fix**: Add a mutex/flag to prevent concurrent `ensureBackend()` calls.

### DB-227: REPL bound methods expose LocalREPL internals
- **File**: `rlm/environments/local_repl.py:93-102`
- **Fix**: Use wrapper functions (not bound methods) in REPL namespace; or create `__self__`-hiding proxy.
- **Test**: Verify `llm_query.__self__` is not accessible from REPL code.

### DB-228: Exec script dill deserialization attack vector
- **File**: `rlm/environments/exec_script_templates.py:58-73`
- **Fix**: Use JSON for state persistence instead of dill/pickle; or validate state before loading.

### DB-230: Elicitation field name mismatch (elicitation_request vs elicitation)
- **Files**: `rlm/mcp_gateway/tools/complete_tools.py:72-84`, `server.py:547,680`
- **Fix**: Rename to consistent key in both schema and implementation.

### DB-231: Cancellation response includes undeclared fields, omits required ones
- **File**: `rlm/mcp_gateway/tools/complete_tools.py:280-284`
- **Fix**: Include all required output fields; declare `is_cancelled` in schema or remove it.

### DB-232: Recursive RLM config omits budget/timeout limits
- **File**: `rlm/core/rlm.py:204-219`
- **Fix**: Propagate `max_budget`, `max_timeout`, `custom_system_prompt` to `recursive_rlm_config`.
- **Test**: Verify child RLM inherits parent's budget limit.

### DB-236: Client usage counter dicts unsynchronized across threads
- **File**: `rlm/clients/openai.py:56-58` (and all clients)
- **Fix**: Use `threading.Lock` around `_track_cost()`; or use atomic counters.

### DB-237: Docker proxy thread not joined in cleanup
- **File**: `rlm/environments/docker_repl.py:331-337`
- **Fix**: Add `self.proxy_thread.join(timeout=2)` after `proxy_server.shutdown()`.

### DB-238: _session_toolset_fingerprints unbounded growth
- **File**: `rlm/mcp_gateway/server.py:1731,1762`
- **Fix**: Clean entries on session close.

### DB-239: _active_requests orphaned on session expiry
- **File**: `rlm/mcp_gateway/session.py:78,95-103`
- **Fix**: On session delete, also remove entries from `_active_requests` pointing to that session.

### DB-243: Docker execute_code subprocess has no timeout
- **File**: `rlm/environments/docker_repl.py:301-306`
- **Fix**: Add `timeout=execution_timeout_seconds` to `subprocess.run()`.

### DB-244: Docker setup subprocess calls have no timeout
- **File**: `rlm/environments/docker_repl.py:224-244`
- **Fix**: Add `timeout=60` to `docker run` and `pip install` subprocess calls.

### DB-245: Docker container leaked on setup pip install failure
- **File**: `rlm/environments/docker_repl.py:217-249`
- **Fix**: Wrap pip install in try/except; call `cleanup()` on failure.

### DB-246: _track_cost raises on missing usage data, discarding successful response
- **File**: `rlm/clients/openai.py:244-250`, `azure_openai.py`
- **Fix**: Log warning and skip usage tracking instead of raising ValueError.

### DB-247: Ollama retries HTTP 4xx errors unnecessarily
- **File**: `rlm/clients/ollama.py:122-136`
- **Fix**: Exclude `requests.HTTPError` (4xx) from retryable exceptions.

### DB-248: handle_execute vs handle_completion error format inconsistency
- **File**: `vscode-extension/python/rlm_backend.py:355-381`
- **Fix**: Use consistent `{"type": "error", "error": "<message>"}` shape for both.

### DB-249: Ephemeral LocalREPL in handle_execute leaks temp dir
- **File**: `vscode-extension/python/rlm_backend.py:344-353`
- **Fix**: Call `repl.cleanup()` after execution.

### DB-250: _compact_history has no error handling
- **File**: `rlm/core/rlm.py:604-624`
- **Fix**: Wrap compaction LM call in try/except; on failure, return uncompacted history.

### DB-257: _prefix_prompt_cache collision across completions
- **File**: `rlm/core/rlm.py:121,567-573`
- **Fix**: Clear cache at start of `completion()`; or use completion-scoped cache.

### DB-259: MCP budgets schema accepts but ignores max_depth, max_tool_calls, max_output_bytes
- **Files**: `rlm/mcp_gateway/server.py:1029-1042`, `complete_tools.py:99-104`
- **Fix**: Remove undocumented properties from schema or implement enforcement.

### DB-260: backend_config_map only supports 2 of 11 backends
- **Files**: `rlm/mcp_gateway/tools/complete_tools.py:35-43`, `server.py:1207-1219`
- **Fix**: Extend `backend_config_map` to all supported `ClientBackend` values.

### DB-263: complete() never updates session.output_bytes — budget bypass
- **File**: `rlm/mcp_gateway/tools/complete_tools.py:265-280`
- **Fix**: Compute `len(json.dumps(output).encode("utf-8"))` and add to `session.output_bytes`.

### DB-264: _truncate_output byte/character mismatch
- **File**: `rlm/mcp_gateway/tools/exec_tools.py:134-141`
- **Fix**: Truncate by encoded byte length, not character count. Return actual truncated size.

### DB-265: _fallback_answer converts dict prompt via str() — lossy repr
- **File**: `rlm/core/rlm.py:672-677`
- **Fix**: Use `json.dumps(message)` instead of `str(message)`.

### DB-266: Anthropic get_last_usage() drops cache token fields
- **File**: `rlm/clients/anthropic.py:196-201`
- **Fix**: Include `cache_creation_input_tokens` and `cache_read_input_tokens` from last tracked values.

### DB-267: add_context discards execute_code return value — errors lost
- **File**: `rlm/environments/local_repl.py:303-324`
- **Fix**: Check `REPLResult.stderr` after each `execute_code` call; raise or log on failure.

### DB-268: VsCodeLM flattens structured messages to text
- **File**: `rlm/clients/vscode_lm.py:115-125`
- **Fix**: Pass structured messages as JSON array through bridge; reconstruct `vscode.LanguageModelChatMessage` objects on TS side.

### DB-272: FINAL missing from RESERVED_TOOL_NAMES
- **File**: `rlm/environments/base_env.py:26-34`
- **Fix**: Add `"FINAL"` to the frozenset.
- **Test**: Verify custom tool named `FINAL` is rejected.

### DB-273: No validation of RLMConfig numeric fields
- **File**: `rlm/core/rlm.py:40-69,95-140`
- **Fix**: Add validation in `_apply_config`: `max_iterations >= 1`, `0 < compaction_threshold_pct <= 1`, etc.
- **Test**: Verify `max_iterations=-1` raises ValueError.

### DB-274: Default model mismatch OpenAI vs extension
- **Files**: `rlm/clients/openai.py:37`, `vscode-extension/package.json:206`
- **Fix**: Align defaults or document intentional difference.

### DB-276: Anthropic/Portkey require api_key as positional — no env var fallback
- **Files**: `rlm/clients/anthropic.py:16`, `portkey.py:18`
- **Fix**: Make `api_key: str | None = None` with fallback to env vars, like OpenAI/Gemini/Azure.

### DB-277: Portkey default model is empty string — delayed failure
- **File**: `rlm/clients/portkey.py:24`
- **Fix**: Validate `model_name` is non-empty in `__init__` or pick a reasonable default.

### DB-278: _update_handler_cost hardcoded rate — max_budget off by 100x
- **File**: `rlm/core/rlm.py:355-370`
- **Fix**: Use model-specific pricing table, or document as token-count proxy instead of dollar budget.

### DB-279: other_backends/other_backend_kwargs desync not validated
- **File**: `rlm/core/rlm.py:108-114,174-176`
- **Fix**: Validate both set or both None, and lengths match.

### DB-280: enable_recursive_subcalls flag never checked — recursion uses different path
- **Files**: `rlm/core/rlm.py:55`, `local_repl.py:239-248`
- **Fix**: Wire flag into `_should_use_recursive_sub_rlm`, or remove from RLMConfig.

### DB-289: LMRequestHandler errors not logged server-side
- **File**: `rlm/core/lm_handler.py:48-55`
- **Fix**: Add `print(f"LMHandler error: {e}", file=sys.stderr)` for generic exceptions.

### DB-290: Zero request/response logging in LMHandler
- **File**: `rlm/core/lm_handler.py:26-56`
- **Fix**: Log request model, prompt length, response time at debug level.

### DB-291: log_metadata() file write has no I/O error handling
- **File**: `rlm/logger/rlm_logger.py:102-107`
- **Fix**: Wrap in `try/except OSError`.

### DB-292: _build_nested_rlm_function swallows all exceptions, returns None
- **File**: `rlm/environments/local_repl.py:280-281`
- **Fix**: Return `f"Error: {e}"` or log the exception.

### DB-293: Daytona get_preview_link failure silently sets broker_url=None
- **File**: `rlm/environments/daytona_repl.py:487-489`
- **Fix**: Log exception and consider raising to fail fast.

### DB-294: _parse_execution_payload returns None on JSON decode failure — no diagnostic
- **Files**: `modal_repl.py:391-393`, `docker_repl.py:275-276`, `daytona_repl.py:636-637`
- **Fix**: Log raw output before returning None.

### DB-295: load_state() silently swallows dill deserialization errors
- **File**: `rlm/environments/exec_script_templates.py:67-68,189-190`
- **Fix**: Print warning to stderr: `print("Warning: failed to load state", file=sys.stderr)`.

### DB-296: send_lm_request/send_lm_request_batched no server-side logging on failure
- **File**: `rlm/core/comms_utils.py:265-266,316-317`
- **Fix**: Log failure to stderr before returning error response.

### DB-297: No structured logging framework (zero `import logging` in core/environments)
- **Files**: All `rlm/core/` and `rlm/environments/`
- **Fix**: Add `logger = logging.getLogger(__name__)` to key modules.

### DB-298: filter_sensitive_keys only matches api+key — misses token/secret/password/auth
- **File**: `rlm/utils/rlm_utils.py:4-12`
- **Fix**: Broaden pattern matching; add value redaction in RLMLogger.

### DB-302: No protocol version field on any boundary
- **Files**: All protocol boundaries (socket, bridge, MCP)
- **Fix**: Add `protocol_version` to `ready`/`configure` messages.

### DB-303: rlm.complete success output missing schema-required response_format
- **Files**: `complete_tools.py:201-218`, `server.py:536-551`
- **Fix**: Add `response_format` to result dict; add undeclared fields to schema.

### DB-304: All error paths violate output schema required fields
- **File**: `rlm/mcp_gateway/tools/complete_tools.py:53-57,263-277`
- **Fix**: Remove `required` constraint from output schema, or add stub values to error responses.

## Priority 4 — Low-Severity / Dead Code

### DB-164: _fallback_answer creates unmanaged client
- **File**: `rlm/core/rlm.py:668-681`
- **Fix**: Reuse existing client or ensure cleanup.

### DB-166: _compact_history hardcodes [:2] assumption
- **File**: `rlm/core/rlm.py:622`
- **Fix**: Dynamically find system message boundary.

### DB-167: asyncio.run() in handler threads
- **File**: `rlm/core/lm_handler.py:121`
- **Fix**: Use thread-local event loop or `asyncio.run()` only when no loop exists.

### DB-168: Usage double-counting risk
- **File**: `rlm/core/lm_handler.py:382-398`
- **Fix**: Exclude default client from `self.clients` iteration or deduplicate.

### DB-170: Exported BLOCKED_MODULES/BLOCKED_FUNCTIONS unused
- **File**: `rlm/core/sandbox/ast_validator.py:61-62`
- **Fix**: Remove public export or use in `restricted_exec.py`.

### DB-178: model_total_tokens dict dead code
- **Files**: All 7 non-vscode clients
- **Fix**: Remove tracking or expose via API.

### DB-179: Ollama /api/generate instead of /api/chat
- **File**: `rlm/clients/ollama.py:95-98`
- **Fix**: Switch to `/api/chat` endpoint for message-list prompts.

### DB-180: vscode_lm.py unused threading lock
- **File**: `rlm/clients/vscode_lm.py:59`
- **Fix**: Remove `self._lock`.

### DB-209: _resolve_repo_root imports nonexistent module
- **File**: `rlm/mcp_gateway/server.py:246-248`
- **Fix**: Remove dead import branch.

### DB-210: score_search_results dead code
- **File**: `rlm/mcp_gateway/search_scorer.py:94-129`
- **Fix**: Remove function or wire into search tools.

### DB-218: Config change restarts backend for non-backend settings
- **File**: `vscode-extension/src/extension.ts:67-75`
- **Fix**: Filter config changes to backend-relevant keys only.

### DB-220: token_counter.py entirely unused
- **File**: `rlm/utils/token_counter.py`
- **Fix**: Delete file (all callers use `token_utils.py`).

### DB-221: check_for_final_answer legacy wrapper
- **File**: `rlm/utils/parsing.py:107-111`
- **Fix**: Delete function.

### DB-229: vars(__builtins__) reveals _safe attribute
- **File**: `rlm/core/sandbox/safe_builtins.py:20-32`
- **Fix**: Remove `_safe` from `dir()`/`vars()` output; or make truly private.

### DB-233: load_context trailing quote causes SyntaxError
- **File**: `rlm/environments/exec_script_templates.py:81-85`
- **Fix**: Use `repr()` or `json.dumps()` for quoting context payloads.

### DB-234: LMResponse.from_dict non-string error coercion
- **File**: `rlm/core/comms_utils.py:94-98`
- **Fix**: Ensure `error` field is always `str | None`.

### DB-251: LMRequestHandler silently drops results on socket error
- **File**: `rlm/core/lm_handler.py:140-155`
- **Fix**: Log warning when socket_send fails after successful LM completion.

### DB-252: _execution_timeout skipped in non-main threads
- **File**: `rlm/environments/local_repl.py:173-188`
- **Fix**: Use threading-based timeout (threading.Timer + interrupt) instead of signal-based.

### DB-253: stdin_reader silently discards JSONDecodeError
- **File**: `vscode-extension/python/rlm_backend.py:397-407`
- **Fix**: Log malformed JSON lines to stderr before discarding.

### DB-254: Docker cleanup docker stop without timeout
- **File**: `rlm/environments/docker_repl.py:328-335`
- **Fix**: Add `--time=5` to docker stop command.

### DB-258: CallHistory from_dict doesn't restore _call_counter
- **File**: `rlm/debugging/call_history.py:56-72`
- **Fix**: Set `_call_counter = max(entry.call_number for entry in entries) + 1`.

### DB-261: exec_run timeout_ms 30000ms cap undocumented
- **File**: `rlm/mcp_gateway/tools/exec_tools.py:43-44`
- **Fix**: Document limit in MCP schema description; or make configurable.

### DB-269: _completion_payload truthiness check — empty collections treated as absent
- **File**: `vscode-extension/python/rlm_backend.py:295-296`
- **Fix**: Use `context if context is not None else prompt`.

### DB-270: RLMChatCompletion.to_dict() passes prompt raw — non-serializable crash
- **File**: `rlm/core/types.py:186-196`
- **Fix**: Apply `_serialize_value(self.prompt)` or validate at entry.

### DB-271: RLMIteration.prompt stores full message history — O(n²) logger memory
- **Files**: `rlm/core/rlm.py:524-548`, `rlm/logger/rlm_logger.py:98-117`
- **Fix**: Store only delta messages per iteration, or omit prompt from logged iterations.

### DB-281: MCP max_depth=10 vs core max_depth=1 naming collision
- **Files**: `rlm/mcp_gateway/session.py:24`, `rlm/core/rlm.py:46`
- **Fix**: Rename session field to `max_session_depth` or align defaults.

### DB-282: Multiple load_dotenv() at import time — env vars frozen at first import
- **Files**: Several `rlm/clients/*.py` modules
- **Fix**: Centralize `load_dotenv()` to `__init__.py`; move `os.getenv()` to `__init__` methods.

### DB-283: Anthropic cache defaults True vs OpenAI defaults False — inconsistent
- **Files**: `rlm/clients/anthropic.py:25`, `openai.py:39`
- **Fix**: Align to opt-in (False) for both, or document intentional difference.

### DB-284: Extension litellm backend aliases only map 3 of 11 backends
- **File**: `vscode-extension/python/rlm_backend.py:210-228`
- **Fix**: Unify routing approach or document divergence.

### DB-299: save_state() silently drops unserializable variables — no warning
- **File**: `rlm/environments/exec_script_templates.py:79-80,198-199`
- **Fix**: Print variable name and type that failed serialization to stderr.

### DB-300: All cleanup() methods silently swallow exceptions — leaked cloud resources
- **Files**: `modal_repl.py:461-463`, `prime_repl.py:691-699`, `daytona_repl.py:715-723`, `local_repl.py:517-519`
- **Fix**: Log exceptions to stderr before `pass`.

### DB-301: CallHistory/GraphTracker not wired into core — dead integration code
- **File**: `rlm/debugging/__init__.py:6-7`
- **Fix**: Wire into LMHandler/RLM loop, or document as opt-in API.

### DB-305: LMResponse.to_dict() explicit Nones vs from_dict() crash on all-None
- **File**: `rlm/core/comms_utils.py:109-149`
- **Fix**: Provide fallback error message in from_dict when all fields None.

### DB-306: RLMChatCompletion.to_dict() conditionally omits metadata — non-uniform
- **File**: `rlm/core/types.py:217-244`
- **Fix**: Always include `"metadata": self.metadata` for consistency.

### DB-307: ConfigureMessage camelCase field matching fragile
- **Files**: `rlm_backend.py:177-189`, `types.ts:64-76`
- **Fix**: Add shared schema definition or reject unknown/missing fields.

### DB-308: Bridge llm_request only carries prompt string — structured messages lost
- **Files**: `rlm/clients/vscode_lm.py:85`, bridge protocol
- **Fix**: Extend to support `messages` array alongside `prompt`.

### DB-309: SessionConfig(**config) crashes on unknown MCP input keys
- **File**: `rlm/mcp_gateway/session.py:107`
- **Fix**: Filter to known field names before constructing SessionConfig.

### DB-310: RLMMetadata.to_dict() serializes callables to repr — non-invertible roundtrip
- **File**: `rlm/core/types.py:343,363`
- **Fix**: Document as one-way logging serialization, or skip non-serializable values.

## Priority 5 — Test Coverage Gaps

_(No items — all P5 test-gap items have been implemented)_
