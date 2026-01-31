# RLM documentation

This folder contains the RLM project documentation.

---

## Documentation layout

- **Next.js doc site** — `src/` (app, pages, components). Run with `npm run dev` from this directory.
- **Markdown content** — `content/` (refactored, organized docs in plain Markdown).

---

## Content index (`content/`)

All refactored docs live under **`content/`** and follow a standard structure:

| Section | Path | Description |
|--------|------|--------------|
| **Index** | [content/index.md](content/index.md) | Documentation index and quick links |
| **Getting started** | [content/getting-started/](content/getting-started/) | Overview, installation, quick start |
| **Guides** | [content/guides/](content/guides/) | IDE setup, MCP gateway, remote isolation, thin workspace, Docker |
| **Reference** | [content/reference/](content/reference/) | Quick reference, agents/contributors, API (RLM class) |
| **Usage** | [content/usage/](content/usage/) | Example scenarios (MCP gateway) |
| **Contributing** | [content/contributing/](content/contributing/) | Contributing guide |

---

## Quick links

- **New users:** [content/getting-started/quick-start.md](content/getting-started/quick-start.md), [content/getting-started/overview.md](content/getting-started/overview.md)
- **IDE + MCP:** [content/guides/ide-setup.md](content/guides/ide-setup.md), [content/guides/mcp-gateway-quick-start.md](content/guides/mcp-gateway-quick-start.md)
- **Production:** [content/guides/remote-isolation.md](content/guides/remote-isolation.md), [content/getting-started/installation.md](content/getting-started/installation.md)
- **Contributors:** [content/reference/agents.md](content/reference/agents.md), [content/contributing/contributing.md](content/contributing/contributing.md)

---

## Conventions

- **Paths:** Use relative links between docs (e.g. `[Quick start](getting-started/quick-start.md)` from within `content/`).
- **Naming:** Lowercase with hyphens (e.g. `quick-start.md`, `remote-isolation.md`).
- **Structure:** Diátaxis-style — getting started, guides, reference, usage, contributing.
- **Single source:** Content in `content/` is canonical; root-level `.md` files (e.g. README, QUICK_START) can link here for the full doc set.
