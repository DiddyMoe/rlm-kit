# RLM — VS Code Extension

> **Recursive Language Models** are a task-agnostic inference paradigm
> that enables an LM to programmatically examine, decompose, and
> recursively call itself over arbitrary-length contexts.
>
> [Paper](https://arxiv.org/abs/2512.24601) · [Blog](https://alexzhang13.github.io/blog/2025/rlm/) · [Upstream](https://github.com/alexzhang13/rlm)

## What This Repo Contains

| Component | Location | Description |
|-----------|----------|-------------|
| **VS Code Extension** | `vscode-extension/` | `@rlm` chat participant with dual-mode LLM access |
| **RLM Engine** | `rlm/` | Python inference engine — REPL loop, LM clients, local environment |

## Quick Start

### Prerequisites

- **Python 3.11+** (for the RLM engine)
- **Node.js 20+** (for building the extension)
- **VS Code 1.99+** or **Cursor**
- A GitHub Copilot subscription *or* an LLM API key

### Setup

```bash
git clone <repo-url> && cd rlm-kit

# Install Python RLM engine
pip install -e .

# Install extension dependencies & build
cd vscode-extension && npm ci && npm run compile
```

### Verify

```bash
make check   # typecheck + lint + tests (all must pass)
```

### Using with VS Code

The extension registers an `@rlm` chat participant that routes prompts
through the RLM recursive REPL loop.

**Built-in mode (Copilot subscription, zero API keys):**

1. Press **F5** to launch the Extension Development Host
2. Open Chat → type `@rlm <your question>`
3. Uses your Copilot subscription via the `vscode.lm` API

**API key mode:**

1. Set `rlm.llmProvider` to `"api_key"` in settings
2. Set `rlm.backend` (e.g. `"openai"`, `"anthropic"`)
3. Run command: **RLM: Set API Key**
4. Chat as normal — the RLM engine calls the API directly

### Using with Cursor

Cursor doesn't expose `vscode.chat` / `vscode.lm` APIs.
Set `rlm.llmProvider` to `"api_key"`, configure a backend, store your
key, then interact via any Cursor-supported integration path.

## Architecture

```
User → @rlm Chat → RLMChatParticipant → Orchestrator → BackendBridge → rlm_backend.py
                                            ↕                               ↕
                                     ConfigService                    RLM.completion()
                                     Logger (JSONL)                   + LocalREPL
```

See [docs/adr/001-extension-architecture.md](docs/adr/001-extension-architecture.md)
for full design rationale.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `rlm.llmProvider` | `"builtin"` | `"builtin"` (Copilot) or `"api_key"` |
| `rlm.backend` | `"openai"` | LLM backend for api_key mode |
| `rlm.model` | `"gpt-4o"` | Model name |
| `rlm.baseUrl` | `""` | Custom API base URL |
| `rlm.subBackend` | `""` | Separate backend for sub-LLM calls |
| `rlm.subModel` | `""` | Model for sub-LLM calls |
| `rlm.maxIterations` | `30` | Max REPL iterations (hard cap: 50) |
| `rlm.maxOutputChars` | `20000` | Max output characters |
| `rlm.pythonPath` | `"python3"` | Python interpreter path |
| `rlm.tracingEnabled` | `true` | Enable/disable trace logging |
| `rlm.logLevel` | `"debug"` | Log level: debug / info / warn / error / off |
| `rlm.logMaxSizeMB` | `10` | Max log file size before rotation |

## Commands

| Command | Description |
|---------|-------------|
| **RLM: Open RLM Chat** | Focus the chat panel (`Ctrl+Shift+R`) |
| **RLM: Set API Key** | Securely store an API key |
| **RLM: Clear All API Keys** | Remove all stored keys |
| **RLM: Show Current Provider** | Display active configuration |
| **RLM: New RLM Chat Session** | Reset REPL state |
| **RLM: Open Debug Log** | Open `logs/trace.jsonl` |

## Tracing & Logging

Structured JSONL traces are written to `logs/trace.jsonl` in the workspace
root (falls back to VS Code global storage if no workspace is open).

- **Rolling:** file is truncated when it exceeds the configured size
  threshold, keeping the newest 50% of entries.
- **Redaction:** API keys, tokens, secrets, and passwords are
  automatically redacted before writing.
- **Crash-safe:** WARN and ERROR entries are flushed synchronously;
  `uncaughtException` and `unhandledRejection` handlers flush and log
  before exit.
- **Toggle:** set `rlm.tracingEnabled` to `false` to suppress DEBUG/INFO
  entries (WARN+ always logged).

## Supported LLM Backends

OpenAI · Anthropic · Azure OpenAI · Google Gemini · OpenRouter ·
Portkey · Vercel AI Gateway · vLLM · LiteLLM

## Security & Privacy

- API keys are stored via `vscode.SecretStorage` (OS keychain) — never
  written to `settings.json` or disk files.
- The Python child process receives a filtered environment: cloud
  credentials, VS Code internals, and `*_TOKEN`/`*_SECRET`/`*_PASSWORD`
  variables are blocked.
- All log entries pass through redaction before being persisted.
- The extension requests no network permissions beyond what the LM
  clients require.

## Development

```bash
# Install everything
make install

# Run quality gates
make typecheck    # strict tsc --noEmit
make lint         # eslint --max-warnings 0
make test         # build + unit tests (15 logger tests)
make check        # all three
make clean        # remove build artifacts
```

### Extension development

Press **F5** in VS Code to launch the Extension Development Host.
Use `npm run watch` (or the _npm: watch_ task) for incremental builds.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `@rlm` not appearing in chat | Verify VS Code ≥1.99; check Copilot is active |
| Python backend fails to start | Verify `rlm.pythonPath` resolves; run `python -c "import rlm"` |
| Timeout errors | Increase `rlm.maxIterations`; check API key validity |
| Cursor: no chat participant | Expected — use api_key mode + backend directly |

## Citation

```bibtex
@misc{zhang2025recursivelanguagemodels,
      title={Recursive Language Models},
      author={Alex L. Zhang and Tim Kraska and Omar Khattab},
      year={2025},
      eprint={2512.24601},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2512.24601},
}
```
