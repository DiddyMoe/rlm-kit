# Contributing Guide

## Quick Start

```bash
# Install uv (first time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <repo-url>
cd rlm-kit
uv sync

# Install dev + test dependencies
uv sync --group dev --group test

# Install pre-commit hooks
uv run pre-commit install

# Run all checks
make check          # Python: lint + format + test
make ext-check      # Extension: typecheck + lint + test
```

## Before Every PR

```bash
# Run all checks
make check && make ext-check

# Or individually
make lint           # ruff check
make format         # ruff format
make test           # pytest
make typecheck      # ty check

# Pre-commit hooks
uv run pre-commit run --all-files
```

## PR Requirements

- Small, focused diffs — one concern per change
- Update tests when changing functionality
- Update docs when behavior changes
- Delete dead code (don't comment it out)
- Avoid touching `core/` files unless necessary
- No new core dependencies without approval
- All Python code must pass ruff
- All TypeScript code must pass tsc + eslint

## Key Principles (from CONTRIBUTING.md)

### Urgent TODOs
- Additional sandboxes (new environment implementations)
- Persistent REPL across multi-turn sessions
- Better unit tests (with most PRs)
- Bug finding and reporting

### Nice-to-Have
- Multi-modal / arbitrary input support
- File-system based environments
- Improved visualization UI
- Better data storage for training/statistics

### Advanced
- Pipelining / asynchrony of LM calls
- Efficient prefix caching
- Training models to work as RLMs

## Scope Rules

**In scope** for this fork:
- IDE integration fidelity (VS Code Agent Chat + Cursor MCP)
- Observability and safety improvements
- Low-risk, isolated code changes
- Documentation improvements

**Out of scope** without explicit approval:
- Core RLM loop/recursion strategy changes
- Trajectory/log schema changes
- New dependencies beyond patch/minor
- Major refactors or renames

## File-Level Guidelines

| Area | Convention |
|------|-----------|
| `rlm/core/` | Minimal changes; keep simple and readable |
| `rlm/clients/` | Follow `BaseLM` pattern; register in `__init__.py` |
| `rlm/environments/` | Follow `BaseEnv` pattern; register in `__init__.py` |
| `rlm/mcp_gateway/` | Can import from `core/` and `utils/` |
| `vscode-extension/` | Zero runtime npm deps; strict TypeScript |
| `tests/` | Class-based, no fixtures, plain assert, mock_lm.py |
| `docs/` | Keep concise and actionable |
