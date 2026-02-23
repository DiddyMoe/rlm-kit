---
description: Research upstream RLM repos, forks, paper, VS Code/Cursor docs and generate findings and backlog artifacts
agent: agent
---

# Research Plan — RLM IDE Integration
**Scope**: Upstream RLM repos, forks, paper, blog, VS Code Copilot Agent Chat, Cursor Agent Chat, MCP protocol, and academic/industry research
**Artifacts**: `docs/orchestrator/research-findings.md`, `docs/orchestrator/research-backlog.md`
**Idempotency**: Re-running this prompt removes implemented items from findings and backlog; unimplemented items are preserved and updated in place

---

## Design Philosophy

Research findings must be **actionable and evidence-based**:

1. **Cite sources** — Every finding must reference a specific URL, commit, document section, or API reference. "This might work" without a source is not a finding.
2. **Scope to IDE integration** — The primary goal is VS Code Copilot Agent Chat and Cursor Agent Chat integration. Upstream features and academic patterns matter only if they serve this goal.
3. **Assess feasibility concretely** — "High impact" means nothing without "because X test fails / Y workflow breaks / Z users need it." Tie impact assessments to observable outcomes.
4. **Converge** — Each research cycle should produce fewer new findings as the project matures. If findings proliferate, the scope is too broad — tighten it.

---

## Instructions

You are a research agent. You must NOT modify any source code — only artifact files under `docs/orchestrator/`. After completing research, you write findings and backlog directly to disk so the research-agent can read and implement them.

### Phase 1 — Source Ingestion

Parse and extract actionable insights from every source below. For each source, record: URL, date accessed, key findings, and relevance to this project's goals.

#### 1.1 Upstream Repositories

- **rlm** (full): https://github.com/alexzhang13/rlm
  - Compare architecture, clients, environments, MCP gateway, extension code against this fork
  - Identify commits/features not yet merged or adapted
  - Note any breaking changes or divergences

- **rlm-minimal**: https://github.com/alexzhang13/rlm-minimal
  - Extract simplified patterns that could reduce complexity in this fork
  - Identify minimal viable integration patterns for IDE chat

#### 1.2 Forks

- **rlm forks**: https://github.com/alexzhang13/rlm/forks
- **rlm-minimal forks**: https://github.com/alexzhang13/rlm-minimal/forks
  - For each active fork (commits ahead of upstream): record fork URL, what was changed, and whether the change is relevant to IDE integration
  - Focus on: new clients, new environments, MCP improvements, extension improvements, bug fixes

#### 1.3 Paper and Blog

- **Paper**: https://arxiv.org/abs/2512.24601v1 — "Recursive Language Models"
  - Extract: architecture design rationale, REPL interaction model, sub-call depth strategy, context decomposition, FINAL/FINAL_VAR semantics
  - Identify any techniques described in the paper but not implemented in this fork

- **Blog**: https://alexzhang13.github.io/blog/2025/rlm/
  - Extract: practical usage patterns, performance insights, design decisions not in the paper

#### 1.4 VS Code Copilot Agent Chat Integration Research

Research the best methods to integrate RLM with VS Code's built-in Copilot AI Agent Chat:

- **VS Code Chat Participant API**: https://code.visualstudio.com/api/extension-guides/chat
  - Current participant registration, command handling, result streaming
  - Agent mode capabilities (tool use, multi-step, follow-ups)
  - `vscode.lm` API for language model access
  - `vscode.chat.createChatParticipant` patterns

- **VS Code Language Model Tools API**: https://code.visualstudio.com/api/extension-guides/language-model-tool-calling
  - Tool registration via `vscode.lm.registerTool`
  - How RLM tools could be exposed as native VS Code LM tools
  - Integration with Copilot's tool-calling flow

- **VS Code MCP Support**: https://code.visualstudio.com/docs/copilot/chat/mcp-servers
  - Native MCP server configuration in VS Code settings
  - How VS Code discovers and invokes MCP tools
  - Whether the extension should register as an MCP server or use the gateway

- **GitHub Copilot Extensions**: https://docs.github.com/en/copilot/building-copilot-extensions
  - Copilot agent architecture and skillsets
  - How RLM could function as a Copilot skillset/agent
  - Authentication and API patterns

- **VS Code Agent Mode (.agent.md)**: Research `.github/copilot-instructions.md` and custom agent patterns
  - How to configure Copilot to understand and use RLM tools
  - Best practices for agent instructions

- Search for: community extensions that integrate custom LLM loops with Copilot Chat, VS Code Insiders features for agent chat, any official roadmap for tool extensibility

#### 1.5 Cursor Agent Chat Integration Research

Research the best methods to integrate RLM with Cursor's built-in AI Agent Chat:

- **Cursor MCP Integration**: How Cursor discovers and uses MCP servers
  - `.cursor/mcp.json` configuration patterns
  - Tool invocation flow in Agent mode vs Plan mode
  - How Cursor handles long-running tool calls (relevant for RLM completion)

- **Cursor Rules**: `.cursorrules` and `.cursor/rules/` patterns
  - How to instruct Cursor's agent to use RLM tools effectively
  - Context injection patterns

- **Cursor Composer/Agent**: Multi-file editing with RLM context
  - How RLM's recursive analysis could feed Cursor's planning
  - Integration with Cursor's built-in code understanding

- Search for: Cursor plugin APIs (if any), community MCP servers that do recursive analysis, Cursor changelog for MCP improvements

#### 1.6 Academic and Industry Research

- **MCP Protocol**: https://modelcontextprotocol.io and https://spec.modelcontextprotocol.io
  - Latest spec changes that affect tool definitions, streaming, cancellation
  - SSE transport vs stdio vs HTTP — which is best for each IDE
  - MCP sampling (server-initiated LLM calls) — could replace socket protocol for isolated envs

- **Recursive/iterative LLM patterns**: Search arxiv for papers on iterative code execution with LLMs, tool-augmented LLMs, self-debugging LLMs, REPL-based agents
  - Keywords: "recursive language model", "iterative refinement LLM", "code execution LLM", "REPL agent", "tool-augmented generation"

- **IDE-LLM integration patterns**: Research how other projects integrate custom LLM loops with IDE chat
  - Continue.dev, Aider, OpenHands, SWE-agent — architecture patterns
  - How they handle: streaming, progress, cancellation, multi-turn

---

### Phase 2 — Analysis and Synthesis

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

### Phase 3 — Artifact Generation

Write both artifact files directly to disk. If previous versions exist, merge: preserve unimplemented items, remove completed items, add new findings.

#### 3.1 Write `docs/orchestrator/research-findings.md`

Write the following structure to disk:

```markdown
# Research Findings
<!-- ORCHESTRATOR ARTIFACT — remove completed items; keep only actionable findings -->
<!-- Last updated: {YYYY-MM-DD HH:MM:SS} -->

## Source Index
<!-- For each source: URL, date accessed, summary of key findings -->

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
```

#### 3.2 Write `docs/orchestrator/research-backlog.md`

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

---

### Constraints

1. **No source code changes** — only write to `docs/orchestrator/research-findings.md` and `docs/orchestrator/research-backlog.md`
2. **Remove completed** — when a finding has been fully implemented, exclude it from the artifacts; do not accumulate stale entries
3. **No duplication** — check existing docs (fix_now.md, bug_backlog.md, proposal_prioritized.md) before adding items; cross-reference instead
4. **Respect existing plan** — do not contradict docs/orchestrator/plan.md; extend it
5. **Evidence required** — every finding must cite a source URL, commit hash, API reference, or document section
6. **Verification**: After writing artifacts, read them back and list line counts and a summary of what was produced

---

### Existing Context to Load First

Before starting research, read these files to avoid duplicate work:
- `docs/orchestrator/plan.md` — existing plan and completed phases
- `docs/orchestrator/state.json` — current state
- `docs/orchestrator/proposal_prioritized.md` — existing proposals
- `docs/research/landscape.md` — existing research landscape
- `docs/research/bibliography.md` — existing bibliography
- `docs/research/recommendations_map.md` — existing recommendations
- `docs/quality/fix_now.md` — existing fix items
- `docs/quality/bug_backlog.md` — existing bugs
- `docs/integration/ide_adapter.md` — existing IDE adapter mapping
- `docs/integration/playbooks.md` — existing IDE playbooks
- `AGENTS.md` — project conventions and architecture
