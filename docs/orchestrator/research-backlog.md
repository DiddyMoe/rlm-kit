# Research Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Consumed by: research-agent.prompt.md -->
<!-- Last updated: 2026-02-19 18:00:00 -->

## Priority 1 — Critical for IDE Integration

## Priority 2 — High-Impact Improvements

### RF-070: Port depth>1 recursive subcalls from upstream PR #84 ⚠️ BLOCKED: large upstream delta requires dedicated migration pass
- **Source**: https://github.com/alexzhang13/rlm/pull/84 (merged Feb 18, 2026, 3168 additions)
- **Category**: Core
- **Impact**: High — enables true recursive decomposition beyond depth=1. Current fork caps at `max_depth=1`. Upstream PR adds `_subcall()`, `BudgetExceededError`, `max_budget`, `max_timeout`, `max_errors`, event callbacks.
- **Effort**: Large
- **Description**: Port the depth>1 subcall system from upstream PR #84. Key components: (1) `_subcall()` method on `RLM` that spawns child instances, (2) `BudgetExceededError` and `max_budget` with OpenRouter cost extraction, (3) execution limits `max_timeout`/`max_tokens`/`max_errors`, (4) event callbacks `on_subcall_start/complete` and `on_iteration_start/complete`, (5) `_subcall` returns `RLMChatCompletion`. Must integrate with existing compaction (RF-049) and custom tools (RF-052) which were not in upstream when #84 was authored.
- **Files affected**: `rlm/core/rlm.py`, `rlm/core/types.py`, `rlm/environments/local_repl.py`, `rlm/clients/openai.py`, `rlm/logger/verbose.py`, new test files
- **Test strategy**: Port 13 unit tests from upstream. Verify `make check` passes. Verify subcall spawns child RLM at depth+1 with mock LM.
- **Depends on**: None (RF-049/050/052/053 already integrated)

- **⚠️ BLOCKED reason**: Upstream PR #84 introduces a broad 3k+ LOC rework (`_subcall`, budget/timeout/error limits, callbacks) that overlaps existing fork integrations (RF-021/049/052/053). Requires a dedicated migration strategy to avoid regressions; deferred from this incremental pass.

### RF-065: Add MCP elicitation support to gateway ⚠️ BLOCKED: requires MCP SDK/server-initiated elicitation support decision
- **Source**: MCP spec 2025-06-18 — https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
- **Category**: Protocol
- **Impact**: Medium — allows the MCP server to request user input during tool execution. Use cases: prompt for API key when `rlm.complete` is called without one; confirm expensive operations; select environment.
- **Effort**: Medium
- **Description**: Implement elicitation in the MCP gateway. When `rlm.complete` detects missing API key, use `sampling/createMessage` or elicitation to request it from the user. Requires MCP SDK support for server-initiated elicitation requests. Cursor and VS Code both support elicitation.
- **Files affected**: `rlm/mcp_gateway/server.py`, `rlm/mcp_gateway/tools/complete_tools.py`
- **Test strategy**: `make test`. Manual: call `rlm.complete` without API key, verify elicitation prompt appears.
- **Depends on**: None

- **⚠️ BLOCKED reason**: Current gateway flow would require introducing and validating server-initiated elicitation wiring in both stdio and HTTP paths; this needs a dedicated design decision against the MCP SDK version in use.

## Priority 3 — Medium-Impact Enhancements

### RF-069: Use MCP elicitation for API key prompting in Cursor ⚠️ BLOCKED: depends on blocked RF-065
- **Source**: Cursor MCP docs — https://cursor.com/docs/context/mcp (protocol support: Elicitation Supported)
- **Category**: IDE Integration
- **Impact**: Medium — when `rlm.complete` is called without API key in Cursor, instead of failing, use elicitation to prompt the user.
- **Effort**: Medium
- **Description**: Implement elicitation flow in `rlm.complete` tool handler. When API key is missing, send an elicitation request to the client. Both VS Code and Cursor support this per their docs.
- **Files affected**: `rlm/mcp_gateway/tools/complete_tools.py`, `rlm/mcp_gateway/server.py`
- **Test strategy**: `make test`. Manual: call `rlm.complete` without key, verify elicitation prompt.
- **Depends on**: RF-065

- **⚠️ BLOCKED reason**: RF-065 is blocked pending SDK/design decisions for server-initiated elicitation flow.

## Priority 4 — Future Exploration

### RF-062: Explore MCP Apps for interactive RLM UI
- **Source**: VS Code MCP Apps blog (Jan 2026) — interactive UI in tool responses
- **What**: Investigate using `@modelcontextprotocol/ext-apps` SDK to render interactive RLM progress visualizations (iteration timeline, code execution results, provenance graphs) in chat responses.
- **Why**: Could replace text-based progress with rich interactive components.
- **Files affected**: `rlm/mcp_gateway/tools/complete_tools.py`, potentially new MCP app definitions
- **Test strategy**: Prototype MCP app response and verify rendering in VS Code Insiders.
- **Depends on**: None

### RF-075: Add MCP cancellation support for long-running rlm.complete
- **Source**: MCP spec 2025-06-18 — cancellation notifications in base protocol
- **Category**: Protocol
- **Impact**: Medium — allows IDE to cancel a running `rlm.complete` call. Currently the gateway has no cancellation for tool calls.
- **Effort**: Medium
- **Description**: Handle `notifications/cancelled` in the MCP gateway for in-flight `rlm.complete` operations. Propagate cancellation to the RLM instance (which already supports soft cancellation internally via RF-012).
- **Files affected**: `rlm/mcp_gateway/server.py`, `rlm/mcp_gateway/tools/complete_tools.py`
- **Test strategy**: `make test`. Add test that sends cancellation during `rlm.complete`.
- **Depends on**: None

## Priority 5 — New Items (this session)

### RF-076: Add MCP Icons to gateway server and tool definitions
- **Source**: VS Code MCP Developer Guide — https://code.visualstudio.com/api/extension-guides/ai/mcp (Icons section)
- **Category**: DX
- **Impact**: Low — branding improvement. RLM icon appears in MCP server list and tool picker.
- **Effort**: Small
- **Description**: Add `icons` property to the MCP server definition with an `src` URI pointing to the RLM logo. Can use `file:///` URI for stdio or a data URI. Also add icon to individual tool definitions if the SDK supports it.
- **Files affected**: `rlm/mcp_gateway/server.py`, `vscode-extension/src/mcpServerProvider.ts` (if RF-063 implemented)
- **Test strategy**: Manual: verify icon appears in VS Code MCP server list.
- **Depends on**: None (optionally RF-063 for the extension-registered variant)

### RF-077: Port Groq/Cerebras client implementations from upstream PR #54
- **Source**: https://github.com/alexzhang13/rlm/pull/54 (open, 149 additions)
- **Category**: Core
- **Impact**: Low — enables high-throughput inference via Groq/Cerebras hardware. These providers are already accessible via `litellm` client, so this is a convenience/discoverability improvement.
- **Effort**: Small
- **Description**: Port `GroqClient` and `CerebrasClient` from upstream PR #54. Register in `rlm/clients/__init__.py` factory. Add to extension's backend list.
- **Files affected**: new `rlm/clients/groq.py`, new `rlm/clients/cerebras.py`, `rlm/clients/__init__.py`, `vscode-extension/python/rlm_backend.py`
- **Test strategy**: `make check`. Add `pytest.importorskip` tests for each client.
- **Depends on**: None

### RF-078: Port upstream prompt templates (reasoning + math examples)
- **Source**: Upstream commits `97bbe97` and `725b734` (Feb 18, 2026)
- **Category**: Core
- **Impact**: Medium — improved default prompts can improve RLM quality for common use cases. Upstream added reasoning-example and math-example system prompt variants.
- **Effort**: Small
- **Description**: Review upstream prompt templates from commits `97bbe97` and `725b734`. Port useful patterns into `rlm/utils/prompts.py`. May add configurable prompt template selection.
- **Files affected**: `rlm/utils/prompts.py`
- **Test strategy**: `make check`. Verify prompts are syntactically valid and contain expected placeholders.
- **Depends on**: None

### RF-079: Document envFile support in Cursor MCP config
- **Source**: Cursor MCP docs — https://cursor.com/docs/context/mcp (stdio-server-configuration section)
- **Category**: DX
- **Impact**: Low — simplifies API key management for Cursor users. Instead of hardcoding keys in mcp.json, users can reference a `.env` file.
- **Effort**: Small
- **Description**: Add `envFile` field to `.cursor/mcp.json` example in playbooks and README. Example: `"envFile": "${workspaceFolder}/.env"`. Document that Cursor automatically loads env vars from the referenced file.
- **Files affected**: `docs/integration/playbooks.md`, `.cursor/mcp.json`
- **Test strategy**: Manual: verify Cursor loads env vars from `.env` file when configured.
- **Depends on**: None

### RF-080: Multi-model sub-call routing (from DSPy integration pattern)
- **Source**: stanfordnlp/dspy#9289 — `sub_lms` parameter for named LM routing inside REPL
- **Category**: Core
- **Impact**: Medium — enables `llm_query(prompt, model="strong")` to route to different LM clients within the same REPL session. DSPy implements this via `sub_lms={"strong": lm_pro, "fast": lm_mini}` dict.
- **Effort**: Medium
- **Description**: Add `sub_lms` parameter to `RLM.__init__()` accepting a dict of `{name: BaseLM}`. In the REPL environment, `llm_query(prompt, model=name)` routes to the specified sub-LM client via the LMHandler. Requires LMHandler to support model-name→client routing. Fallback to primary client when model name not found.
- **Files affected**: `rlm/core/rlm.py`, `rlm/core/lm_handler.py`, `rlm/environments/local_repl.py`, `rlm/core/comms_utils.py`
- **Test strategy**: `make check`. Add test with mock sub-LMs verifying routing by model name.
- **Depends on**: None

### RF-081: Document VS Code envFile + tool sets in playbooks
- **Source**: VS Code MCP servers docs — https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_standard-io-stdio-servers, https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_group-related-tools-in-a-tool-set
- **Category**: DX
- **Impact**: Low — improves onboarding. VS Code supports `envFile` for API keys (same as Cursor) and tool sets for grouping the 14 RLM gateway tools.
- **Effort**: Small
- **Description**: Add `envFile` property to `.vscode/mcp.json` example in playbooks. Document that VS Code supports tool sets for grouping related RLM tools. Mention `chat.mcp.autoStart` experimental setting for auto-restart.
- **Files affected**: `docs/integration/playbooks.md`, `.vscode/mcp.json`
- **Test strategy**: Manual: verify VS Code loads env vars from `.env` file when configured.
- **Depends on**: None

### RF-082: Submit RLM MCP gateway to GitHub MCP Registry
- **Source**: GitHub MCP Registry — https://github.com/mcp, https://docs.github.com/en/copilot/concepts/context/mcp#about-the-github-mcp-registry
- **Category**: DX
- **Impact**: Medium — makes RLM discoverable in VS Code's MCP server gallery (`@mcp` in Extensions view). GitHub has replaced Copilot Extensions with MCP as the primary extension mechanism.
- **Effort**: Medium
- **Description**: Prepare the RLM MCP gateway for submission to the GitHub MCP Registry. Requires: server naming conventions (camelCase), proper metadata, and potentially publishing as an npm/pip package. Would appear in VS Code Extensions view under "MCP Servers" section.
- **Files affected**: `README.md`, `scripts/rlm_mcp_gateway.py`, potentially `package.json` for npm packaging
- **Test strategy**: Manual: verify the MCP server appears in registry after submission.
- **Depends on**: RF-063 (programmatic MCP registration) or standalone gateway packaging

### RF-083: Port FINAL() callable and parser code fence handling from upstream PR #115
- **Source**: https://github.com/alexzhang13/rlm/pull/115 (open, Feb 19, 2026)
- **Category**: Core
- **Impact**: Medium — prevents false-positive final answer detection when LM writes code containing FINAL/FINAL_VAR inside code fences, comments, or strings. Makes FINAL() a callable function in REPL instead of a string match.
- **Effort**: Small
- **Description**: Port two changes from upstream PR #115: (1) Make `FINAL()` a callable function injected into the REPL environment (instead of pure regex matching on output). (2) Update `find_final_answer()` in the parser to ignore FINAL/FINAL_VAR patterns that appear inside code fences. Both changes improve parsing reliability for complex REPL outputs.
- **Files affected**: `rlm/utils/parsing.py`, `rlm/environments/local_repl.py`, `rlm/core/rlm.py`
- **Test strategy**: `make check`. Add test cases where FINAL appears inside code fences and verify it is not detected as a final answer. Verify FINAL() callable works in mock REPL.
- **Depends on**: None

### RF-084: Add MCP resource links in tool call results
- **Source**: MCP spec 2025-06-18, PR #603 — https://modelcontextprotocol.io/specification/2025-06-18/server/tools#resource-links
- **Category**: Protocol
- **Impact**: Low-medium — tool results from `rlm.complete` can include links to MCP resources (trajectories, iterations, sessions). Enables IDEs to show "Related Resources" alongside tool output for structured data browsing.
- **Effort**: Small
- **Description**: After `rlm.complete` finishes, include resource links in the tool result pointing to the session trajectory (`rlm://session/{id}/trajectory`) and individual iteration resources (`rlm://session/{id}/iteration/{n}`). These resources already exist in the gateway (RF-017/RF-019); this item adds links to them in tool call results.
- **Files affected**: `rlm/mcp_gateway/tools/complete_tools.py`
- **Test strategy**: `make test`. Add test verifying `rlm.complete` result includes resource links. Verify links resolve to existing MCP resources.
- **Depends on**: None
