# ADR-001: Extension Architecture — RLM Orchestrator Integration

## Status
Accepted

## Context
The rlm-kit repository contains:
1. A Python library (`rlm/`) implementing Recursive Language Model inference
2. A VS Code extension (`vscode-extension/`) that bridges the Chat API to the Python backend
3. An MCP gateway (`rlm/mcp_gateway/`) for Cursor IDE integration
4. Multiple cloud sandbox environments (Modal, Prime, Daytona, Docker)

The goal is a production-grade VS Code/Cursor extension with:
- RLM orchestration wired into the chat agent workflow
- Centralized settings, deep tracing, security hardening
- Strict typing, minimal complexity, CI-ready quality gates

## Decision

### What stays
- **Python library (`rlm/`)**: The RLM engine stays as the computation backend. The extension spawns it as a child process via `rlm_backend.py`.
- **VS Code extension (`vscode-extension/`)**: The primary deliverable. Gets a new TypeScript orchestrator layer, improved logging, settings service, and security hardening.
- **MCP gateway**: Stays for Cursor integration path.
- **Tests**: Kept and extended.

### What gets added (TypeScript, in the extension)
1. **`src/orchestrator.ts`** — RLM Orchestrator: thin TypeScript layer that sits between the chat participant and BackendBridge. Responsibilities:
   - Bounded recursion depth enforcement (configurable)
   - Work budget tracking (time/steps)
   - Deterministic termination conditions
   - Trace span emission for every orchestration step
   - Context management (externalized, not stuffed into prompts)

2. **`src/configService.ts`** — Centralized settings reader:
   - Single source of truth for all `rlm.*` settings
   - Runtime toggle for tracing
   - Emits change events

3. **Enhanced `src/logger.ts`** — Improved tracing:
   - Rolling JSONL at `logs/trace.jsonl` (extension storage)
   - 10MB rotation with newest-entries-preserved truncation
   - Expanded redaction patterns (Gemini keys, Azure keys, generic tokens, arrays)
   - Crash-safe flush (sync on fatal, `process.on('uncaughtException')`)
   - Toggle via settings

### What gets pruned
- Empty log files in `logs/`
- Dead CI workflow (`docs.yml`)
- `ollama.py` client (unregistered)
- `MANIFEST.IN` (redundant with pyproject.toml)
- `__pycache__` directories from version control

### Architecture flow
```
User → @rlm Chat → RLMChatParticipant → Orchestrator → BackendBridge → Python
                                            ↓
                                     ConfigService (settings)
                                     Logger (trace spans)
```

The orchestrator does NOT duplicate the Python RLM loop. It wraps the bridge call with:
- Pre-flight validation (budget, depth)
- Trace span start/end
- Error boundary with structured logging
- Timeout enforcement

## Consequences
- Extension bundle stays lightweight (zero runtime npm deps)
- Python backend continues to own the full RLM iteration loop
- TypeScript orchestrator provides observability, safety bounds, and configuration
- Both VS Code and Cursor paths are preserved
