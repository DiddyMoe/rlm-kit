# Contributing

Guidelines for contributing to the RLM repository.

---

## General

- Avoid changing `core/` unless necessary; keep the repo minimal and readable.
- Prefer small, focused PRs; one logical change per PR.
- Update docs and tests when behavior changes; delete dead code.
- Run checks before opening a PR (see below).
- **Upstream sync (rlm-kit):** This repo extends alexzhang13/rlm. Periodically merge or track upstream; keep MCP gateway and AgentRLM as an additional layer. See PROJECT_TECHNICAL_OVERVIEW.md §9 for conflict resolution and tracked issues/PRs.

---

## Before a PR

```bash
uv run ruff check --fix .
uv run ruff format .
uv run pre-commit run --all-files
uv run pytest
```

Ensure:

- Style and lint pass.
- Tests pass.
- Docs and tests are updated if needed.
- No unnecessary or guarded dead code.

---

## Scope

- **Urgent:** Additional sandboxes, persistent REPL across client, benchmarks/examples, better docs and unit tests, bug reports.
- **Nice to have:** Multi-modal/arbitrary input, filesystem+bash environments, improved visualizer UI, better trajectory data for training.
- **Future:** Pipelining/async LM calls, prefix caching, training models for RLM use (see e.g. verifiers `rlm_env`).

---

## Development setup

See [Agents & contributors](../reference/agents.md) for:

- uv and venv setup
- LM client and environment implementation
- AgentRLM and MCP integration
- Architecture (environment ↔ LM handler)

---

## CI

- **Style:** `ruff` lint and format (see `.github/workflows/style.yml`).
- **Tests:** pytest on multiple Python versions (see `.github/workflows/test.yml`). Modal and API-key–dependent tests are excluded in CI; run them locally when needed.

Running locally like CI:

```bash
python -m pytest tests/ -v \
  --ignore=tests/repl/test_modal_repl.py \
  --ignore=tests/clients/
```

See `.github/workflows/README.md` for workflow details and branch protection suggestions.
