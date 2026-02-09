# Prioritized proposal

Ranked by impact, risk, and effort. For IDE-facing items: 2–3 options and recommended option.

---

## 1. IDE compatibility

**Impact**: High. **Risk**: Medium. **Effort**: Medium.

- **Scope**: VS Code agents/tools/MCP; Cursor modes/rules/MCP; config discovery; version compatibility.

**Options**:
- **A)** Keep current split: VS Code = Chat Participant + optional MCP in settings; Cursor = MCP only. Document playbooks only.
- **B)** Add a single “IDE adapter” doc that maps both IDEs to the same tool/contract table and config matrix; add minimal compatibility tests (e.g. “MCP gateway starts”, “extension builds”).
- **C)** Introduce a small compatibility layer (e.g. env or config flags) to toggle VS Code vs Cursor behavior in one code path; unify where possible.

**Recommendation**: **B**. Improves clarity and verification without changing behavior. A is low effort but leaves gaps; C is higher risk and effort.

---

## 2. Tool surfaces (MCP)

**Impact**: High. **Risk**: Low. **Effort**: Low–Medium.

- **Scope**: MCP server packaging (optional extra, entry point), tool discovery, permissions, stable tool contracts (names, args).

**Options**:
- **A)** Document current tool names and args in ide_touchpoints and README; no pyproject change.
- **B)** Add optional extra `[mcp]` in pyproject.toml with dependency `mcp`; document HTTP deps (fastapi, uvicorn) for HTTP mode. Keep entry point as `scripts/rlm_mcp_gateway.py`.
- **C)** Add setuptools entry point for the MCP server so IDEs can discover it via package metadata; optional extra as in B.

**Recommendation**: **B** first (explicit deps, low risk). C only if IDE tooling expects entry points (approval for packaging change).

---

## 3. Observability

**Impact**: High. **Risk**: Low. **Effort**: Medium.

- **Scope**: Trajectory integrity, schema validation, log rotation under concurrency, run IDs.

**Options**:
- **A)** Document current JSONL schema and RLMLogger behavior; add run_id (or equivalent) to state/orchestrator docs only.
- **B)** Add optional schema validation (e.g. load JSONL and validate against a fixed schema) in dev/tests; no change to production write path.
- **C)** Add log rotation or size limits in RLMLogger when writing from multiple processes/sessions; keep schema unchanged.

**Recommendation**: **A** plus **B** in tests only. Schema change or production log rotation = approval.

---

## 4. Sandbox hardening

**Impact**: Medium. **Risk**: Medium. **Effort**: Medium.

- **Scope**: Safer defaults, resource limits, timeouts, filesystem/network policies; align restricted_exec vs MCP constants.

**Options**:
- **A)** Document the two surfaces (LocalREPL vs MCP exec_tools) and current limits in docs/quality or security note; no code change.
- **B)** Align constants (e.g. timeouts, code size) between rlm/core/sandbox and rlm/mcp_gateway/constants; keep behavior compatible.
- **C)** Tighten LocalREPL safe_builtins (e.g. remove open) or add AST check; high risk of breaking existing flows.

**Recommendation**: **A** now; **B** as small, approved patches. **C** requires explicit approval and testing.

---

## 5. Reliability

**Impact**: High. **Risk**: Low. **Effort**: Medium.

- **Scope**: Provider error taxonomy, retries/backoff (rlm/core/retry.py), cancellation, streaming, concurrency safety.

**Options**:
- **A)** Document provider error handling and retry usage; add failure_modes.md (Phase 2B).
- **B)** Use retry_with_backoff in more call sites (e.g. socket send/recv or LM client calls) where appropriate; keep same public API.
- **C)** Add cancellation support (e.g. token or timeout) for long-running completion; design required.

**Recommendation**: **A** in Phase 2B; **B** as AUTO-APPLY only where clearly safe; **C** needs design and approval.

---

## 6. Determinism

**Impact**: Medium. **Risk**: Low. **Effort**: Low.

- **Scope**: Stable run IDs, reproducible configs, stable serialization of traces.

**Options**:
- **A)** Document how run_id (or equivalent) is produced today (e.g. RLMLogger timestamp + uuid); record in state.json when runs are logged.
- **B)** Add an explicit run_id field to RLMMetadata or first JSONL line; keep backward compatible (optional field).
- **C)** Freeze config snapshot per run and write to trajectory; schema change.

**Recommendation**: **A** first. **B** if needed for tooling; approval for schema. **C** = approval.

---

## 7. Testing

**Impact**: High. **Risk**: Low. **Effort**: Medium.

- **Scope**: Golden trajectories, IDE-facing integration harnesses, mocks for providers and tools.

**Options**:
- **A)** Add tests that run a short RLM scenario (e.g. mock LM) and assert on trajectory shape (no schema change); optional golden file.
- **B)** Add “MCP gateway starts in stdio” and “extension build + typecheck” to CI; no new test content.
- **C)** Full IDE integration harness (e.g. headless VS Code/Cursor); high effort.

**Recommendation**: **A** + **B**. **B** is AUTO-APPLY; **A** is high value, low risk. **C** later if needed.

---

## 8. Docs — playbooks

**Impact**: High. **Risk**: None. **Effort**: Low.

- **Scope**: “Use from VS Code Agent Chat” and “Use from Cursor Agent Chat” playbooks.

**Options**:
- **A)** Single doc (e.g. docs/integration/playbooks.md) with two sections: VS Code steps, Cursor steps (MCP, tools, config).
- **B)** Two separate docs under docs/integration/.
- **C)** Extend README only with short “Quick start” for each IDE.

**Recommendation**: **A**. One place to maintain; clear separation of IDE flows.
