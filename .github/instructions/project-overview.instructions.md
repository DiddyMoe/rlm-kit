# Project Overview

## What Is RLM?

RLM (Recursive Language Models) is a task-agnostic inference engine that lets language models handle large contexts via programmatic examination, decomposition, and recursive self-calls through a REPL. Language models write and execute code to inspect, chunk, and recursively analyze context — producing verified, grounded answers.

**Paper**: [Recursive Language Models](https://arxiv.org/abs/2512.24601)

This fork focuses on seamless IDE integration with VS Code Copilot Agent Chat and Cursor Agent Chat.

## Repository Layout

```
rlm/                          # Core Python package
├── core/                     # RLM loop, LM handler, types, comms, sandbox
│   ├── rlm.py               # Main completion loop (RLM class, RLMConfig)
│   ├── lm_handler.py         # Multi-threaded TCP server wrapping LM clients
│   ├── types.py              # All data types (dataclasses with manual serialization)
│   ├── comms_utils.py        # Socket protocol (LMRequest/LMResponse)
│   ├── constants.py          # Shared constants (MAX_SUB_CALL_PROMPT_CHARS)
│   ├── retry.py              # Exponential backoff retry mechanism
│   └── sandbox/              # AST validation, safe builtins, restricted exec
├── clients/                  # LM API integrations
│   ├── base_lm.py            # Abstract base class (BaseLM)
│   ├── openai.py, anthropic.py, gemini.py, etc.
│   └── __init__.py           # get_client() factory with lazy imports
├── environments/             # REPL execution environments
│   ├── base_env.py           # BaseEnv, NonIsolatedEnv, IsolatedEnv, SupportsPersistence
│   ├── local_repl.py         # Local sandboxed REPL
│   ├── docker_repl.py        # Docker container REPL
│   ├── modal_repl.py         # Modal cloud sandbox
│   ├── prime_repl.py         # Prime cloud sandbox
│   ├── daytona_repl.py       # Daytona cloud sandbox
│   ├── e2b_repl.py           # E2B code interpreter
│   ├── constants.py          # Default packages for isolated environments
│   ├── exec_script_templates.py  # Script templates for isolated sandboxes
│   └── __init__.py           # get_environment() factory
├── mcp_gateway/              # MCP server for IDE integration
│   ├── server.py             # MCP tool registration and dispatch
│   ├── session.py, validation.py, handles.py, provenance.py
│   ├── auth.py               # Authentication (API key, OAuth)
│   ├── constants.py          # Gateway-specific constants
│   └── tools/                # Tool implementations (fs, search, exec, complete, etc.)
├── logger/                   # Logging infrastructure
│   ├── rlm_logger.py         # JSONL trajectory logger
│   └── verbose.py            # Rich console printer (Tokyo Night theme)
├── utils/                    # Shared utilities
│   ├── parsing.py            # Code block extraction, FINAL answer parsing
│   ├── prompts.py            # System prompt building (RLM_SYSTEM_PROMPT)
│   ├── rlm_utils.py          # General utilities (filter_sensitive_keys)
│   ├── token_counter.py      # Heuristic token counting (~4 chars/token)
│   └── token_utils.py        # Accurate token counting (tiktoken), model context limits
└── debugging/                # Call history, graph tracking
    ├── call_history.py       # Flat LLM call tracking with filtered queries
    └── graph_tracker.py      # Recursive call graph tracking (optional NetworkX)

vscode-extension/             # VS Code extension (zero runtime npm deps)
├── src/
│   ├── extension.ts          # Entry point, activation, command registration
│   ├── rlmParticipant.ts     # @rlm chat participant (commands: analyze, summarize, search)
│   ├── orchestrator.ts       # Boundary between chat and Python backend
│   ├── backendBridge.ts      # Spawns Python sidecar, JSON-over-stdin/stdout
│   ├── configService.ts      # Singleton for rlm.* settings with typed change events
│   ├── configModel.ts        # RlmConfig interface, defaults, normalization
│   ├── apiKeyManager.ts      # API key storage via vscode.SecretStorage
│   ├── logger.ts             # JSONL logger with rolling, redaction, crash-safe
│   ├── platform.ts           # VS Code vs Cursor detection
│   ├── platformLogic.ts      # Pure detection logic (testable without VS Code host)
│   ├── tools.ts              # Language Model Tools (rlm_analyze, rlm_execute)
│   ├── toolsFormatting.ts    # Tool output formatting and truncation
│   ├── mcpServerProvider.ts  # MCP server definition provider for VS Code
│   ├── cursorMcpRegistration.ts  # MCP server registration for Cursor
│   ├── types.ts              # Protocol types (OutboundMessage, InboundMessage)
│   └── *.test.ts             # Unit tests (5 files: logger, configModel, platformLogic, backendBridge.protocol, toolsFormatting)
└── python/
    └── rlm_backend.py        # Python sidecar (JSON-over-stdio protocol)

scripts/                      # Entry point scripts
├── rlm_mcp_gateway.py        # MCP gateway launcher
└── _repo_root.py             # Repository root resolver

tests/                        # pytest test suite
├── mock_lm.py                # MockLM(BaseLM) for testing
├── test_*.py                 # Class-based test grouping, plain assert
├── clients/                  # Client-specific tests
└── repl/                     # REPL-specific tests

docs/                         # Documentation
├── INDEX.md                  # Documentation index
├── adr/                      # Architecture Decision Records
├── index/                    # Project index, setup matrix, coverage
├── integration/              # IDE playbooks, adapter mapping, matrix
├── orchestrator/             # Plan, backlog, findings, state, run log
├── quality/                  # Bug backlog, failure modes, security surfaces, observability
└── research/                 # Landscape, bibliography, benchmarks, recommendations
```

## Architecture Flow

```
RLM.completion(prompt)
  ├── get_client() → BaseLM              # Factory with lazy imports
  ├── LMHandler(client)                   # TCP socket server wrapping BaseLM
  ├── get_environment() → BaseEnv         # Factory with lazy imports
  ├── Iteration loop (max 30):
  │     ├── lm_handler.completion()        # LLM call
  │     ├── find_code_blocks(response)     # Extract ```repl blocks
  │     ├── env.execute_code(code)         # Run in REPL
  │     │     └── llm_query() → socket → LMHandler   # Sub-LM calls
  │     └── find_final_answer()            # Check FINAL()/FINAL_VAR()
  └── Return RLMChatCompletion
```

## IDE Integration

| IDE     | Entry Point        | LLM Source               | Config                      |
|---------|--------------------|--------------------------|------------------------------|
| VS Code | Chat `@rlm`        | Copilot (vscode.lm) or API key | settings.json (`rlm.*`)   |
| Cursor  | MCP tools           | Cursor LLM + optional API key  | `.cursor/mcp.json`        |

VS Code uses the Chat Participant API. Cursor uses MCP tools only (no Chat Participant registered).

## Public API

The entire public API is: `from rlm import RLM`. Clients use `get_client()`, environments use `get_environment()` — both are factory functions with lazy imports.
