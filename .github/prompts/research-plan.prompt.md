---
description: Research upstream RLM repos, forks, paper, VS Code/Cursor docs and generate findings and backlog artifacts
agent: agent
---

# Research Plan — RLM IDE Integration
**Scope**: Upstream RLM repos, forks, paper, blog, VS Code Copilot Agent Chat, Cursor Agent Chat, MCP protocol, and academic/industry research
**Artifacts**: `docs/orchestrator/research-findings.md`, `docs/orchestrator/research-backlog.md`
**Idempotency**: Re-running this prompt removes implemented items from findings and backlog; unimplemented items are preserved and updated in place. This prompt is also **resumable**: it must checkpoint artifacts to disk immediately and keep updating them throughout the run.

---

## Design Philosophy

Research findings must be **actionable and evidence-based**:

1. **Cite sources** — Every finding must reference a specific URL, commit, document section, or API reference. "This might work" without a source is not a finding.
2. **Scope to IDE integration** — The primary goal is VS Code Copilot Agent Chat and Cursor Agent Chat integration. Upstream features and academic patterns matter only if they serve this goal.
3. **Assess feasibility concretely** — "High impact" means nothing without "because X test fails / Y workflow breaks / Z users need it." Tie impact assessments to observable outcomes.
4. **Converge** — Each research cycle should produce fewer new findings as the project matures. If findings proliferate, the scope is too broad — tighten it.

---

## Instructions

You are a research agent. You must NOT modify any source code — only artifact files under `docs/orchestrator/`. Do not wait until the end to write artifacts. Create or refresh the artifact files as soon as you have enough context to preserve prior state, then keep merging new findings to disk throughout the run so work survives context pressure.

---

## Persistence-First Execution Mode

The default failure mode for this prompt is losing context before artifacts are written. Avoid that by using this exact execution pattern:

1. **Bootstrap artifacts early** — after the startup checklist and before broad web research, create or refresh `docs/orchestrator/research-findings.md` and `docs/orchestrator/research-backlog.md` with the required skeleton, carried-forward unresolved items, and a partial Source Index.
2. **Use the Source Index as a working ledger** — track each source with a status such as `pending`, `checked`, or `unreachable`, plus date accessed and short notes. This ledger is the durable memory for the run.
3. **Work in small batches** — process at most 1–2 source families or ~8 URLs before writing artifacts again. Do not accumulate the entire research corpus in memory.
4. **Analyze immediately** — after each batch, convert notes into actionable findings/backlog entries right away instead of postponing synthesis until all sources are read.
5. **Re-read your own artifacts** — after each checkpoint write, read the artifacts back before continuing so the next batch starts from disk, not from fragile conversational memory.
6. **Stop safely if needed** — if context pressure, tool limits, or time budget become a risk, stop after the current batch once artifacts are updated. Partial but well-checkpointed output is better than broad but lossy coverage.

When prioritization is necessary, cover source families in this order: **current project state → VS Code integration → Cursor integration → upstream/forks → paper/blog → broader ecosystem**.

---

## Startup Checklist (run every invocation)

Before starting any research, read these files to avoid duplicate work and understand current state:

1. Read `AGENTS.md` — project conventions and architecture
2. Read `docs/orchestrator/plan.md` — existing plan and completed phases
3. Read `docs/orchestrator/state.json` — current state; an item is "completed" if its RF-ID appears in `recommendations.verified`
4. Read `docs/orchestrator/proposal_prioritized.md` — existing proposals
5. Read `docs/research/landscape.md` — existing research landscape
6. Read `docs/research/bibliography.md` — existing bibliography
7. Read `docs/research/recommendations_map.md` — existing recommendations
8. Read `docs/quality/fix_now.md` — existing fix items (do not duplicate)
9. Read `docs/quality/bug_backlog.md` — existing bugs (do not duplicate)
10. Read `docs/integration/ide_adapter.md` — existing IDE adapter mapping
11. Read `docs/integration/playbooks.md` — existing IDE playbooks
12. Read `docs/orchestrator/debug-findings.md` — debug context (if exists; do not duplicate)
13. Read `docs/orchestrator/debug-backlog.md` — do not duplicate debug items (if exists)
14. Read `docs/orchestrator/refactor-findings.md` — refactor context (if exists; do not duplicate)
15. Read `docs/orchestrator/refactor-backlog.md` — do not duplicate refactor items (if exists)
16. Read `docs/orchestrator/research-findings.md` — previous findings (if exists; remove completed items, re-research as needed)
17. Read `docs/orchestrator/research-backlog.md` — previous backlog (if exists; extend, don't replace)

## Tool Usage

- **Web sources**: Fetch each documentation URL, blog post, and spec page listed below. If a source is unreachable, record the failure in the Source Index with date and reason — do not silently skip it.
- **GitHub repos/PRs/issues**: Inspect upstream repositories, pull requests, issues, and fork activity via web fetching or GitHub API access.
- **Codebase comparison**: Read files and search this fork's code to compare against upstream findings.
- **Checkpoint loop**: Prefer this loop throughout the run: `research small batch → merge artifacts to disk → read artifacts back → continue`.

---

## Phase 0 — Bootstrap and First Checkpoint

Before broad source ingestion, do this immediately:

1. Read all startup-checklist files.
2. Determine completed RF-IDs from `docs/orchestrator/state.json`.
3. Load any existing research artifacts and remove completed items.
4. Write both research artifacts to disk right away with:
  - the required section skeletons,
  - preserved unresolved findings/backlog items,
  - a Source Index ledger seeded with known sources marked `pending`,
  - a provisional Session Log entry for the current run.
5. Read the just-written artifacts back before continuing.

This phase is mandatory. Do not defer the first artifact write until after external research.

---

## Phase 1 — Source Ingestion

Parse and extract actionable insights from the sources below **batch by batch**. For each source, record: URL, date accessed, status, key findings, and relevance to this project's goals. After each subsection or small batch, checkpoint the artifacts to disk before moving on.

### 1.1 Upstream Repositories

- **rlm** (full): https://github.com/alexzhang13/rlm
  - Compare architecture, clients, environments, MCP gateway, extension code against this fork
  - Identify commits/features not yet merged or adapted
  - Note any breaking changes or divergences

- **rlm-minimal**: https://github.com/alexzhang13/rlm-minimal
  - Extract simplified patterns that could reduce complexity in this fork
  - Identify minimal viable integration patterns for IDE chat

### 1.2 Forks

- **rlm forks**: https://github.com/alexzhang13/rlm/forks
- **rlm-minimal forks**: https://github.com/alexzhang13/rlm-minimal/forks
  - For each active fork (commits ahead of upstream): record fork URL, what was changed, and whether the change is relevant to IDE integration
  - Focus on: new clients, new environments, MCP improvements, extension improvements, bug fixes

### 1.3 Paper and Blog

- **Paper**: https://arxiv.org/abs/2512.24601 — "Recursive Language Models"
  - Extract: architecture design rationale, REPL interaction model, sub-call depth strategy, context decomposition, FINAL/FINAL_VAR semantics
  - Identify any techniques described in the paper but not implemented in this fork

- **Blog**: https://alexzhang13.github.io/blog/2025/rlm/
  - Extract: practical usage patterns, performance insights, design decisions not in the paper

### 1.4 VS Code Copilot Agent Chat Integration Research

Research the best methods to integrate RLM with VS Code's built-in Copilot AI Agent Chat:

- **VS Code AI Extensibility Overview**: https://code.visualstudio.com/api/extension-guides/ai/ai-extensibility-overview
  - Three integration paths: LM Tools, MCP Tools, Chat Participant
  - Decision matrix for which path to use

- **VS Code Chat Participant API**: https://code.visualstudio.com/api/extension-guides/chat
  - Current participant registration, command handling, result streaming
  - Agent mode capabilities (tool use, multi-step, follow-ups)
  - `vscode.lm` API for language model access
  - `vscode.chat.createChatParticipant` patterns

- **VS Code Language Model Tools API**: https://code.visualstudio.com/api/extension-guides/ai/tools
  - Tool registration via `vscode.lm.registerTool` and `contributes.languageModelTools`
  - `prepareInvocation` and `when` clause patterns
  - How RLM tools could be exposed as native VS Code LM tools
  - Integration with Copilot's tool-calling flow

- **VS Code MCP Developer Guide**: https://code.visualstudio.com/api/extension-guides/ai/mcp
  - Programmatic MCP server registration via `vscode.lm.registerMcpServerDefinitionProvider`
  - MCP Apps (interactive UI in tool responses)
  - MCP Icons, OAuth 2.1, Sampling, Elicitation
  - Development mode (`watch` + `debug` config)
  - MCP installation URLs (`vscode:mcp/install?{json-config}`)

- **VS Code MCP User Docs**: https://code.visualstudio.com/docs/copilot/chat/mcp-servers
  - Native MCP server configuration in VS Code settings
  - `envFile` support, tool sets, `chat.mcp.autoStart`, max 128 tools
  - How VS Code discovers and invokes MCP tools
  - Whether the extension should register as an MCP server or use the gateway

- **GitHub Copilot Extensions**: https://docs.github.com/en/copilot/building-copilot-extensions
  - Copilot agent architecture and skillsets
  - How RLM could function as a Copilot skillset/agent
  - Authentication and API patterns

- **GitHub Copilot MCP**: https://docs.github.com/en/copilot/concepts/context/mcp
  - MCP as primary Copilot extension mechanism
  - GitHub MCP Registry

- **VS Code Agent Mode (.agent.md)**: Research `.github/copilot-instructions.md` and custom agent patterns
  - How to configure Copilot to understand and use RLM tools
  - Best practices for agent instructions

- Search for these specific terms on the VS Code Marketplace and GitHub:
  - Marketplace: `"chat participant" "language model"` — extensions registering custom LM tools
  - GitHub: `vscode.lm.registerTool site:github.com` — repos using the LM Tools API
  - VS Code release notes: search for "agent mode" and "MCP" in https://code.visualstudio.com/updates/

### 1.5 Cursor Agent Chat Integration Research

Research the best methods to integrate RLM with Cursor's built-in AI Agent Chat:

- **Cursor MCP Integration**: https://cursor.com/docs/context/mcp
  - `.cursor/mcp.json` configuration patterns
  - Tool invocation flow in Agent mode vs Plan mode
  - How Cursor handles long-running tool calls (relevant for RLM completion)
  - `envFile` support, config interpolation (`${workspaceFolder}`, `${env:NAME}`)
  - Auto-run for trusted tools

- **Cursor MCP Extension API**: https://cursor.com/docs/context/mcp-extension-api
  - `vscode.cursor.mcp.registerServer()` / `unregisterServer()` for programmatic registration
  - Differences from VS Code's MCP registration API

- **Cursor Rules**: `.cursorrules` and `.cursor/rules/` patterns
  - How to instruct Cursor's agent to use RLM tools effectively
  - Context injection patterns

- **Cursor Composer/Agent**: Multi-file editing with RLM context
  - How RLM's recursive analysis could feed Cursor's planning
  - Integration with Cursor's built-in code understanding

- Search for these specific terms:
  - GitHub: `cursor mcp recursive` — community MCP servers doing recursive analysis
  - Cursor changelog: https://cursor.com/changelog — filter for "MCP" entries
  - Cursor forum: `site:forum.cursor.com MCP tools` — community patterns and issues

### 1.6 Academic and Industry Research

- **MCP Protocol**: https://modelcontextprotocol.io and https://spec.modelcontextprotocol.io
  - Latest spec changes that affect tool definitions, streaming, cancellation
  - SSE transport vs stdio vs HTTP — which is best for each IDE
  - MCP sampling (server-initiated LLM calls) — could replace socket protocol for isolated envs

- **Recursive/iterative LLM patterns**: Search arxiv for papers on iterative code execution with LLMs, tool-augmented LLMs, self-debugging LLMs, REPL-based agents
  - Keywords: "recursive language model", "iterative refinement LLM", "code execution LLM", "REPL agent", "tool-augmented generation"
  - Search query: `https://arxiv.org/search/?query=recursive+language+model+code+execution&searchtype=all`

- **IDE-LLM integration patterns**: Research how other projects integrate custom LLM loops with IDE chat
  - Continue.dev (https://github.com/continuedev/continue) — architecture, MCP usage
  - Aider (https://github.com/Aider-AI/aider) — streaming, multi-turn
  - OpenHands (https://github.com/All-Hands-AI/OpenHands) — sandbox, agent loop
  - SWE-agent (https://github.com/princeton-nlp/SWE-agent) — tool-augmented execution
  - For each: record how they handle streaming, progress, cancellation, multi-turn

### 1.7 Ecosystem Integrations

- **DSPy RLM integration**: https://github.com/stanfordnlp/dspy/issues/9289
  - Multimodal support, budget callable, multi-model routing, LocalInterpreter
  - Patterns applicable to this fork's IDE integration

- Search for downstream projects using RLM:
  - GitHub: `"from rlm" OR "import rlm" language:python` — projects importing rlm
  - GitHub: `alexzhang13/rlm` in requirements.txt / pyproject.toml — dependent projects

---

## Phase 2 — Analysis and Synthesis

Perform this analysis continuously during the run, not only at the end. Each completed batch from Phase 1 should immediately produce updated findings/backlog content.

For each finding from Phase 1, evaluate:

1. **Relevance**: Does it directly improve VS Code Copilot or Cursor integration?
2. **Feasibility**: Can it be implemented without breaking existing functionality? Cite the specific files/APIs affected.
3. **Impact**: High / Medium / Low — with a concrete justification (not just "this seems important")
4. **Effort**: Small (< 1 day) / Medium (1–3 days) / Large (> 3 days)
5. **Dependencies**: What must exist first?
6. **Test strategy**: How would the change be verified? What test would confirm it works?

Categorize findings into:
- **IDE Integration** — VS Code Copilot Agent Chat or Cursor Agent Chat improvements
- **Core Improvements** — RLM loop, clients, environments enhancements from upstream/forks/paper
- **Protocol/Transport** — MCP, socket, streaming improvements
- **Developer Experience** — Testing, docs, tooling improvements
- **Security/Safety** — Sandbox, validation, isolation improvements

---

## Phase 3 — Artifact Generation

Phase 0 creates the first artifact checkpoint. During this phase, keep rewriting the same two artifact files as batches complete. If previous versions exist, merge using this algorithm:

1. **Determine completion**: An item is "completed" if its RF-ID appears in `docs/orchestrator/state.json` under `recommendations.verified`.
2. **Remove completed items**: Delete entries whose RF-IDs are verified in state.json from both findings and backlog.
3. **Preserve unimplemented**: Keep all items not marked as verified — do not discard items just because they are old.
4. **Add new findings**: Append new items with the next sequential RF-ID.

### 3.1 Write `docs/orchestrator/research-findings.md`

Write the following structure to disk:

```markdown
# Research Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Source Index
<!-- For each source: status (pending/checked/unreachable), URL, date accessed, summary of key findings -->

## VS Code Copilot Agent Chat
### Current State (this project)
### Best Available Methods
### Recommended Changes (ranked by impact, with evidence)

## Cursor Agent Chat
### Current State (this project)
### Best Available Methods
### Recommended Changes (ranked by impact, with evidence)

## Upstream Delta
### Features in upstream not in this fork
### Features in forks worth adopting

## Paper/Blog Insights
### Unimplemented techniques
### Design rationale clarifications

## Academic/Industry Patterns
### Applicable patterns from other projects
### MCP protocol opportunities

## Cross-Cutting Concerns
### Streaming and progress
### Cancellation
### Multi-turn and persistence
### Security boundaries

## Limitations
<!-- Document what this research pass cannot find -->
<!-- e.g., runtime behavior, production performance, private API changes, undocumented IDE features -->

## Session Log
<!-- Appended by Phase 4 after each run -->
```

### 3.2 Write `docs/orchestrator/research-backlog.md`

Write the following structure to disk:

```markdown
# Research Backlog
<!-- ORCHESTRATOR ARTIFACT — items are removed when implemented -->
<!-- Consumed by: research-agent.prompt.md -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Priority 1 — Critical for IDE Integration
<!-- Items that directly enable or fix VS Code Copilot / Cursor integration -->

## Priority 2 — High-Impact Improvements
<!-- Significant improvements from upstream, forks, or research -->

## Priority 3 — Medium-Impact Enhancements
<!-- Nice-to-have improvements -->

## Priority 4 — Future Exploration
<!-- Long-term research items -->

## Priority 5 — Low Priority / Nice-to-Have
<!-- Low-priority items that are not blocking anything -->
```

Each backlog item must have:
- **ID**: `RF-{NNN}` (sequential)
- **Title**: Short descriptive title
- **Source**: Where the finding came from (URL or reference)
- **Category**: IDE Integration | Core | Protocol | DX | Security
- **Impact**: High | Medium | Low — with justification
- **Effort**: Small | Medium | Large
- **Description**: What to do and why
- **Files affected**: List of files that would change
- **Test strategy**: How to verify the change works (specific test or verification command)
- **Depends on**: Other RF-IDs or prerequisites

**Item granularity rule**: Each backlog item must represent a single implementable change (completable in one agent session). If a finding requires multiple phases or touches more than 5 files, break it into sub-items with IDs like `RF-070a`, `RF-070b`, `RF-070c`. Each sub-item must independently satisfy its own test strategy.

Partial completion is allowed. If the full source list cannot be covered in one run, keep unfinished sources explicitly marked as `pending` in the findings artifact and leave backlog generation limited to evidence already gathered.

---

## Phase 4 — Session Summary

After writing artifacts, append a session summary block at the bottom of `docs/orchestrator/research-findings.md`:

```markdown
## Session Log

### {YYYY-MM-DD} - {HH:MM:SS}
- **New findings added**: {count}
- **Findings removed (completed)**: {count}
- **Remaining backlog size**: {count} (P1: {n}, P2: {n}, P3: {n}, P4: {n}, P5: {n})
- **Sources checked**: {count} ({unreachable_count} unreachable)
- **Convergence**: {increasing|stable|decreasing} — {one-sentence explanation}
```

This enables tracking convergence across research cycles. If backlog size is growing rather than shrinking, note which category is growing and why.

For long runs with multiple checkpoints, it is acceptable to refresh the current run's session block as totals change. The final checkpoint should leave one accurate summary block for the run.

---

## Constraints

1. **No source code changes** — only write to `docs/orchestrator/research-findings.md` and `docs/orchestrator/research-backlog.md`
2. **Remove completed** — when a finding has been fully implemented, exclude it from the artifacts; do not accumulate stale entries
3. **No duplication** — check existing docs (fix_now.md, bug_backlog.md, proposal_prioritized.md, debug-backlog.md, refactor-backlog.md) before adding items; cross-reference instead
4. **Respect existing plan** — do not contradict docs/orchestrator/plan.md; extend it
5. **Evidence required** — every finding must cite a source URL, commit hash, API reference, or document section
6. **Source unavailability** — if a source URL is unreachable, returns an error, or has moved, record the failure in the Source Index table with the date and reason (e.g., "404", "repo archived", "page restructured"). Do not silently skip sources.
7. **Verification**: After writing artifacts, read them back and list line counts and a summary of what was produced
8. **Checkpoint early and often** — write the first artifact checkpoint before broad research and rewrite artifacts after every small batch
9. **Prefer resumable progress over monolithic completeness** — if one run cannot finish the full source list, leave durable partial artifacts with explicit `pending` markers rather than compressing the whole task into a brittle summary
