# Research Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: 2026-02-19 18:00:00 -->

## Source Index

| Source | URL | Date Accessed | Key Findings | Relevance |
|---|---|---|---|---|
| Upstream rlm commits | https://github.com/alexzhang13/rlm/commits/main | 2026-02-19 | PR #84 merged: depth>1 recursive subcalls with `_subcall()`, `max_budget`/`BudgetExceededError`, event callbacks, execution limits (3168 additions). Version bumped to 0.1.1 (PyPI). New prompt templates (reasoning + math examples). PR #110 (compaction), #109 (scaffold), #108 (timeouts), #106 (custom tools) previously merged. | High |
| Upstream PR #84 | https://github.com/alexzhang13/rlm/pull/84 | 2026-02-19 | Full depth>1 `_subcall()` spawning child RLM instances, `BudgetExceededError`, OpenRouter cost extraction, `max_timeout`/`max_tokens`/`max_errors` limits, event callbacks (`on_subcall_start/complete`, `on_iteration_start/complete`). Referenced by DSPy integration (stanfordnlp/dspy#9289). | High |
| Upstream PR #115 (open) | https://github.com/alexzhang13/rlm/pull/115 | 2026-02-19 | FINAL() callable in REPL; parser ignores FINAL/FINAL_VAR inside code fences. Prevents false-positive final answer detection. | Medium |
| Upstream PR #114 (open) | https://github.com/alexzhang13/rlm/pull/114 | 2026-02-19 | Extra user-defined tools via `tool_prompts` + `tool_code` params. Alternative approach to #106, adds prompt-based tool doc + code injection. | Low |
| Upstream PR #54 (open) | https://github.com/alexzhang13/rlm/pull/54 | 2026-02-19 | Groq API and Cerebras SDK client implementations (149 additions). Enables high-throughput inference via Groq/Cerebras hardware. | Low |
| Upstream PR #53 (open) | https://github.com/alexzhang13/rlm/pull/53 | 2026-02-19 | Removed file-based roundtrip in `LocalREPL.add_context()`. | Low |
| Upstream issues | https://github.com/alexzhang13/rlm/issues | 2026-02-19 | 27 open. #113: pip install Python 3.10 broken stub. #111: metadata placement question. #100: Azure Anthropic. #97: CVEs in visualizer. #92: claude-agent-sdk client. #88: Standard API for 3rd-party tools. #82: Benchmarking/memoization. #50: Structured output on final answer. #42: ContextWindowExceededError. #31: K8s sandboxes. | Medium |
| Upstream forks | https://github.com/alexzhang13/rlm/forks | 2026-02-19 | 486 forks; no active fork has IDE integration features beyond what is adopted. | Low |
| VS Code LM Tools API | https://code.visualstudio.com/api/extension-guides/ai/tools | 2026-02-19 | `vscode.lm.registerTool`, `contributes.languageModelTools` in package.json, `when` clauses, `prepareInvocation` for confirmations, `canBeReferencedInPrompt`, `toolReferenceName`. Updated 12/10/2025. | High |
| VS Code MCP Developer Guide | https://code.visualstudio.com/api/extension-guides/ai/mcp | 2026-02-19 | `vscode.lm.registerMcpServerDefinitionProvider` for programmatic MCP registration. MCP Sampling with model access controls. MCP Apps (`@modelcontextprotocol/ext-apps`) with SDK (connect, callServerTool, sendMessage, updateModelContext). MCP Resources via "Add Context". Prompts as slash commands. Tool annotations (`title`, `readOnlyHint`). Dynamic tool discovery. MCP installation URL + CLI (`--add-mcp`). Dev mode (watch + debug). Streamable HTTP transport. Icons (`src` URI on servers/tools/resources). Autodiscovery from Claude Desktop. OAuth 2.1 with GitHub/Entra built-in + DCR fallback. Updated 02/04/2026. | High |
| VS Code AI Extensibility Overview | https://code.visualstudio.com/api/extension-guides/ai/ai-extensibility-overview | 2026-02-19 | Three paths: LM Tools, MCP Tools, Chat Participant. Decision guide: LM Tools for VS Code API integration; MCP Tools for cross-platform; Chat Participant for end-to-end control. Updated 02/04/2026. | High |
| MCP spec 2025-06-18 | https://modelcontextprotocol.io/specification/2025-06-18 | 2026-02-19 | New revision: Removed JSON-RPC batching. Added structured tool output (`outputSchema`/`structuredContent`). Elicitation (server→user queries). Resource links in tool results. `title` field for display names. `context` field in CompletionRequest. OAuth as Resource Server with RFC 8707. `_meta` on more types. Protocol version header for HTTP. | High |
| MCP spec changelog | https://modelcontextprotocol.io/specification/2025-06-18/changelog | 2026-02-19 | 9 major changes + 3 schema changes since 2025-03-26. Batching removed (RF-060 is invalid). Structured output is the biggest tool-facing change. | High |
| Cursor MCP docs | https://cursor.com/docs/context/mcp | 2026-02-19 | Tools, Prompts, Resources, Roots, Elicitation all supported. Three transports (stdio/SSE/Streamable HTTP). Config interpolation (`${workspaceFolder}`, `${env:NAME}`, `${userHome}`, `${pathSeparator}`). `envFile` for stdio servers. Auto-run for tools. OAuth with static client credentials. One-click install buttons. | High |
| Cursor MCP Extension API | https://cursor.com/docs/context/mcp-extension-api | 2026-02-19 | `vscode.cursor.mcp.registerServer()` / `unregisterServer()`. Types: `StdioServerConfig`, `RemoteServerConfig`. Enables programmatic MCP registration without mcp.json. | High |
| DSPy RLM integration | https://github.com/stanfordnlp/dspy/issues/9289, https://github.com/stanfordnlp/dspy/pull/9295 | 2026-02-19 | Production-ready RLM for DSPy: multimodal media support (`llm_query_with_media`), budget controls (`budget()`, `max_time`, `max_cost`), multi-model sub-call routing (`sub_lms`), LocalInterpreter (unsandboxed), depth>1 recursion, GEPA compatibility. 20+ tests. +2825 lines. | Medium |
| RLM paper v2 | https://arxiv.org/abs/2512.24601v2 | 2026-02-19 | Updated Jan 28, 2026 (v2). 9 pages + 33 appendix. Core design: REPL interaction, recursive sub-calls, context decomposition, FINAL/FINAL_VAR semantics. | High |
| RLM blog | https://alexzhang13.github.io/blog/2025/rlm/ | 2026-02-19 | Strategies: Peeking, Grepping, Partition+Map, Summarization, Long-input/long-output. Benchmarks: RLM(GPT-5-mini) outperforms GPT-5 on OOLONG 132k by 114%. BrowseComp-Plus: only RLM maintains perfect performance at 1000 docs. Limitations: no async sub-calls, no cost/runtime guarantees. Future: RL-ifiable trajectories as inference-time scaling axis. | High |
| rlm-minimal | https://github.com/alexzhang13/rlm-minimal | 2026-02-19 | Gist-like RLM implementation. 683 stars, 109 forks. `rlm_repl.py` + `repl.py`. Only depth=1 in default config; depth>1 via swapping `Sub_RLM` → `RLM_REPL`. PR #3 merged (swap model config). No IDE integration features. | Low |
| rlm-minimal forks | https://github.com/alexzhang13/rlm-minimal/forks | 2026-02-19 | 109 forks; only `mateolafalce/human-action-rlm` (7 stars) is notable. No IDE-relevant changes in any fork. | Low |
| VS Code MCP servers | https://code.visualstudio.com/docs/copilot/chat/mcp-servers | 2026-02-19 | Config format: stdio/HTTP/SSE. `envFile` in stdio config. Input variables (`promptString`) for API keys. Tool sets for grouping. `chat.mcp.autoStart` (experimental). MCP server gallery (`@mcp` in Extensions). Settings Sync for MCP configs. Enterprise management via GitHub policies. Max 128 tools per request. Unix socket support. Server naming: camelCase. Updated 02/04/2026. | High |
| GitHub Copilot Extensions/MCP | https://docs.github.com/en/copilot/concepts/context/mcp | 2026-02-19 | GitHub now uses MCP as the primary Copilot extension mechanism (replaces old Copilot Extensions skillset/agent model). GitHub MCP Registry at github.com/mcp. Enterprise MCP policy (enabled/disabled per org). GitHub MCP server supports remote access + toolset customization. | Medium |

## Implemented (previous sessions, RF-001 through RF-074)

All items from RF-001 through RF-074 (except blocked RF-065, RF-069, RF-070) have been implemented and verified. This includes upstream PRs #106 (custom tools), #108 (timeouts), #109 (scaffold protection), #110 (compaction); VS Code LM tools registration; MCP tool annotations; MCP prompts; MCP resources; MCP sampling bridge; MCP programmatic server registration (both VS Code RF-063 and Cursor RF-066); token budget protection; soft cancellation; streaming; follow-up provider; Streamable HTTP endpoints; chunk metadata reconstruction; model preferences; fail-fast semantics; tools/list_changed notifications; Cursor rules; provider-native streaming; and more. See `docs/orchestrator/state.json` for the full verified list.

## VS Code Copilot Agent Chat

### Current State (this project)
- Chat Participant `@rlm` with commands: `analyze`, `summarize`, `search`
- Two Language Model Tools registered: `rlm_analyze`, `rlm_execute`
- Workspace MCP config at `.vscode/mcp.json` (stdio transport)
- Backend bridge spawns `rlm_backend.py` via stdio JSON protocol
- MCP Prompts, Resources, Sampling implemented in gateway
- Tool annotations with `readOnlyHint` on all gateway tools
- Programmatic MCP server registration via `vscode.lm.registerMcpServerDefinitionProvider` (RF-063)
- Token-level streaming for final answer (RF-011)
- Soft cancellation via `type: cancel` (RF-012)
- Token budget protection (RF-013)
- Follow-up provider (RF-007)

### Best Available Methods
1. **`vscode.lm.registerMcpServerDefinitionProvider`** — VS Code supports programmatic MCP server registration from extensions. Instead of relying on `.vscode/mcp.json`, the extension can auto-register the RLM MCP gateway on activation, providing a seamless zero-config experience.
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp#register-an-mcp-server-in-your-extension
   - Requires `contributes.mcpServerDefinitionProviders` in package.json
   - Implementation: `McpStdioServerDefinition` with command/args
   - Also supports `McpHttpServerDefinition` for Streamable HTTP
   - Benefit: Users don't need to manually configure `.vscode/mcp.json`

2. **MCP Apps** — Interactive UI components in tool responses. Could render iteration progress timelines, code execution results, or provenance graphs inline in chat.
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp (MCP Apps section)
   - SDK: `@modelcontextprotocol/ext-apps` — `App.connect()`, `callServerTool()`, `sendMessage()`, `updateModelContext()`
   - Architecture: Tool returns `_meta.ui.resourceUri` pointing to `ui://` HTML resource with `text/html;profile=mcp-app` MIME
   - Security: Sandboxed iframe with CSP; declare `connectDomains`, `resourceDomains`, `frameDomains`
   - Status: Available in VS Code (inline display mode only, no fullscreen or pip)

3. **MCP Installation URL** — `vscode:mcp/install?{json-config}` enables one-click MCP server installation from a web page or CLI. Also `--add-mcp` CLI option.
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp#create-an-mcp-installation-url
   - Could be added to README / docs for easy setup

4. **MCP Dev Mode** — VS Code supports `dev` config for MCP servers with `watch` (file glob for auto-restart) and `debug` (Node.js/Python debugger attachment).
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp#mcp-development-mode-in-vs-code
   - Could provide dev mode config in `.vscode/mcp.json` for contributors

5. **MCP Icons** — VS Code supports icons on MCP servers, resources, and tools via `src` URI property. Stdio servers can use `file:///` URIs or data URIs.
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp (Icons section)
   - Could add RLM icon to the MCP server definition for better visual identification

6. **Autodiscovery** — VS Code can discover MCP servers from other tools (e.g., Claude Desktop config).
   - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp (Add MCP servers section)
   - Informational: users who have RLM configured in Claude Desktop would see it in VS Code too

7. **Tool Sets** — VS Code supports grouping tools into named tool sets. The 14 RLM gateway tools could be grouped into logical sets (e.g., "RLM Core", "RLM Search", "RLM Files") for easier management.
   - Source: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_group-related-tools-in-a-tool-set
   - Reduces tool picker clutter; no code change needed (VS Code manages grouping)

8. **`envFile` support** — VS Code also supports `envFile` in stdio config (not just Cursor). Can reference `.env` for API keys.
   - Source: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_standard-io-stdio-servers
   - Could add `envFile` to `.vscode/mcp.json` for consistent API key management across both IDEs

9. **`chat.mcp.autoStart`** — Experimental VS Code setting to auto-start MCP servers when config changes. Reduces manual server restarts.
   - Source: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_automatically-start-mcp-servers
   - Informational: document in playbooks for better DX

10. **GitHub MCP as Copilot Extension Mechanism** — GitHub now uses MCP as the primary way to extend Copilot (replacing the old Copilot Extensions skillset/agent model). The RLM MCP gateway approach is the correct architecture.
    - Source: https://docs.github.com/en/copilot/concepts/context/mcp
    - GitHub MCP Registry at github.com/mcp could host the RLM gateway in the future
    - Enterprise MCP policy (enabled/disabled per org) — enterprise users may need approval

11. **OAuth 2.1 Authorization** — VS Code supports MCP server authorization via OAuth 2.1 with built-in GitHub and Microsoft Entra support, plus DCR fallback for other IdPs. Relevant if the gateway is deployed as a remote HTTP service for enterprise use.
    - Source: https://code.visualstudio.com/api/extension-guides/ai/mcp (Authorization section)
    - Redirect URLs: `http://127.0.0.1:33418` and `https://vscode.dev/redirect`
    - Users manage trusted MCP servers via Accounts menu

12. **Resource links in tool results** — MCP spec 2025-06-18 adds resource links in tool results (PR #603). Tool responses from `rlm.complete` could link to trajectory resources, providing structured access to iteration data.
    - Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#resource-links

### Recommended Changes (ranked by impact, with evidence)
1. **Add MCP elicitation support** (RF-065) — Medium impact. Server can request user input during tool execution (e.g., API key, confirmation). **BLOCKED** pending SDK/design decision.
2. **Add resource links in tool results** (RF-084) — Low-medium impact. `rlm.complete` returns links to trajectory/iteration resources for structured data access.
3. **Add MCP Icons to server/tools** (RF-076) — Low impact. Better visual identification in tools picker/server list.

## Cursor Agent Chat

### Current State (this project)
- MCP config at `.cursor/mcp.json` (stdio transport)
- Extension detects Cursor and skips Chat Participant registration
- MCP gateway fully functional with all 14+ tools
- Cursor rules in `.cursor/rules/` for tool-use behavior
- MCP Prompts/Resources/Sampling available
- Programmatic MCP registration via `vscode.cursor.mcp.registerServer()` (RF-066)

### Best Available Methods
1. **`vscode.cursor.mcp.registerServer()`** — Cursor extension API for programmatic MCP server registration (RF-066, implemented).
   - Source: https://cursor.com/docs/context/mcp-extension-api

2. **Elicitation** — Cursor supports MCP elicitation (server-initiated user queries). Could be used for API key prompting, confirmation dialogs.
   - Source: https://cursor.com/docs/context/mcp (protocol support table)

3. **Config interpolation** — Cursor resolves `${workspaceFolder}`, `${env:NAME}`, `${userHome}`, `${workspaceFolderBasename}`, `${pathSeparator}` in mcp.json.
   - Source: https://cursor.com/docs/context/mcp (config-interpolation section)

4. **`envFile` support** — Cursor supports `envFile` path in stdio server config to load environment variables from a `.env` file.
   - Source: https://cursor.com/docs/context/mcp (stdio-server-configuration section)
   - Could add `envFile` to `.cursor/mcp.json` example for API key management

5. **Static OAuth** — Cursor supports `auth` object on remote servers with `CLIENT_ID`, `CLIENT_SECRET`, `scopes` for static OAuth without DCR.
   - Source: https://cursor.com/docs/context/mcp (static-oauth-for-remote-servers section)
   - Relevant if the gateway is deployed as a remote HTTP service

6. **One-click install** — Cursor supports "Add to Cursor" buttons and a browseable MCP server directory.
   - Source: https://cursor.com/docs/context/mcp (one-click-installation section)

7. **Auto-run** — Cursor supports auto-run for trusted tools, bypassing confirmation prompts.
   - Source: https://cursor.com/docs/context/mcp (auto-run section)

### Recommended Changes (ranked by impact, with evidence)
1. **Use elicitation for API key prompting** (RF-069) — Medium impact. When `rlm.complete` needs API key, server can request it via elicitation instead of failing. **BLOCKED** on RF-065.
2. **Document envFile in Cursor config** (RF-079) — Low impact. Simplifies API key management for Cursor users.
3. **Submit to Cursor MCP directory** — Low impact. Makes RLM discoverable via "Add to Cursor" button.

## Upstream Delta

### Features in upstream not in this fork

1. **PR #84: Depth>1 recursive subcalls** (merged Feb 18, 2026) — 3168 additions, 216 deletions
   - `_subcall()` method spawning child RLM instances with incremented depth
   - `BudgetExceededError` with `max_budget` parameter, OpenRouter cost extraction
   - Execution limits: `max_timeout`, `max_tokens`, `max_errors` with exceptions
   - Event callbacks: `on_subcall_start`, `on_subcall_complete`, `on_iteration_start`, `on_iteration_complete`
   - `_subcall()` returns `RLMChatCompletion` (uniform return type)
   - Files: `rlm/core/rlm.py`, `rlm/core/types.py`, `rlm/environments/local_repl.py`, `rlm/clients/openai.py`, `rlm/logger/verbose.py`
   - Tests: 13 unit tests + 1 e2e test
   - **Impact**: High — enables true recursive decomposition. Current fork has `max_depth=1` ceiling.
   - **DSPy reference**: stanfordnlp/dspy#9289 references this PR for production-ready RLM.

2. **PR #115: FINAL() callable + code fence parser fix** (open, Feb 19, 2026)
   - Makes FINAL() a callable function in REPL environment (not just a string match)
   - Parser ignores FINAL/FINAL_VAR patterns appearing inside code fences (```...```)
   - Prevents false-positive final answer detection when LM writes code containing FINAL in comments/strings
   - **Impact**: Medium — improves parsing reliability for complex REPL outputs

3. **Version 0.1.1 on PyPI** (Feb 18, 2026)
   - Upstream published to PyPI as `rlms` package (commit `beb0603`)
   - Users can `pip install rlms` (Python 3.11+ required; Python 3.10 installs broken stub per issue #113)
   - **Impact**: Low for fork — informational.

4. **New prompt templates** (Feb 18, 2026)
   - "merge in new prompt with reasoning example" (commit `97bbe97`)
   - "updated prompt with math example" (commit `725b734`)
   - **Impact**: Medium — improved default prompts could improve RLM quality for common use cases.

5. **PR #114: Extra user-defined tools** (open, Feb 18, 2026)
   - `tool_prompts`: Append extra prompt sections (string or list) to system prompt for documenting custom tools
   - `tool_code`: Inject Python code into REPL environment before each completion (merged into `setup_code`)
   - 265 additions, alternative approach to PR #106 (custom tools, already ported)
   - **Impact**: Low — this fork already has custom tools via RF-052/RF-053.

6. **PR #54: Groq API + Cerebras SDK** (open, Jan 17, 2026)
   - Adds `GroqClient` and `CerebrasClient` implementations (149 additions)
   - Enables high-throughput inference via Groq/Cerebras hardware
   - **Impact**: Low — these providers are accessible via `litellm` client already.

7. **PR #53: Remove file roundtrip in add_context()** (open, Jan 17, 2026)
   - Removes unnecessary file-based serialization in `LocalREPL.add_context()`
   - **Impact**: Low — minor performance/code quality improvement.

8. **Backend alias routing for extension-only providers** — Extension settings include `vercel`, `openrouter`, and `vllm`; these are now routed through `litellm` by prefixing model names (`<provider>/<model>`) in the extension Python backend.

### Features in forks worth adopting
- No active forks of rlm (486 forks) or rlm-minimal (109 forks) have IDE-integration features beyond what is already adopted.
- Only notable rlm-minimal fork: `mateolafalce/human-action-rlm` (7 stars) — a domain-specific RLM application, not relevant for IDE integration.

## Paper/Blog Insights

### Unimplemented techniques
- **Structured output for final answers** — Paper describes FINAL semantics. Issue #50 requests structured output. MCP spec 2025-06-18 adds `outputSchema`/`structuredContent` which aligns.
- **Memoization of sub-calls** — Issue #82 proposes caching sub-call results for repeated patterns. Not implemented in upstream or fork.
- **Asynchronous sub-calls** — Blog explicitly notes: "each recursive LM call is both blocking and does not take advantage of any kind of prefix caching." Parallelizing independent sub-calls in Partition+Map strategy could reduce latency significantly. Not implemented in upstream.
- **Cost/runtime guarantees** — Blog notes: "we do not currently have strong guarantees about controlling either the total API cost or the total runtime of each call." DSPy integration (stanfordnlp/dspy#9289) addresses this with `budget()`, `max_time`, `max_cost`. Upstream PR #84 adds `max_budget`/`BudgetExceededError`.

### Design rationale clarifications
- **Context-centric decomposition** — Blog clarifies RLMs decompose by context (not by task/problem). "We retain the view that LM calls can be decomposed by the context, and the choice of decomposition should purely be the choice of an LM." Differs from agents (task decomposition).
- **Metadata as user message** — Issue #111 questions metadata placement. Upstream PR #84 changed metadata role to "user" (already adopted via RF-056).
- **Paper v2 update** (Jan 28, 2026) — Minor revisions to appendix; core design unchanged.

### Emergent RLM strategies (from blog)
1. **Peeking** — Root LM grabs small slices of context to observe structure (e.g., first 2000 chars).
2. **Grepping** — Uses regex/keyword patterns to narrow lines of interest (semantic retrieval replacement).
3. **Partition + Map** — Chunks context → recursive LM calls per chunk → aggregation. Most common for semantic tasks.
4. **Summarization** — Summarizes subsets of context for root LM decision-making.
5. **Long-input/long-output** — One-shots programmatic tasks (e.g., LoCoDiff benchmark: tracking git diff history via code execution).

These strategies emerge naturally without prompting. Blog notes: "a lot more patterns will emerge when models get better and are trained to work this way."

## Academic/Industry Patterns

### Applicable patterns from other projects

1. **DSPy RLM integration** (stanfordnlp/dspy#9289, PR #9295) — Comprehensive production-ready RLM features for DSPy:
   - **Multimodal media**: `llm_query_with_media(prompt, *media_var_names)` — auto-detects Audio/Image inputs, adds them as multimodal content parts to sub-LLM calls. Media objects held in registry outside sandbox.
   - **Multi-model sub-call routing**: `sub_lms={"strong": lm_pro}` — named LM dict, sandbox selects model via `llm_query(prompt, model="strong")`.
   - **Budget awareness**: `budget()` callable in sandbox returns human-readable summary of remaining iterations, LLM calls, time, cost. Warns at <20% threshold. `max_time`/`max_cost` trigger extract-fallback (not crash).
   - **LocalInterpreter**: Unsandboxed `exec()` in host process. State persists across iterations. Full package access (numpy, PIL, etc.).
   - **GEPA resilience**: Broad `except Exception` handler preserves partial trace for optimization.
   - **Depth>1 via LocalInterpreter**: Child inherits parent's interpreter type. Budget propagation: children receive remaining time/cost.
   - **Branch**: +2825 lines, 20 new tests, 6 test classes.
   - **Relevance to this fork**: Multi-model routing (`sub_lms`) pattern is directly applicable. Budget awareness (`budget()`) callable could be exposed in REPL. Multimodal support requires paper/design work.

### MCP protocol opportunities

1. **Elicitation** (spec 2025-06-18) — Server can request input from users mid-tool. Could prompt for API keys, environment selection, or confirmation before expensive operations.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation

2. **Structured tool output** (spec 2025-06-18) — `outputSchema`/`structuredContent` allows tools to return typed data alongside text. Could structure `rlm.complete` results with typed fields for answer, iterations, usage.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#structured-content

3. **Resource links in tool results** (spec 2025-06-18, PR #603) — Tool results can include links to MCP resources. `rlm.complete` could link to trajectory/iteration resources for IDE to browse.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#resource-links

4. **JSON-RPC batching removed** (spec 2025-06-18) — RF-060 is now **invalid**; batching was removed from the spec.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/changelog (Major change #1)

5. **`context` field in CompletionRequest** (spec 2025-06-18) — Completion requests can include previously-resolved variables. Relevant for MCP prompt argument autocompletion.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/changelog (Schema change #2)

6. **Protocol version header** (spec 2025-06-18) — `MCP-Protocol-Version` header required in subsequent HTTP requests after negotiation.
   - Source: https://modelcontextprotocol.io/specification/2025-06-18/changelog (Major change #8)

## Cross-Cutting Concerns

### Streaming and progress
- Extension backend streams iteration progress via JSON-over-stdin/stdout (RF-029 implemented).
- MCP gateway uses text-based progress in tool results.
- MCP Apps could replace text progress with interactive UI (future exploration, RF-062).

### Cancellation
- Soft cancellation implemented in extension backend (RF-012).
- MCP gateway has no cancellation support for long-running `rlm.complete` calls. MCP spec supports cancellation notifications (`notifications/cancelled`). See RF-075.

### Multi-turn and persistence
- `SupportsPersistence` protocol with `save_state()`/`load_state()` implemented.
- Extension supports multi-turn sessions with `newSession` command.

### Security boundaries
- Two sandbox tiers documented in `docs/quality/security_surfaces.md`.
- MCP gateway has path validation, CORS restriction, optional API key auth.
- MCP spec 2025-06-18 strengthens OAuth requirements (Resource Indicators per RFC 8707) — relevant if HTTP mode is exposed publicly.
- VS Code supports OAuth 2.1 for MCP servers with built-in GitHub/Entra auth + DCR fallback.

### Configured backend routing
- Extension `package.json` lists `openrouter`, `vercel`, `vllm` as backend options.
- Extension Python backend maps these selections to `litellm` and prefixes model names for provider routing.
- No dedicated `rlm/clients/*` wrappers are required for these three providers in extension API-key mode.
