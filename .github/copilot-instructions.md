# Copilot Instructions — RLM (Recursive Language Models)

Instructions for GitHub Copilot (VS Code Chat, Agent Mode, and Copilot Extensions).
This file supplements `AGENTS.md` (canonical project guide) — do not duplicate its content.

Detailed workspace-level instruction sets are in `.github/instructions/`:

| File | Covers |
|------|--------|
| `project-overview.instructions.md` | Architecture, layout, data flow, IDE integration summary |
| `python-conventions.instructions.md` | Formatting, typing, naming, errors, complexity, dataclass patterns |
| `typescript-conventions.instructions.md` | Strict mode, typing rules, extension architecture, security |
| `testing.instructions.md` | pytest patterns, mock LM, class-based tests, CI workflows |
| `code-patterns.instructions.md` | Dataclass serialization, factory functions, socket IPC, singletons, builtins |
| `developing-clients.instructions.md` | How to add a new LM client (BaseLM subclass) |
| `developing-environments.instructions.md` | How to add a new REPL environment (BaseEnv subclass) |
| `mcp-gateway.instructions.md` | MCP tool list, server modes, security, search patterns |
| `security.instructions.md` | Sandbox tiers, AST validation, extension security, env vars |
| `cross-boundary.instructions.md` | Python↔TypeScript protocol, socket protocol, MCP contracts |
| `ide-integration.instructions.md` | VS Code chat participant, Cursor MCP, settings, provider modes |
| `orchestrator-workflow.instructions.md` | Plan/agent prompts, backlog formats, evidence gates |
| `contributing.instructions.md` | Quick start, PR requirements, scope rules |
| `logging-trajectory.instructions.md` | RLMLogger, JSONL schema, VerbosePrinter, trajectory data flow |
| `debugging.instructions.md` | CallHistory, GraphTracker, export formats, NetworkX integration |
| `rlm-config-features.instructions.md` | Compaction, budgets, custom tools, callbacks, recursive subcalls |
| `token-management.instructions.md` | Token counting, model context limits, tiktoken, heuristic estimates |

## Quick Reference

**Paper**: [Recursive Language Models](https://arxiv.org/abs/2512.24601)

### Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Core | `rlm/core/` | RLM loop, LM handler, iteration, comms, types, sandbox |
| Clients | `rlm/clients/` | LM API integrations (OpenAI, Anthropic, Gemini, etc.) |
| Environments | `rlm/environments/` | REPL execution: Local, Docker, Modal, Prime, Daytona, E2B |
| MCP Gateway | `rlm/mcp_gateway/` | MCP server for IDE integration (VS Code + Cursor) |
| Extension | `vscode-extension/` | VS Code Chat Participant + Python backend bridge |
| Sandbox | `rlm/core/sandbox/` | AST validation, builtins restriction, restricted exec |
| Logger | `rlm/logger/` | JSONL trajectory logger, Rich console printer |
| Utils | `rlm/utils/` | Parsing, prompts, token counting |
| Debugging | `rlm/debugging/` | Call history, graph tracking |

### Build and Verify

```bash
make check        # lint + format + test (Python)
make ext-check    # typecheck + lint + test (Extension)
make lint         # ruff check
make format       # ruff format
make test         # pytest
make typecheck    # ty check
```

### Code Style (Summary)

**Python**: ruff (line-length=100, Python 3.11); explicit types with `X | Y` union syntax; snake_case methods, PascalCase classes, UPPER_CASE constants; fail fast, fail loud; max 3 nesting levels, 50 lines/function, 5 params; `@dataclass` + manual `to_dict()`/`from_dict()` (no Pydantic); context managers for resources; `TYPE_CHECKING` guards for circular imports.

**TypeScript**: All strict flags + `exactOptionalPropertyTypes`; no `any` (use `unknown` + type guards); ESLint `strictTypeChecked` with `no-explicit-any: "error"`, complexity cap 15; zero runtime npm dependencies.

### Key Patterns

- **LM Client**: `BaseLM` → `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`
- **Environment**: `NonIsolatedEnv`/`IsolatedEnv` → `setup`, `load_context`, `execute_code`, `cleanup`
- **RLM Loop**: `RLM.completion(prompt)` → iterative REPL → `FINAL(answer)` or `FINAL_VAR(var)`
- **Sub-LLM calls**: `llm_query(prompt)` / `llm_query_batched(prompts)` inside REPL code
- **Socket IPC**: 4-byte big-endian length prefix + UTF-8 JSON between handler and environment
- **Factory functions**: `get_client()` and `get_environment()` with lazy imports
- **Dataclass serialization**: manual `to_dict()`/`from_dict()` — no Pydantic
- **Two sandbox tiers**: strict builtins for MCP exec, relaxed builtins for REPL
- **Thread-safe IO**: `threading.Lock()` for stdout in sidecar processes
- **Orphan protection**: Parent PID monitoring in Python sidecar

### Testing

- `pytest` under `tests/`; class-based grouping; plain `assert`; no pytest fixtures
- Mock LM: `tests/mock_lm.py` (direct object creation)
- `pytest.importorskip` for optional deps
- Extension tests: plain Node.js scripts (`node out/*.test.js`)

### IDE Integration

| IDE | Entry Point | LLM Source | Config |
|-----|------------|------------|--------|
| VS Code | Chat `@rlm` | Copilot (vscode.lm) or API key | settings.json (`rlm.*`) |
| Cursor | MCP tools | Cursor LLM + optional API key | `.cursor/mcp.json` |

See `docs/integration/playbooks.md` for setup instructions.

### Orchestrator Prompts

Plan/agent pairs in `.github/prompts/`: research, debug, refactor. Plans write to `docs/orchestrator/`. Agents implement with evidence gates. Backlogs are separate per domain. See `orchestrator-workflow.instructions.md` for details.
