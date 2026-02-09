# Project index

High-level map of the RLM fork. See [docs/index/project_index.json](index/project_index.json), [docs/index/trajectory_logging_coverage.md](index/trajectory_logging_coverage.md), [docs/integration/ide_touchpoints.md](integration/ide_touchpoints.md), [docs/integration/playbooks.md](integration/playbooks.md).

## Repository layout

### rlm/ — Core Python package

- **core/** — RLM loop, LM handler, socket protocol, types, sandbox (rlm.py, lm_handler.py, comms_utils.py, types.py, constants.py, retry.py, sandbox/).
- **clients/** — LM API integrations (OpenAI, Anthropic, Gemini, Portkey, LiteLLM, Azure, VsCodeLM, Ollama, etc.).
- **environments/** — base_env, local_repl, docker_repl, modal_repl, prime_repl, daytona_repl.
- **logger/** — RLMLogger (JSONL), VerbosePrinter.
- **mcp_gateway/** — server, session, validation, provenance, handles, tools (session, fs, span, chunk, search, exec, complete, provenance).
- **utils/** — parsing, prompts, rlm_utils, token_counter.
- **debugging/** — call_history, graph_tracker.

### vscode-extension/

- **src/** — extension, rlmParticipant, orchestrator, backendBridge, configService, apiKeyManager, logger, platform, types.
- **python/** — rlm_backend.py (JSON-over-stdio).

### scripts/

- rlm_mcp_gateway.py, _repo_root.py.

### Tests, config, docs

- tests/ (test_parsing, test_types, test_local_repl*, test_multi_turn_integration, test_imports; repl/, clients/).
- .cursor/mcp.json, .vscode/, pyproject.toml, .python-version, uv.lock, Makefile.
- docs/adr/, docs/index/, docs/integration/, docs/orchestrator/, docs/research/, docs/quality/.
