.PHONY: help install install-dev install-modal run-all \
        quickstart docker-repl lm-repl modal-repl \
        lint format test typecheck check \
        ext-install ext-build ext-typecheck ext-lint ext-test ext-check ext-clean

help:
	@echo "RLM Examples Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install        - Install base dependencies with uv"
	@echo "  make install-dev    - Install dev dependencies with uv"
	@echo "  make install-modal  - Install modal dependencies with uv"
	@echo "  make run-all        - Run all examples (requires all deps and API keys)"
	@echo ""
	@echo "Examples:"
	@echo "  make quickstart     - Run quickstart.py (needs OPENAI_API_KEY)"
	@echo "  make docker-repl    - Run docker_repl_example.py (needs Docker)"
	@echo "  make lm-repl        - Run lm_in_repl.py (needs PORTKEY_API_KEY)"
	@echo "  make modal-repl     - Run modal_repl_example.py (needs Modal)"
	@echo ""
	@echo "Development:"
	@echo "  make lint           - Run ruff linter"
	@echo "  make format         - Run ruff formatter"
	@echo "  make test           - Run tests"
	@echo "  make typecheck      - Run ty type checker"
	@echo "  make check          - Run lint + format + tests"
	@echo ""
	@echo "Extension:"
	@echo "  make ext-install    - Install extension npm dependencies"
	@echo "  make ext-build      - Compile TypeScript"
	@echo "  make ext-typecheck  - Type-check with tsc --noEmit"
	@echo "  make ext-lint       - Run ESLint"
	@echo "  make ext-test       - Build + run extension unit tests"
	@echo "  make ext-check      - All extension gates"
	@echo "  make ext-clean      - Remove out/ directory"

install:
	uv sync

install-dev:
	uv sync --group dev --group test --extra mcp

install-modal:
	uv pip install -e ".[modal]"

run-all: quickstart docker-repl lm-repl modal-repl

quickstart: install
	uv run python -m examples.quickstart

docker-repl: install
	uv run python -m examples.docker_repl_example

lm-repl: install
	uv run python -m examples.lm_in_repl

modal-repl: install-modal
	uv run python -m examples.modal_repl_example

lint: install-dev
	uv run ruff check .

format: install-dev
	uv run ruff format .

test: install-dev
	uv run pytest

typecheck: install-dev
	uv run ty check --exit-zero --output-format=concise

check: lint format test

# ── VS Code Extension ───────────────────────────────────────────────

EXT_DIR := vscode-extension

ext-install:
	cd $(EXT_DIR) && npm ci

ext-build: ext-install
	cd $(EXT_DIR) && npx tsc -p ./

ext-typecheck: ext-install
	cd $(EXT_DIR) && npx tsc --noEmit

ext-lint: ext-install
	cd $(EXT_DIR) && npx eslint src/ --max-warnings 0

ext-test: ext-build
	node $(EXT_DIR)/out/logger.test.js
	node $(EXT_DIR)/out/backendBridge.protocol.test.js
	node $(EXT_DIR)/out/platformLogic.test.js
	node $(EXT_DIR)/out/configModel.test.js
	node $(EXT_DIR)/out/toolsFormatting.test.js

ext-check: ext-typecheck ext-lint ext-test

ext-clean:
	rm -rf $(EXT_DIR)/out
