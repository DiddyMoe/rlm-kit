# Research Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Consumed by: research-agent.prompt.md -->
<!-- Last updated: 2026-03-08 12:00:00 -->

## Priority 1 — Critical for IDE Integration

_(No items — all P1 items have been implemented)_

## Priority 2 — High-Impact Improvements

_(No items — all P2 items have been implemented)_

## Priority 3 — Medium-Impact Enhancements

_(No items — all P3 items have been implemented)_

## Priority 4 — Future Exploration

### RF-062: Explore MCP Apps for interactive RLM UI
- **Source**: VS Code MCP Apps blog (Jan 2026) — interactive UI in tool responses
- **What**: Investigate using `@modelcontextprotocol/ext-apps` SDK to render interactive RLM progress visualizations (iteration timeline, code execution results, provenance graphs) in chat responses.
- **Why**: Could replace text-based progress with rich interactive components. SDK provides `App.connect()`, `callServerTool()`, `sendMessage()`, `updateModelContext()`, `openLink()`.
- **Limitations**: VS Code only (inline display mode only, no pip/fullscreen). Send message fills chat input but doesn't auto-send. No camera/mic/geo.
- **Files affected**: `rlm/mcp_gateway/tools/complete_tools.py`, potentially new MCP app definitions
- **Test strategy**: Prototype MCP app response and verify rendering in VS Code Insiders.
- **Depends on**: None

### RF-095: Study open-sourced Copilot Chat for integration improvements
- **Source**: VS Code v1.102 — Copilot Chat open-sourced at `microsoft/vscode-copilot-chat` (MIT)
- **What**: Analyze the open-sourced Copilot Chat implementation to understand agent mode internals: tool calling patterns, MCP integration, prompt construction, streaming, multi-turn state management. Identify integration improvements for our chat participant.
- **Why**: Direct access to how VS Code's agent mode works internally. Could reveal better patterns for tool registration, result formatting, or multi-turn handling.
- **Files affected**: Potentially `vscode-extension/src/rlmParticipant.ts`, `vscode-extension/src/orchestrator.ts`
- **Test strategy**: Code review and prototype improvements. Run ext-check after any changes.
- **Depends on**: None

## Priority 5 — Low Priority / Nice-to-Have

_(No items — all P5 research items have been implemented)_
