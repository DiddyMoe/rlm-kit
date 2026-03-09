# Research Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: 2026-07-15 12:00:00 -->

## Source Index

| Source | URL | Date Accessed | Key Findings | Relevance |
|---|---|---|---|---|
| Upstream rlm repo | https://github.com/alexzhang13/rlm | 2026-07-15 | ~2.9k stars, 548 forks, 20+ contributors. Latest: `2e5764b` (Mar 2) — semaphore queue for batched sub-calls. Release v0.1.1a (depth>1, compaction). 36 open PRs, 28 open issues. | High |
| Upstream commit Mar 2 | https://github.com/alexzhang13/rlm/pull/131 | 2026-03-02 | PR #131 (merged): Replace `asyncio.run_all()` with semaphore queue for batched LM sub-calls. Cap batching to 16. 99 additions, 12 deletions. | High |
| Upstream PR #129 (open) | https://github.com/alexzhang13/rlm/pull/129 | 2026-07-15 | Fix budget tracking: cumulative cost with handler deltas. Fixes subcall cost visibility and `_check_iteration_limits` overwriting `_cumulative_cost`. 128+/16-. By le-big-mac. | High |
| Upstream PR #127 (open) | https://github.com/alexzhang13/rlm/pull/127 | 2026-07-15 | Claude 4.6 hallucinated FINAL() fix — skip text FINAL when code blocks present. 7+/1-. By huiwenn. Upstream author hesitant ("ideally less hacky solutions"). | High |
| Upstream PR #126 (open) | https://github.com/alexzhang13/rlm/pull/126 | 2026-07-15 | Anthropic prompt caching (`cache_control` annotations), per-model USD cost tracking with built-in pricing table, shared LM handler for child RLMs, cache-aware billing. 1047+/63-. By iam-dev. | Medium |
| Upstream PR #125 (open) | https://github.com/alexzhang13/rlm/pull/125 | 2026-02-27 | Claude Code CLI client + unit tests. New backend for Claude Code as RLM client. | Low |
| Upstream PR #124 (open) | https://github.com/alexzhang13/rlm/pull/124 | 2026-02-27 | Replace 15 bare `except:` with `except Exception:` in REPL environments. Already fixed in this fork (RF-087). | Medium |
| Upstream PR #122 (open) | https://github.com/alexzhang13/rlm/pull/122 | 2026-02-27 | Fix incorrect numbering of custom tools section in system prompt. Already fixed in this fork (RF-088). | Low-Medium |
| Upstream PR #115 (open) | https://github.com/alexzhang13/rlm/pull/115 | 2026-07-15 | Two fixes: (1) parser matched FINAL() inside fenced code blocks → wrong answers, (2) FINAL never injected into REPL globals → NameError. Adds `_final()` method, adds FINAL to RESERVED_TOOL_NAMES. 57+/2-. By jkbrooks. | Medium |
| Upstream PR #114 (open) | https://github.com/alexzhang13/rlm/pull/114 | 2026-02-19 | Extra user-defined tools via `tool_prompts` + `tool_code` params. | Low |
| Upstream PR #84 (merged) | https://github.com/alexzhang13/rlm/pull/84 | 2026-02-19 | Depth>1 `_subcall()`, `BudgetExceededError`, cost tracking, execution limits, event callbacks. 3168 additions. Already implemented in this fork (RF-070). | High |
| Upstream PR #54 (open) | https://github.com/alexzhang13/rlm/pull/54 | 2026-02-19 | Groq API and Cerebras SDK client implementations. Already implemented in this fork (RF-077). | Low |
| Upstream PR #49 (open) | https://github.com/alexzhang13/rlm/pull/49 | 2026-07-15 | Multimodal support (vision and audio). 1 review requesting changes. 3 comments. | Medium |
| Upstream PR #46 (open) | https://github.com/alexzhang13/rlm/pull/46 | 2026-07-15 | Jupyter Support, Traces & Persistent REPL (Specs 00-02). 4 tasks done. | Low |
| Upstream PR #16 (open) | https://github.com/alexzhang13/rlm/pull/16 | 2026-07-15 | Interactive playground for running new queries. 7 comments. | Low |
| Upstream issues | https://github.com/alexzhang13/rlm/issues | 2026-07-15 | 28 open. #117: VLM sub-queries. #113: pip 3.10 stub. #100: Azure Anthropic. #92: claude-agent-sdk. #88: Standard API. #82: Memoization. #50: Structured output. #42: ContextWindowExceeded. #31: K8s sandboxes. | Medium |
| VS Code v1.99 release notes | https://code.visualstudio.com/updates/v1_99 | 2026-07-15 | March 2025: Agent mode stable, MCP server support, fetch/usages/thinking tools, BYOK preview, unified chat view, prompt files, extension tools in agent mode, SWE-bench 56% pass rate. | High |
| VS Code v1.100 release notes | https://code.visualstudio.com/updates/v1_100 | 2026-07-15 | April 2025: Instructions/prompt files, `#githubRepo` tool, Streamable HTTP MCP, MCP image output, conversation summary + prompt caching, MCP tool annotations (`readOnlyHint`), proposed MCP extension API. | High |
| VS Code v1.101 release notes | https://code.visualstudio.com/updates/v1_101 | 2026-07-15 | May 2025: MCP Prompts/Resources/Sampling/Auth GA, tool sets, MCP dev mode, MCP extension APIs finalized, custom chat modes preview, terminal cwd context, Electron 35/Node 22. | High |
| VS Code v1.102 release notes | https://code.visualstudio.com/updates/v1_102 | 2026-07-15 | June 2025: **Copilot Chat open-sourced** (MIT), **MCP GA**, elicitations, MCP server gallery + discovery, MCP first-class resources (`mcp.json` per profile), MCP migration from settings.json, custom chat modes improvements, terminal auto-approval, CLI `code chat`, edit previous requests, instructions on demand. | Critical |
| VS Code LM Tools API | https://code.visualstudio.com/api/extension-guides/ai/tools | 2026-03-02 | `vscode.lm.registerTool`, `contributes.languageModelTools`, `when` clauses, `prepareInvocation`. | High |
| VS Code MCP Developer Guide | https://code.visualstudio.com/api/extension-guides/ai/mcp | 2026-07-15 | Full suite: Tools, Prompts, Resources, Elicitation, Sampling, MCP Apps, Icons, OAuth 2.1, Streamable HTTP, Dev Mode, Extension APIs. | High |
| VS Code AI Extensibility Overview | https://code.visualstudio.com/api/extension-guides/ai/ai-extensibility-overview | 2026-03-02 | Three paths: LM Tools, MCP Tools, Chat Participant. | High |
| MCP spec 2025-06-18 | https://modelcontextprotocol.io/specification/2025-06-18 | 2026-03-02 | Structured tool output, elicitation, resource links, `title` field, OAuth as Resource Server, protocol version header. | High |
| MCP spec changelog | https://modelcontextprotocol.io/specification/2025-06-18/changelog | 2026-02-27 | 9 major + 3 schema changes since 2025-03-26. Batching removed, structured output biggest change. | High |
| Cursor MCP docs | https://cursor.com/docs/context/mcp | 2026-03-02 | Tools, Prompts, Resources, Roots, Elicitation supported. stdio/SSE/Streamable HTTP. Config interpolation. `envFile`. Auto-run. OAuth. | High |
| Cursor MCP Extension API | https://cursor.com/docs/context/mcp-extension-api | 2026-02-19 | `vscode.cursor.mcp.registerServer()`/`unregisterServer()`. | High |
| VS Code MCP servers user docs | https://code.visualstudio.com/docs/copilot/chat/mcp-servers | 2026-02-19 | `envFile`, tool sets, `chat.mcp.autoStart`, MCP gallery, max 128 tools. | High |
| GitHub Copilot MCP | https://docs.github.com/en/copilot/concepts/context/mcp | 2026-02-19 | MCP is primary Copilot extension mechanism. GitHub MCP Registry. | Medium |
| DSPy RLM issue #9289 | https://github.com/stanfordnlp/dspy/issues/9289 | 2026-07-15 | Now has linked PR #9295 (+2825 lines). Multimodal media, budget controls (`budget()`, `max_time`, `max_cost`), multi-model routing (`sub_lms`), LocalInterpreter, depth>1 recursion, GEPA bootstrap_trace resilience. 20 new tests. | Medium |
| RLM paper v2 | https://arxiv.org/abs/2512.24601v2 | 2026-02-19 | Updated Jan 28, 2026. Core design unchanged. | High |
| RLM blog | https://alexzhang13.github.io/blog/2025/rlm/ | 2026-02-19 | Strategies, benchmarks, limitations. | High |
| rlm-minimal | https://github.com/alexzhang13/rlm-minimal | 2026-02-19 | 683 stars, 109 forks. No IDE integration. | Low |

## Implemented (previous sessions, RF-001 through RF-090)

All items from RF-001 through RF-090 have been implemented and verified. See `docs/orchestrator/state.json` for the full verified list. Key recent additions:
- RF-070: Recursive subcalls with budget propagation (depth>1, error/timeout/cost rollup)
- RF-075: MCP cancellation support
- RF-087: Bare except cleanup
- RF-088: Custom tools numbering fix
- RF-089: Semaphore queue for batched sub-calls
- RF-090: BudgetExceededError and cumulative cost tracking

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
- Resource links in `rlm.complete` tool results (RF-084)

### New Developments (v1.100–v1.102)

1. **Copilot Chat open-sourced** (v1.102, MIT license) — Full source at `microsoft/vscode-copilot-chat`. Includes agent mode prompts, inline chat, MCP integration implementation. Enables deep study of how chat participant → agent mode → tool calling works internally.

2. **MCP GA** (v1.102) — MCP is now generally available, no longer experimental. Organization policies can control MCP availability.

3. **MCP first-class resources** (v1.102) — MCP servers now stored in dedicated `mcp.json` per VS Code profile, not `settings.json`. Automatic migration from old format. Settings Sync integration.

4. **Elicitation support** (v1.102) — VS Code supports MCP elicitations per 2025-06-18 spec. Servers can request structured user input.

5. **MCP server gallery + discovery** (v1.102) — VS Code `code.visualstudio.com/mcp` curated list, Extensions view integration, one-click install, management view.

6. **Custom chat modes** (v1.101 preview → v1.102 improvements) — `.chatmode.md` files with `model`, `tools`, `description` metadata. Import via `vscode:chat-mode/install?url=...`. Configure gear menu.

7. **Instructions on demand** (v1.102) — LLM can load `.instructions.md` files on demand based on glob patterns and descriptions.

8. **Terminal auto-approval** (v1.102, experimental) — Allow/deny list for auto-approving terminal commands. `github.copilot.chat.agent.terminal.allowList`/`denyList`.

9. **CLI chat** (v1.102) — `code chat [options] [prompt]` with `-m` mode, `-a` add-file, `--maximize`. Enables headless/script-driven RLM integration.

10. **MCP Auth** (v1.101) — OAuth 2.1 authorization for MCP servers (both 2025-03-26 and draft specs). GitHub/Entra built-in.

11. **MCP Dev Mode** (v1.101) — `dev.watch` for file-watching restarts, `dev.debug` for Node.js/Python server debugging.

12. **Tool sets** (v1.101) — Group tools into named sets, enable/disable together, reference via `#setname`.

13. **Conversation summary + prompt caching** (v1.100) — Automatic conversation compression for long sessions. Stable prefix for reduced latency.

### Best Available Methods
1. **`vscode.lm.registerMcpServerDefinitionProvider`** — Programmatic MCP server registration (implemented, RF-063).
2. **MCP Apps** — Interactive UI in tool responses via `@modelcontextprotocol/ext-apps` SDK (RF-062).
3. **MCP Installation URL** — `vscode:mcp/install?{json-config}` for one-click setup.
4. **Custom Chat Modes** — `.chatmode.md` for tailored RLM workflows (e.g., "RLM Agent" mode with specific tools).
5. **Instructions on demand** — LLM auto-loads relevant `.instructions.md` files.
6. **MCP Dev Mode** — `watch` + `debug` config for contributors.
7. **MCP Icons** — `icons` with `src` URI on servers/tools/resources.
8. **Tool Sets** — Tool grouping for reduced picker clutter.
9. **`envFile` support** — API key management in MCP config.
10. **GitHub MCP Registry** — MCP is primary Copilot extension mechanism.
11. **Terminal auto-approval** — Auto-approve safe commands for faster agent loops.
12. **CLI `code chat`** — Script-driven RLM invocation from terminal.

### Recommended Changes (ranked by impact, with evidence)
1. **Explore MCP Apps for interactive RLM UI** (RF-062) — Future. Replace text progress with interactive visualization.
2. ~~**Provide custom chat mode for RLM** (RF-091)~~ — DONE. Created `.vscode/rlm-agent.chatmode.md`.
3. ~~**MCP `mcp.json` migration** (RF-092)~~ — DONE. Verified `.vscode/mcp.json` already v1.102-compatible.
4. ~~**Adopt Anthropic prompt caching** (RF-093)~~ — DONE. Added `_ANTHROPIC_PRICING` table and `get_estimated_cost()` to `rlm/clients/anthropic.py`.
5. ~~**Budget tracking fix from PR #129** (RF-094)~~ — DONE. Handler-delta approach already implemented; added subcall cost accumulation tests.
6. **FINAL() safety from PR #115 and PR #127** (RF-095/RF-096/RF-097) — RF-096 (hallucination guard) and RF-097 (code-fence stripping + FINAL in RESERVED_TOOL_NAMES) are DONE. RF-095 remains P4 (needs user approval).

## Cursor Agent Chat

### Current State (this project)
- MCP config at `.cursor/mcp.json` (stdio transport)
- Extension detects Cursor and skips Chat Participant registration
- Programmatic MCP registration via `vscode.cursor.mcp.registerServer()` (RF-066)
- MCP gateway fully functional with all 14+ tools
- Cursor rules in `.cursor/rules/`
- MCP Prompts/Resources/Sampling available

### Best Available Methods
1. **`vscode.cursor.mcp.registerServer()`** — Programmatic registration (RF-066, implemented).
2. **Elicitation** — Cursor supports server-initiated user queries.
3. **Config interpolation** — `${workspaceFolder}`, `${env:NAME}`, `${userHome}`, etc.
4. **`envFile` support** — API key management via `.env` file.
5. **Static OAuth** — `auth` object for remote server authentication.
6. **One-click install** — "Add to Cursor" buttons.
7. **Auto-run** — Bypass confirmation for trusted tools.

### Recommended Changes (ranked by impact, with evidence)
_(No remaining Cursor-specific actions.)_

## Upstream Delta

### Features in upstream not in this fork

1. **PR #129: Budget tracking fix** (open) — ~~Ported~~ (RF-094). Handler-delta approach implemented; subcall cost accumulation tests added.

2. **PR #127: Claude 4.6 hallucinated FINAL()** (open) — ~~Ported~~ (RF-096). `find_final_answer()` skips text-based FINAL() when code blocks are present.

3. **PR #126: Anthropic prompt caching** (open, 1047 additions) — ~~Ported~~ (RF-093). Added `_ANTHROPIC_PRICING` table, `get_estimated_cost()` with cache-aware billing.

4. **PR #115: FINAL() callable in REPL** (open, 57 additions) — ~~Ported~~ (RF-097). Added `"FINAL"` to `RESERVED_TOOL_NAMES`. Code-fence stripping and FINAL callable were already implemented.

5. **PR #125: Claude Code CLI client** (open) — Niche. Low priority.

6. **PR #49: Multimodal support** (open, changes requested) — Vision and audio inputs.

### Notable upstream issues
- #117: VLM sub-queries
- #100: Azure Anthropic
- #92: claude-agent-sdk
- #82: Memoization
- #50: Structured output
- #42: ContextWindowExceeded
- #31: K8s sandboxes

### Features in forks worth adopting
- No active forks have IDE-relevant features worth adopting. (548 forks checked)

## Paper/Blog Insights

### Unimplemented techniques
- **Structured output for final answers** — Paper FINAL semantics + Issue #50 + MCP `outputSchema`/`structuredContent`.
- **Memoization of sub-calls** — Issue #82.
- **Cost/runtime guarantees** — DSPy `budget()`, upstream `max_budget`/`BudgetExceededError`. PR #129 fixes budget tracking.

### DSPy RLM integration (updated)
- PR #9295 now open (+2825 lines): multimodal media, budget controls (`budget()`, `max_time`, `max_cost`), multi-model routing (`sub_lms`), LocalInterpreter (unsandboxed exec), depth>1 recursion, GEPA bootstrap_trace resilience.
- 20 new tests, 30 subcall tests, offline (no API keys needed).
- Multi-model routing (`sub_lms`) is not yet in our fork; could be useful for IDE integration where different models serve different purposes.

### Emergent RLM strategies (from blog)
1. Peeking — Small slices for structure observation.
2. Grepping — Regex/keyword narrowing.
3. Partition + Map — Chunk → recursive → aggregate.
4. Summarization — Subset summaries for decisions.
5. Long-input/long-output — Programmatic one-shots.

## Academic/Industry Patterns

### Applicable patterns
1. **DSPy RLM** — `budget()` callable, multimodal media, multi-model routing.

### MCP protocol opportunities
1. **Structured tool output** — `outputSchema`/`structuredContent` for typed results.
2. **MCP Apps** — Interactive UI for RLM progress (RF-062).
3. **Protocol version header** — `MCP-Protocol-Version` required in HTTP.
4. **Elicitation** — Server-initiated user input (now GA in VS Code v1.102).

### VS Code ecosystem changes (NEW)
1. **Copilot Chat open-sourced** (v1.102) — MIT license at `microsoft/vscode-copilot-chat`. Enables studying agent mode implementation.
2. **Custom chat modes** (v1.101–v1.102) — `.chatmode.md` extensibility for tailored AI workflows with specific tools and instructions.
3. **MCP first-class resources** (v1.102) — Profile-specific `mcp.json` replaces settings.json entries.
4. **Pylance MCP tools** (v1.102) — Experimental; shows trend of language servers exposing MCP tools.
5. **MCP server gallery** (v1.102) — `code.visualstudio.com/mcp` curated list with one-click install.

## Cross-Cutting Concerns

### Streaming and progress
- Extension streams iteration progress (RF-029). MCP gateway uses text progress. MCP Apps could replace with interactive UI (RF-062, future).

### Cancellation
- Extension: soft cancellation (RF-012). MCP gateway: cancellation via `Session.cancellation_requested` + `_CancellationError` callback (RF-075, implemented).

### Multi-turn and persistence
- `SupportsPersistence` with `save_state()`/`load_state()`. Multi-turn via `newSession`.

### Security boundaries
- Sandbox tiers in `docs/quality/security_surfaces.md`.
- Bare `except:` in REPL environments — Fixed (RF-087).
- MCP spec 2025-06-18 strengthens OAuth (RFC 8707).

### Batched sub-calls reliability
- DONE: Semaphore queue (cap 16) for batched LM sub-calls (RF-089).

### Budget and cost tracking
- Our RF-090 implements `BudgetExceededError` and `_cumulative_cost`. Upstream PR #129's handler-delta approach ported (RF-094). Subcall cost accumulation verified with 3 new tests.

## Session Log

### Session 2026-07-15

**Sources ingested**: 35+ (upstream repo, 12+ upstream PRs, VS Code v1.99–v1.102 release notes, DSPy #9289/#9295, MCP spec, Cursor docs, GitHub Copilot MCP docs)

**Key new findings**:
- VS Code Copilot Chat open-sourced (v1.102) — MIT license, enables deep agent mode study
- MCP officially GA in VS Code v1.102 — no longer experimental
- MCP servers now first-class resources with dedicated `mcp.json` per profile (v1.102)
- Elicitation support GA in VS Code (v1.102)
- Custom chat modes finalized (v1.101–v1.102) — new extensibility primitive
- Terminal auto-approval (v1.102) — experimental setting for agent workflows
- CLI `code chat` subcommand (v1.102) — script-driven chat integration
- DSPy RLM PR #9295 now open with +2825 lines
- Upstream PR #129 budget tracking fix (alternative to our RF-090 approach)
- Upstream PR #127 Claude 4.6 hallucinated FINAL() fix

**New RF items**: RF-091 through RF-097

**Convergence check**: All RF-001 through RF-090 remain verified. Only RF-062 carried over from prior session. 6 new items added. Pipeline is converging — most research items implemented.

**No source code changes** — research-only session.

### Session 2026-07-15 (Implementation)

**Items implemented**: RF-091, RF-092, RF-093, RF-094, RF-096, RF-097

**Code changes**:
- `rlm/utils/parsing.py`: `find_final_answer()` skips text-based FINAL() when code blocks present (RF-096)
- `rlm/environments/base_env.py`: Added `"FINAL"` to `RESERVED_TOOL_NAMES` (RF-097)
- `rlm/clients/anthropic.py`: Added `_ANTHROPIC_PRICING` table and `get_estimated_cost()` (RF-093)
- `.vscode/rlm-agent.chatmode.md`: Custom chat mode for RLM Agent (RF-091)
- `.vscode/mcp.json`: Verified v1.102-compatible, no changes needed (RF-092)

**Tests added**: 12 new tests across 4 files
- `tests/test_parsing.py`: 6 tests (hallucination guard, FINAL overwrite protection)
- `tests/test_budget_and_limits.py`: 3 tests (subcall cost accumulation)
- `tests/clients/test_anthropic_prompt_cache.py`: 2 tests (cache-aware cost estimation)
- `tests/test_recursive_subcalls.py`: 1 test fixed (regression from RF-096)

**Verification**: `make check` 485 passed, `make ext-check` 15 passed

**Items remaining**: RF-062 (P4, MCP Apps), RF-095 (P4, needs user approval)

**Convergence**: Only P4 items remain. Pipeline converged for P2/P3.
