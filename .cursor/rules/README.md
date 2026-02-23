# Project rules and reusable prompts

Put project-specific prompts and rules here so Cursor applies them consistently.

## Current active rules

- `rlm-architecture.mdc` — architecture and coding conventions
- `mcp-tool-use.mdc` — MCP-first tool usage guidance

## Skill packages

- `.cursor/skills/rlm-mcp-workflow/` — Cursor Agent Skill for MCP-first bounded retrieval and recursive RLM completion flow.

Legacy `.cursorrules` has been migrated to these rule files.

## File format

- **`.mdc`** or **`.md`** — Cursor picks these up as rules.
- Add YAML frontmatter to control when a rule applies:

```yaml
---
description: Short description (shown in rule picker)
globs: "**/*.py"      # Optional: only when matching files are open
alwaysApply: false    # Set true to apply in every conversation
---

# Your rule or prompt content...
```

## Examples

- `rlm-patterns.mdc` — RLM-specific patterns (REPL, types, MCP).
- `code-style.mdc` — Formatting, naming, error handling.
- `prompts.mdc` — Reusable prompt templates you want the agent to follow.

Create as many rule files as you need; Cursor merges them based on `globs` and `alwaysApply`.
