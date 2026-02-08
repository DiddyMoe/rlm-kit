.PHONY: help install build typecheck lint test check clean

EXT_DIR := vscode-extension

help:
	@echo "RLM VS Code Extension"
	@echo ""
	@echo "  make install    - Install npm + Python dependencies"
	@echo "  make build      - Compile TypeScript"
	@echo "  make typecheck  - Strict TypeScript type-check (no emit)"
	@echo "  make lint       - ESLint (zero warnings)"
	@echo "  make test       - Run extension unit tests"
	@echo "  make check      - typecheck + lint + test"
	@echo "  make clean      - Remove build artifacts"

install:
	cd $(EXT_DIR) && npm ci
	pip install -e . --quiet 2>/dev/null || true

build:
	cd $(EXT_DIR) && npx tsc -p ./

typecheck:
	cd $(EXT_DIR) && npx tsc --noEmit

lint:
	cd $(EXT_DIR) && npx eslint src/ --max-warnings 0

test: build
	cd $(EXT_DIR) && node out/logger.test.js

check: typecheck lint test

clean:
	rm -rf $(EXT_DIR)/out
