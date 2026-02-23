# Copilot Instructions — RLM (Recursive Language Models)
Instructions for GitHub Copilot (VS Code Chat, Agent Mode, and Copilot Extensions).
This file supplements `AGENTS.md` (canonical project guide) — do not duplicate its content.

## Project Overview

RLM is a task-agnostic inference engine that lets language models handle large contexts via programmatic examination, decomposition, and recursive self-calls through a REPL. This fork focuses on seamless IDE integration with VS Code Copilot Agent Chat and Cursor Agent Chat.

**Paper**: [Recursive Language Models](https://arxiv.org/abs/2512.24601)

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Core | `rlm/core/` | RLM loop, LM handler, iteration, comms, types |
| Clients | `rlm/clients/` | LM API integrations (OpenAI, Anthropic, Gemini, etc.) |
| Environments | `rlm/environments/` | REPL execution: Local, Docker, Modal, Prime, Daytona |
| MCP Gateway | `rlm/mcp_gateway/` | MCP server for Cursor integration |
| Extension | `vscode-extension/` | VS Code Chat Participant + Python backend bridge |
| Sandbox | `rlm/core/sandbox/` | AST validation, builtins restriction |

## Build and Verify

```bash
make check        # lint + format + test (Python)
make ext-check    # typecheck + lint + test (Extension)
make lint         # ruff check
make format       # ruff format
make test         # pytest
make typecheck    # ty check
```

## Code Style

### Python
- **Formatting**: ruff (line-length=100, target Python 3.11)
- **Typing**: Explicit types on all function signatures; `X | Y` union syntax; no `Any` or `# type: ignore` without justification
- **Naming**: snake_case methods/variables, PascalCase classes, UPPER_CASE constants
- **Errors**: Fail fast, fail loud — no silent fallbacks or bare `except:`
- **Complexity**: Max 3 nesting levels, max 50 lines per function, max 5 parameters
- **Patterns**: `@dataclass` + manual `to_dict()`/`from_dict()` (no Pydantic); context managers for resources; `TYPE_CHECKING` guards for circular imports

### TypeScript
- **Strict mode**: All strict flags, `exactOptionalPropertyTypes`
- **No `any`**: Use `unknown` + type guards
- **ESLint**: `strictTypeChecked`, `no-explicit-any: "error"`, complexity cap 15
- **Zero runtime npm dependencies**

## Orchestrator Prompts

This project uses structured prompt files in `.github/prompts/` for multi-step workflows:

| Prompt | Mode | Purpose |
|--------|------|---------|
| `research-plan.prompt.md` | Plan | Research upstream, forks, paper, IDE integration |
| `research-agent.prompt.md` | Agent | Read plan artifacts from disk, then implement |
| `debug-plan.prompt.md` | Plan | Tool-assisted quality audit with orthogonal detection passes |
| `debug-agent.prompt.md` | Agent | Fix backlog items with regression-aware verification |
| `refactor-plan.prompt.md` | Plan | Structural refactoring audit across six dimensions |
| `refactor-agent.prompt.md` | Agent | Implement refactors with full migration, no backward compat |

### Quality Pipeline Philosophy

- **Tool-first detection**: `ruff`, `ty`, `tsc`, `eslint`, `pytest` for deterministic findings; model analysis supplements only
- **Orthogonal passes**: Tool errors → protocol/schema → incomplete implementations → complexity → test gaps
- **Evidence-based backlog**: Items cite tool output or file:line references, not narrative descriptions
- **Regression-aware fixes**: Test requirements and tool re-checks before marking items done
- **Exposure tracking**: Fixes that reveal latent issues get new backlog items
- **Acknowledged limits**: Cannot find runtime bugs, race conditions, or behavioral correctness issues

### How to Use

1. Run a **plan** prompt to research/audit — it writes findings and backlog artifacts directly to disk
2. Run the matching **agent** prompt to read artifacts from disk and implement backlog items
3. Plans write only to `docs/orchestrator/` artifact files; agents implement and verify with `make check`
4. Research and debug backlogs are separate — agents stay in their lane
5. Agent prompts enforce **evidence gates**: tool verification, test requirements, regression checks

### Orchestrator Artifacts (docs/orchestrator/)

| File | Purpose |
|------|---------|
| `research-findings.md` | Research analysis (completed items removed) |
| `research-backlog.md` | Research implementation queue (items removed when done) |
| `debug-findings.md` | Codebase audit results (completed items removed) |
| `debug-backlog.md` | Debug fix queue (items removed when done) |
| `plan.md` | Canonical orchestrator plan (do not modify without amendment) |
| `state.json` | Machine-readable project state |
| `run_log.md` | Append-only execution log |

## Key Patterns

- **LM Client**: `BaseLM` → `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`
- **Environment**: `NonIsolatedEnv`/`IsolatedEnv` → `setup`, `load_context`, `execute_code`, `cleanup`
- **RLM Loop**: `RLM.completion(prompt)` → iterative REPL → `FINAL(answer)` or `FINAL_VAR(var)`
- **Sub-LLM calls**: `llm_query(prompt)` / `llm_query_batched(prompts)` inside REPL code
- **Socket IPC**: 4-byte big-endian length prefix + UTF-8 JSON between handler and environment
- **Factory functions**: `get_client()` and `get_environment()` with lazy imports

## Testing

- `pytest` under `tests/`; class-based grouping; plain `assert`
- Mock LM: `tests/mock_lm.py`
- No pytest fixtures — direct object creation
- `pytest.importorskip` for optional deps

## IDE Integration Docs

- Setup playbooks: `docs/integration/playbooks.md`
- IDE adapter mapping: `docs/integration/ide_adapter.md`
- IDE matrix: `docs/integration/ide_matrix.md`
- IDE touchpoints: `docs/integration/ide_touchpoints.md`
