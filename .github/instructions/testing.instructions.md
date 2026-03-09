# Testing Conventions

## Running Tests

```bash
make test           # Run Python tests (uv run pytest)
make ext-test       # Build + run extension unit tests
make check          # lint + format + test (Python)
make ext-check      # typecheck + lint + test (Extension)
```

## Python Testing

### Framework and Discovery

- **Framework**: pytest with discovery under `tests/`
- **Config**: `[tool.pytest.ini_options]` in `pyproject.toml`, `testpaths = ["tests"]`
- **Async**: pytest-asyncio for async tests
- **Coverage**: pytest-cov available but not enforced

### Test Structure

- **Class-based grouping**: Group related tests in classes (e.g., `class TestFindCodeBlocks:`)
- **Plain `assert`**: No `assertEqual`, `assertTrue` — just `assert expression`
- **No pytest fixtures**: Tests create objects directly. No `@pytest.fixture` usage.
- **Direct object creation**: Construct test subjects inline, not via shared setup

```python
class TestFindCodeBlocks:
    def test_single_repl_block(self):
        text = "```repl\nprint('hello')\n```"
        blocks = find_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0] == "print('hello')"

    def test_no_blocks(self):
        text = "No code here"
        blocks = find_code_blocks(text)
        assert blocks == []
```

### Mock Patterns

- **Mock LM client**: `tests/mock_lm.py` provides `MockLM(BaseLM)` — all abstract methods implemented with deterministic responses
- **`unittest.mock.patch`**: Use `patch.object` for integration tests
- **No real network calls**: Mock all external API calls
- **`pytest.importorskip`**: For tests requiring optional deps (litellm, portkey_ai, etc.)

```python
from tests.mock_lm import MockLM
from unittest.mock import patch

class TestRLMCompletion:
    def test_basic_completion(self):
        mock = MockLM()
        # Direct object creation, no fixtures
        with patch.object(mock, "completion", return_value="FINAL(42)"):
            result = mock.completion("test prompt")
            assert "42" in result
```

### Test Files

| Test File | What It Tests |
|-----------|---------------|
| `test_parsing.py` | Code block extraction, FINAL answer parsing |
| `test_types.py` | Dataclass serialization round-trips |
| `test_comms_utils.py` | Socket protocol, LMRequest/LMResponse |
| `test_local_repl.py` | Local REPL execution |
| `test_local_repl_persistent.py` | Persistent REPL mode |
| `test_multi_turn_integration.py` | End-to-end multi-turn with mock LM |
| `test_sandbox.py` | AST validator, safe builtins |
| `test_path_validator.py` | Path traversal rejection |
| `test_mcp_gateway_*.py` | MCP gateway tools, session, resources, prompts |
| `test_mcp_cancellation.py` | Session cancellation flag, cancel by request ID |
| `test_imports.py` | Import smoke tests |
| `test_trajectory_schema.py` | JSONL trajectory shape validation |
| `test_rlm_backend_protocol.py` | Backend bridge protocol |
| `test_token_utils.py` | Token counting/budget utilities |
| `test_compaction.py` | Compaction init, compact_history, threshold trigger |
| `test_token_budgets.py` | max_root_tokens / max_sub_tokens enforcement |
| `test_custom_tools.py` | Custom tool injection, tool survival, prompt mentions |
| `test_semaphore_batch.py` | _MAX_CONCURRENT_BATCH=16 semaphore in batched LLM requests |
| `test_recursive_subcalls.py` | Recursive subcall depth, callbacks, budget/timeout inheritance |
| `test_client_timeout.py` | BaseLM.timeout parameter passthrough |
| `test_budget_and_limits.py` | Cost budget, timeout, error limit enforcement |
| `test_call_history.py` | CallHistory add/filter/export |
| `test_graph_tracker.py` | GraphTracker nodes/edges/export |
| `test_retry.py` | retry_with_backoff mechanism |
| `test_prompts.py` | System prompt building |
| `test_rlm_config.py` | RLMConfig field validation |
| `test_env_configs.py` | Environment configuration |
| `test_file_cache.py` | MCP FileMetadataCache |
| `test_search_tools.py` | MCP search tools |
| `test_span_tools.py` | MCP span tools |
| `test_async_completion.py` | Async completion path |
| `test_bare_except.py` | No bare except: in codebase |
| `test_lm_handler_model_preferences.py` | LMHandler model routing |
| `test_rlm_utils.py` | General utilities (filter_sensitive_keys) |
| `test_verbose_printer.py` | VerbosePrinter output |
| `test_exec_script_templates.py` | Exec script rendering for isolated envs |
| `clients/` | Provider-specific tests (OpenAI, Anthropic, Gemini, Ollama, Portkey, VS Code LM) |
| `repl/` | REPL-specific tests |

### What to Test

When changing functionality, always update tests:
- **Serialization changes** → add/update round-trip test in `test_types.py`
- **Protocol changes** → update both Python and TS sides, add contract test
- **New client** → add test with MockLM pattern
- **New environment** → add test with mock external services
- **Parsing changes** → add edge case tests in `test_parsing.py`

## TypeScript Testing

### Test Files

Extension tests are plain Node.js scripts (no test framework dependency):

```bash
node vscode-extension/out/logger.test.js
node vscode-extension/out/backendBridge.protocol.test.js
node vscode-extension/out/platformLogic.test.js
node vscode-extension/out/configModel.test.js
node vscode-extension/out/toolsFormatting.test.js
```

`make ext-test` runs all 5 test files. Note: CI (`extension.yml`) currently only runs `logger.test.js`.

### Pattern

- Tests are `.test.ts` files compiled to `.test.js`
- No vscode API mocking (tests cover pure logic only)
- Run via raw `node` — no test runner dependency
- ESLint relaxes `no-unsafe-*` rules for test files

## CI/CD

### GitHub Actions Workflows

| Workflow | Trigger | What It Does |
|----------|---------|--------------|
| `test.yml` | Push/PR | Matrix Python 3.11/3.12, pytest with coverage, MCP gateway smoke. Excludes `tests/clients/` and `tests/repl/test_modal_repl.py` (other repl tests included) |
| `style.yml` | Push/PR | ruff check, ruff format --check, ty check. Pins `ruff==0.14.10`, `ty==0.0.1a21` |
| `extension.yml` | Push/PR | Node 20, tsc --noEmit, eslint, build, `logger.test.js` only (not all 5 test files), npm audit |
| `docs.yml` | Push to main | Builds and deploys docs site to GitHub Pages |
