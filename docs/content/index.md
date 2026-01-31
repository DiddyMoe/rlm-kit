# RLM Documentation

Documentation for **Recursive Language Models (RLMs)** — a task-agnostic inference paradigm for language models to handle near-infinite length contexts via programmatic examination, decomposition, and recursive self-calls.

**Key resources:** [Paper (arXiv)](https://arxiv.org/abs/2512.24601) · [Blog post](https://alexzhang13.github.io/blog/2025/rlm/) · [RLM Minimal](https://github.com/alexzhang13/rlm-minimal)

---

## Documentation structure

### Getting started

| Doc | Description |
|-----|-------------|
| [Overview](getting-started/overview.md) | What RLMs are, architecture, and core concepts |
| [Installation](getting-started/installation.md) | Install with uv, optional extras, and verification |
| [Quick start](getting-started/quick-start.md) | Run your first RLM completion and MCP gateway in 3 steps |

### Guides

| Doc | Description |
|-----|-------------|
| [IDE setup (Cursor & VS Code)](guides/ide-setup.md) | Configure MCP gateway for local or remote use |
| [MCP gateway quick start](guides/mcp-gateway-quick-start.md) | 3-step MCP setup and tool usage |
| [Remote isolation](guides/remote-isolation.md) | Deploy gateway on a separate host for production |
| [Cursor thin workspace](guides/cursor-thin-workspace.md) | Use a workspace with no source code (remote-only access) |
| [Docker sandbox](guides/docker-sandbox.md) | Stronger sandbox isolation with Docker |

### Reference

| Doc | Description |
|-----|-------------|
| [Quick reference](reference/quick-reference.md) | Commands, config snippets, MCP tools, verification |
| [Agents & contributors](reference/agents.md) | Code style, LM clients, environments, AgentRLM, architecture |
| [API: RLM class](reference/api/rlm.md) | RLM constructor, methods, and types |

### Usage

| Doc | Description |
|-----|-------------|
| [Example scenarios](usage/example-scenarios.md) | Real-world MCP gateway usage (codebase structure, search, analysis) |

### Contributing

| Doc | Description |
|-----|-------------|
| [Contributing](contributing/contributing.md) | PR expectations, TODOs, and repo guidelines |

---

## Quick links

- **New users:** Start with [Quick start](getting-started/quick-start.md) or [Overview](getting-started/overview.md).
- **IDE + MCP:** [IDE setup](guides/ide-setup.md) and [MCP gateway quick start](guides/mcp-gateway-quick-start.md).
- **Production (remote):** [Remote isolation](guides/remote-isolation.md) and [Installation (gateway)](getting-started/installation.md).
- **Contributors:** [Agents & contributors](reference/agents.md) and [Contributing](contributing/contributing.md).
