# Example prompts (MCP workflow)

Example prompts you can use in IDE chat so the agent follows the correct MCP workflow: session → roots → list → handle → span read (and search if needed).

---

## Analyze the RLM core loop

**Prompt:** “Analyze the RLM core loop. How does the main completion loop work in `rlm/core/rlm.py`?”

**Expected workflow:** Use `rlm.session.create` → `rlm.roots.set(session_id, roots=["rlm/core"])` → `rlm.fs.list` → `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")` → `rlm.span.read(session_id, handle_id, start_line=1, end_line=200)` (and further spans or search as needed).

---

## Find all call sites of llm_query

**Prompt:** “Find all call sites of `llm_query` in the codebase.”

**Expected workflow:** Session → roots.set (e.g. `roots=["rlm"]`) → `rlm.search.query(session_id, query="llm_query", scope="rlm", k=10)` to get references → then `rlm.fs.handle.create` and `rlm.span.read` for each relevant file/range.

---

## Summarize rlm/core/types.py

**Prompt:** “Summarize the main types and data structures in `rlm/core/types.py`.”

**Expected workflow:** Session → roots.set → `rlm.fs.handle.create(session_id, "rlm/core/types.py")` → `rlm.span.read` for bounded ranges (e.g. 1–200, 201–400) until the agent has enough to summarize.

---

## What does the MCP gateway expose?

**Prompt:** “What RLM MCP tools are available and when should I use span.read vs chunk.get vs search.query?”

**Expected workflow:** The agent can answer from tool list; ideally it uses session → roots → list to confirm structure, and may use [Quick reference](../reference/quick-reference.md) (Tool selection) if available in the workspace.

---

## General rule

For any prompt that touches the repository: **use session → roots → list → handle → span read (and search if needed).** Do not read files directly; all access goes through MCP tools with bounded reads (max 200 lines / 8KB per span).
