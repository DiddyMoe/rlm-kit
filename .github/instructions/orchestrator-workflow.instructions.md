# Orchestrator Workflow

This project uses structured prompt files in `.github/prompts/` for multi-step workflows. Each prompt is idempotent — re-running produces the same effect without duplication.

## Prompt Overview

| Prompt | Mode | Purpose |
|--------|------|---------|
| `research-plan.prompt.md` | Plan | Research upstream repos, forks, paper, IDE integration methods |
| `research-agent.prompt.md` | Agent | Read plan artifacts, implement backlog items with evidence gates |
| `debug-plan.prompt.md` | Plan | Tool-assisted quality audit with orthogonal detection passes |
| `debug-agent.prompt.md` | Agent | Fix backlog items with regression-aware verification |
| `refactor-plan.prompt.md` | Plan | Structural refactoring audit across six dimensions |
| `refactor-agent.prompt.md` | Agent | Implement refactors with full migration, no backward compat |

## How to Use

1. Run a **plan** prompt first — it researches/audits and writes findings + backlog artifacts to `docs/orchestrator/`
2. Run the matching **agent** prompt — it reads artifacts from disk and implements backlog items
3. Plans write only to `docs/orchestrator/` artifact files; agents implement and verify with `make check`
4. Research, debug, and refactor backlogs are separate — agents stay in their lane
5. Agent prompts enforce **evidence gates**: tool verification, test requirements, regression checks

## Quality Pipeline Philosophy

- **Tool-first detection**: `ruff`, `ty`, `pylance`, `tsc`, `eslint`, `pytest` for deterministic findings; model analysis supplements only
- **Orthogonal passes**: Tool errors → protocol/schema → incomplete implementations → complexity → test gaps
- **Evidence-based backlog**: Items cite tool output or file:line references, not narrative descriptions
- **Regression-aware fixes**: Test requirements and tool re-checks before marking items done
- **Exposure tracking**: Fixes that reveal latent issues get new backlog items
- **Acknowledged limits**: Cannot find runtime bugs, race conditions, or behavioral correctness issues

## Artifact Ownership

| Artifact | Written by | Read by | Mutated by |
|----------|-----------|---------|------------|
| `docs/orchestrator/research-findings.md` | research-plan | research-agent, debug-plan, debug-agent, refactor-plan, refactor-agent | research-agent (remove completed) |
| `docs/orchestrator/research-backlog.md` | research-plan | research-agent, debug-plan, debug-agent, refactor-plan, refactor-agent | research-agent (remove completed) |
| `docs/orchestrator/debug-findings.md` | debug-plan | debug-agent, research-plan, research-agent, refactor-plan, refactor-agent | debug-agent (remove completed) |
| `docs/orchestrator/debug-backlog.md` | debug-plan | debug-agent, research-plan, research-agent, refactor-plan, refactor-agent | debug-agent (remove completed) |
| `docs/orchestrator/refactor-findings.md` | refactor-plan | refactor-agent, research-plan, research-agent, debug-plan, debug-agent | refactor-agent (remove completed) |
| `docs/orchestrator/refactor-backlog.md` | refactor-plan | refactor-agent, research-plan, research-agent, debug-plan, debug-agent | refactor-agent (remove completed) |
| `docs/orchestrator/plan.md` | Manual | All prompts | Never (propose amendments only) |
| `docs/orchestrator/state.json` | All agents | All prompts | All agents |

## Cross-Pipeline Rules

- **Plans** read all other pipelines' backlogs/findings to avoid duplication
- **Agents** read other pipelines' findings for context but must not implement their items (research-agent skips DB/RT items, debug-agent skips RF/RT items, refactor-agent skips RF/DB items)
- Priority auto-stop thresholds differ per agent: research stops at P4, debug at P5, refactor at P6

## Backlog Item Formats

### Research: `RF-{NNN}`
Fields: ID, Title, Source, Category, Impact, Effort, Description, Files affected, Test strategy, Depends on

### Debug: `DB-{NNN}`
Fields: ID, Title, Category, Evidence, Severity, File(s), Line(s), Description, Test requirement, Depends on

### Refactor: `RT-{NNN}`
Fields: ID, Title, Category, Evidence, Severity, File(s), Line(s), Description, Migration scope, Test requirement, Depends on

## Evidence Gates (Agent Protocol)

Every fix/implementation must pass before marking complete:

1. **Tool verification**: `make check` and/or `make ext-check` must pass
2. **Regression check**: Original error gone, no new errors introduced
3. **Test requirement**: Tests exist and pass (mandatory for Priority 2+ items)
4. **Exposure check**: Review touched files for newly visible issues
5. **Artifact update**: Remove completed items from backlog and findings

## Verification Commands

```bash
# Python-only changes
make lint && make format && make test

# Extension-only changes
make ext-check

# Both sides
make check && make ext-check

# Complexity check
uv run radon cc {file} -s -n B

# Circular import check
python -c "import rlm"
python -c "from rlm import RLM"
```

## Pipeline Limitations

This pipeline cannot:
- Find runtime-only bugs, race conditions, or environment-specific failures
- Guarantee exhaustive coverage
- Verify behavioral correctness
- Prevent all regressions
