# Cross-Boundary Development

Rules for changes that span Python ↔ TypeScript ↔ MCP boundaries. These boundaries are the highest risk for regressions.

## Python ↔ TypeScript Protocol (BackendBridge ↔ rlm_backend.py)

**Protocol**: JSON-over-newline on stdin/stdout

### Message Types

**Outbound (Extension → Python)** — 7 types:
- `{"type": "configure", "provider": "...", "backend": "...", "model": "...", ...}` — set provider, backend, model (flat fields, not nested)
- `{"type": "completion", "nonce": "...", "prompt": "...", ...}` — start RLM completion
- `{"type": "execute", "nonce": "...", "code": "..."}` — execute code
- `{"type": "cancel"}` — request soft cancellation
- `{"type": "llm_response", "nonce": "...", "text?": "...", "error?": "...", "promptTokens?": N, "completionTokens?": N}` — response to sub-LLM request (builtin mode)
- `{"type": "ping", "nonce": "..."}` — health check
- `{"type": "shutdown"}` — graceful shutdown

**Inbound (Python → Extension)** — 9 types:
- `{"type": "ready"}` — backend process ready
- `{"type": "configured", "provider": "...", "backend": "..."}` — configuration acknowledged
- `{"type": "result", "nonce": "...", "text": "...", ...}` — completion result
- `{"type": "exec_result", "nonce": "...", ...}` — code execution result
- `{"type": "llm_request", "nonce": "...", "prompt": "...", ...}` — sub-LLM request (builtin mode)
- `{"type": "progress", "nonce": "...", ...}` — iteration progress
- `{"type": "chunk", "nonce": "...", "text": "..."}` — streaming chunk
- `{"type": "error", "nonce": "...", "error": "..."}` — error
- `{"type": "pong", "nonce": "..."}` — health check response

### Type Definitions

Full protocol types are defined in `vscode-extension/src/types.ts`:
- `OutboundMessage` — discriminated union of all outbound types
- `InboundMessage` — discriminated union of all inbound types
- `PendingRequest<T>` — nonce-based request tracking with resolve/reject

### Rules When Changing Protocol

1. Update BOTH `backendBridge.ts` AND `rlm_backend.py` simultaneously
2. Add/update a contract test in `tests/test_rlm_backend_protocol.py`
3. Run both `make check` AND `make ext-check` immediately after
4. Update `vscode-extension/src/types.ts` if message types change

## Socket Protocol (Environment ↔ LMHandler)

**Protocol**: 4-byte big-endian length prefix + UTF-8 JSON payload

```python
# rlm/core/comms_utils.py
def socket_send(sock: socket.socket, data: dict) -> None:
    payload = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)
```

### Dataclasses

- `LMRequest`: `prompt`, `prompts` (batched), `model`, `model_preferences`, `depth`
- `LMResponse`: `error`, `chat_completion`, `chat_completions`

### Rules When Changing Socket Protocol

1. Update `comms_utils.py` (both `LMRequest` and `LMResponse`)
2. Update `lm_handler.py` (`LMRequestHandler.handle()`)
3. Update environment code that constructs requests
4. Add/update serialization round-trip test in `tests/test_comms_utils.py`

## MCP Tool Contracts

When changing MCP tool signatures:

1. Update tool implementation in `rlm/mcp_gateway/tools/`
2. Update tool registration in `rlm/mcp_gateway/server.py`
3. Update documentation in `docs/integration/ide_adapter.md`
4. Update Cursor rules if tool behavior changes
5. Update playbooks in `docs/integration/playbooks.md`

## Dataclass Serialization

When changing `@dataclass` types:

1. Update both `to_dict()` and `from_dict()` — they must be exact inverses
2. Add/update round-trip test in `tests/test_types.py`
3. If the type crosses Python ↔ TypeScript boundary, update both sides
4. If the type is used in JSONL trajectories, document the schema change

## Dependency Direction

Dependencies must flow in one direction:

```
core/  ←  clients/
core/  ←  environments/
core/  ←  mcp_gateway/
core/  ←  utils/
utils/ ←  mcp_gateway/
```

**Violations to avoid**:
- `core/` must NOT import from `clients/`, `environments/`, or `mcp_gateway/`
- `utils/` must NOT import from `clients/` or `environments/`
- Use `TYPE_CHECKING` guards when type annotations create circular imports

## Cross-Boundary Testing

After any cross-boundary change, always run the full verification:

```bash
make check && make ext-check
```

For protocol changes specifically:
```bash
# Verify contract tests
uv run pytest tests/test_rlm_backend_protocol.py tests/test_comms_utils.py -v

# Verify imports still work
python -c "import rlm"
python -c "from rlm import RLM"
python -c "from rlm.clients import get_client"
python -c "from rlm.environments import get_environment"
```
