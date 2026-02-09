# Failure modes

Cause, detection, mitigation. File pointers for implementation.

## Provider errors

- **Cause**: API key missing/invalid, rate limit, timeout, model unavailable.
- **Detection**: Exception from LM client; `LMResponse.error` in rlm/core/comms_utils.py; extension shows error in Chat.
- **Mitigation**: rlm/core/retry.py (`retry_with_backoff`); fail fast on missing key; playbooks in docs/integration/playbooks.md.

## Socket LM requests (env → LMHandler)

- **Cause**: Transient connection/timeout errors when environments call `send_lm_request` / `send_lm_request_batched` (rlm/core/comms_utils.py).
- **Mitigation**: Both helpers wrap `socket_request` in `retry_with_backoff` (max_attempts=3, ConnectionError/TimeoutError/OSError). No public API change.

## Recursion runaway

- **Cause**: max_iterations/max_depth too high; model never emits FINAL.
- **Detection**: Default answer after exhausting max_iterations (rlm/core/rlm.py); extension can report budgetExhausted.
- **Mitigation**: ABSOLUTE_MAX_ITERATIONS=50 (rlm/core/constants.py); config caps (maxIterations in extension); document defaults in playbooks.

## Cancellation

- **Cause**: User cancel; process kill; timeout.
- **Detection**: Process exit or timeout; no in-loop cancellation token today.
- **Mitigation**: Document current behavior (no mid-completion cancel); future design for abort required (approval).

## Concurrency

- **Cause**: Multiple completions; shared state in backend or bridge.
- **Detection**: Generation counter in backendBridge; stdout lock in rlm_backend.py.
- **Mitigation**: Session-scoped state; document assumptions in docs/quality and playbooks.

## Context overflow

- **Cause**: Sub-call prompt exceeds MAX_SUB_CALL_PROMPT_CHARS or model context window.
- **Detection**: Provider error (e.g. context_length_exceeded).
- **Mitigation**: rlm/core/constants.py, rlm/mcp_gateway/constants.py; document in failure_modes and ide_touchpoints.

## Sandbox

- **Cause**: Malicious or unsafe code in REPL or MCP exec.
- **Detection**: rlm/core/sandbox/ast_validator.py; restricted builtins in safe_builtins.py; path checks in rlm/mcp_gateway/validation.py.
- **Mitigation**: Document two surfaces (LocalREPL vs exec_tools) in docs/quality or security note; safe defaults; path validation.

## Serialization

- **Cause**: Isolated env state (dill) load/save failures; version or env mismatch.
- **Detection**: Load/save errors in isolated envs (e.g. modal_repl, prime_repl, daytona_repl).
- **Mitigation**: Document lifecycle; add persistence tests where feasible.
