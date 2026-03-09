# CLAUDE.md
Instructions for Claude Code (claude-code, Cursor with Claude, or any Claude-based agent).
This file supplements `AGENTS.md` (canonical project guide) — do not duplicate its content.

## Quick Reference

- **Build/test**: `make check` (lint + format + test), `make ext-check` (extension)
- **Lint**: `make lint` — ruff check
- **Format**: `make format` — ruff format
- **Test**: `make test` — pytest
- **Typecheck**: `make typecheck` — ty check
- **Extension**: `make ext-check` — typecheck + lint + test

## Orchestrator Prompts

This project uses structured prompt files in `.github/prompts/` for multi-step workflows. Each prompt is idempotent and produces artifacts under `docs/orchestrator/`.

| Prompt | Mode | Purpose | Artifacts |
|--------|------|---------|-----------|
| `research-plan.prompt.md` | Plan | Research upstream, forks, paper, IDE integration methods | `research-findings.md`, `research-backlog.md` |
| `research-agent.prompt.md` | Agent | Read plan artifacts from disk, then implement with test-verified evidence | Updates backlog + findings |
| `debug-plan.prompt.md` | Plan | Tool-assisted quality audit with orthogonal detection passes | `debug-findings.md`, `debug-backlog.md` |
| `debug-agent.prompt.md` | Agent | Fix backlog items with regression-aware verification and evidence gates | Updates backlog + findings |
| `refactor-plan.prompt.md` | Plan | Structural refactoring audit across six dimensions | `refactor-findings.md`, `refactor-backlog.md` |
| `refactor-agent.prompt.md` | Agent | Implement refactors with full migration, no backward compat, evidence gates | Updates backlog + findings |

### Quality Pipeline Philosophy

- **Tool-first detection**: `ruff`, `ty`, `pylance`, `tsc`, `eslint`, `pytest` for deterministic findings; model analysis supplements only
- **Orthogonal passes**: Tool errors → protocol/schema → incomplete implementations → complexity → test gaps
- **Evidence-based backlog**: Items cite tool output or file:line references, not narrative descriptions
- **Regression-aware fixes**: Test requirements and tool re-checks before marking items done
- **Exposure tracking**: Fixes that reveal latent issues get new backlog items, not ignored
- **Acknowledged limits**: Cannot find runtime bugs, race conditions, or behavioral correctness issues

### Workflow

1. Run a **plan** prompt first — it researches/audits and writes findings and backlog artifacts directly to disk
2. Run the matching **agent** prompt — it reads artifacts from disk and implements backlog items
3. Plans write only to `docs/orchestrator/` artifact files; agents implement and verify with `make check`
4. Agent prompts enforce **evidence gates**: tool verification, test requirements, and regression checks
5. Research, debug, and refactor backlogs are separate — agents do not cross boundaries

### Artifact Ownership

| Artifact | Written by | Read by | Mutated by |
|----------|-----------|---------|------------|
| `docs/orchestrator/research-findings.md` | research-plan | research-agent, debug-plan, debug-agent, refactor-plan, refactor-agent | research-agent (remove completed) |
| `docs/orchestrator/research-backlog.md` | research-plan | research-agent, debug-plan, debug-agent, refactor-plan, refactor-agent | research-agent (remove completed) |
| `docs/orchestrator/debug-findings.md` | debug-plan | debug-agent, research-plan, research-agent, refactor-plan, refactor-agent | debug-agent (remove completed) |
| `docs/orchestrator/debug-backlog.md` | debug-plan | debug-agent, research-plan, research-agent, refactor-plan, refactor-agent | debug-agent (remove completed) |
| `docs/orchestrator/refactor-findings.md` | refactor-plan | refactor-agent, research-plan, research-agent, debug-plan, debug-agent | refactor-agent (remove completed) |
| `docs/orchestrator/refactor-backlog.md` | refactor-plan | refactor-agent, research-plan, research-agent, debug-plan, debug-agent | refactor-agent (remove completed) |
| `docs/orchestrator/plan.md` | Manual / orchestrator | All prompts | Never (propose amendments only) |
| `docs/orchestrator/state.json` | All agents | All prompts | All agents (append to applied/verified) |

## Detailed Instruction Files

Workspace-level instruction sets are in `.github/instructions/`:

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

## Conventions (defer to AGENTS.md for details)

- **Python**: ruff, explicit types, snake_case, PascalCase classes, UPPER_CASE constants, fail-fast errors
- **TypeScript**: strict mode, no `any`, exactOptionalPropertyTypes, ESLint strictTypeChecked
- **Dataclasses**: manual `to_dict()`/`from_dict()` — no Pydantic
- **Dependencies**: Avoid new core deps; use optional extras
- **Testing**: pytest, class-based grouping, mock_lm.py, plain assert
- **Diffs**: Small, focused, one concern per change

## Project Goal

Get the RLM architecture seamlessly working with:
1. **VS Code's built-in Copilot AI Agent Chat** — via Chat Participant API + optional MCP
2. **Cursor's built-in AI Agent Chat** — via MCP gateway tools

See `docs/integration/playbooks.md` for current setup instructions.
