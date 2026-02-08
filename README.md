# Recursive Language Models (RLM) — VS Code & Cursor Extension

> **RLMs** are a task-agnostic inference paradigm for language models to handle near-infinite length contexts by enabling the LM to *programmatically* examine, decompose, and recursively call itself over its input.
>
> [Paper](https://arxiv.org/abs/2512.24601) • [Blogpost](https://alexzhang13.github.io/blog/2025/rlm/) • [Upstream](https://github.com/alexzhang13/rlm)

## What This Repo Contains

| Component | Location | Description |
|-----------|----------|-------------|
| **RLM Core** | `rlm/` | Python inference engine — REPL loop, LM clients, environments |
| **VS Code Extension** | `vscode-extension/` | Chat Participant (`@rlm`) with dual-mode LLM access |
| **MCP Gateway** | `rlm/mcp_gateway/` | MCP server for Cursor integration |

## Quick Start

### Prerequisites

- Python 3.11+, [uv](https://astral.sh/uv)
- VS Code 1.99+ (for the extension) or Cursor (for MCP)
- An LLM API key OR a GitHub Copilot subscription

### Setup

```bash
# Clone and install
git clone <repo-url> && cd rlm-kit
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .

# Verify
make check
```

### Using with VS Code

The extension provides an `@rlm` chat participant that routes prompts through the RLM's recursive REPL loop.

**Mode A: Built-in (Copilot subscription, zero API keys)**
1. Install the extension (F5 to launch Extension Host)
2. Open Chat → type `@rlm <your question>`
3. Uses your Copilot subscription via `vscode.lm` API

**Mode B: API Key**
1. Set `rlm.llmProvider` to `"api_key"` in settings
2. Set `rlm.backend` (e.g. `"openai"`, `"anthropic"`)
3. Run command: `RLM: Set API Key`
4. Chat as normal — uses your own API key directly

### Using with Cursor

Cursor integrates via MCP — no Chat Participant (Cursor doesn't support `vscode.chat`/`vscode.lm` APIs).

**Mode 1: Cursor-as-outer-loop (primary, zero keys)**
1. `.cursor/mcp.json` is preconfigured
2. Cursor's agent calls RLM MCP tools directly
3. Uses Cursor's own LLM subscription

**Mode 2: API Key via `rlm.complete`**
1. Set your API key as an env var (e.g. `OPENAI_API_KEY`)
2. Ask Cursor to use the `rlm.complete` MCP tool
3. RLM runs the full recursive loop with your API key

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  VS Code                                                         │
│  ┌─────────────────┐    JSON/stdio    ┌──────────────────────┐  │
│  │ Chat Participant │◄───────────────►│  rlm_backend.py      │  │
│  │ (TypeScript)     │                 │  (Python RLM loop)   │  │
│  └─────────────────┘                 └──────────────────────┘  │
│         │                                      │                │
│    vscode.lm API                          rlm.completion()      │
│    (builtin mode)                         + LocalREPL           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Cursor                                                          │
│  ┌─────────────────┐      MCP        ┌──────────────────────┐  │
│  │ Cursor Agent     │◄──────────────►│  MCP Gateway          │  │
│  │ (built-in LLM)   │               │  (rlm_mcp_gateway.py) │  │
│  └─────────────────┘               └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Extension Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `rlm.llmProvider` | `"builtin"` | `"builtin"` (Copilot) or `"api_key"` (own keys) |
| `rlm.backend` | `"openai"` | LLM backend for api_key mode |
| `rlm.model` | `"gpt-4o"` | Model name |
| `rlm.baseUrl` | `""` | Custom API base URL |
| `rlm.subBackend` | `""` | Separate backend for sub-LLM calls |
| `rlm.subModel` | `""` | Model for sub-LLM calls |
| `rlm.maxIterations` | `30` | Max REPL iterations |
| `rlm.pythonPath` | `"python3"` | Python interpreter path |

### Extension Commands

| Command | Description |
|---------|-------------|
| `RLM: Open RLM Chat` | Focus the chat panel |
| `RLM: Set API Key` | Securely store an API key |
| `RLM: Clear All API Keys` | Remove stored keys |
| `RLM: Show Current Provider` | Display active configuration |
| `RLM: New RLM Chat Session` | Reset REPL state |
| `RLM: Open Debug Log` | Open JSONL debug log |

## Supported LLM Backends

OpenAI, Anthropic, Azure OpenAI, Google Gemini, OpenRouter, Portkey, Vercel AI Gateway, vLLM, LiteLLM

## REPL Environments

| Environment | Type | Description |
|-------------|------|-------------|
| `local` | Non-isolated | Same process, `exec`-based (default) |
| `docker` | Non-isolated | Docker container |
| `modal` | Isolated | Modal cloud sandbox |
| `prime` | Isolated | Prime Intellect sandbox |
| `daytona` | Isolated | Daytona cloud sandbox |

## Development

```bash
# Install dev dependencies
make install-dev

# Run checks
make check           # lint + format + tests

# Build extension
cd vscode-extension && npm install && npm run compile
```

See [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

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
