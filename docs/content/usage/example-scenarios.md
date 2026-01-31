# Example scenarios (MCP gateway)

Real-world patterns for using the RLM MCP Gateway in IDE AI chats.

---

## Scenario 1: Codebase structure

**User:** “What is the structure of the RLM core implementation?”

**Agent (via MCP):**

1. `rlm.session.create()` → get `session_id`
2. `rlm.roots.set(session_id, roots=["rlm/core"])`
3. `rlm.fs.list(session_id, root="rlm/core", depth=2)` — metadata only
4. `rlm.fs.manifest(session_id, root="rlm/core")` — hashes/sizes only
5. Reason over metadata and describe structure

**Result:** Structure analysis using only metadata; no full file reads.

---

## Scenario 2: Find code patterns

**User:** “Find all classes that inherit from BaseLM”

**Agent (via MCP):**

1. Create session and set roots to `rlm`
2. `rlm.search.regex(session_id, pattern="class.*BaseLM", scope="rlm", k=10)` — references only
3. For each result: `rlm.fs.handle.create` → `rlm.span.read` with bounded span (e.g. ±5–10 lines)
4. Summarize findings with references

**Result:** All matching classes via search + bounded span reads.

---

## Scenario 3: Analyze a specific file/method

**User:** “Analyze the RLM completion method implementation”

**Agent (via MCP):**

1. Session + roots `rlm/core`
2. `rlm.search.query(session_id, query="def completion", scope="rlm/core", k=5)`
3. `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")`
4. `rlm.span.read(session_id, handle, start_line, end_line)` — bounded (e.g. 200 lines max)
5. If method continues, read next span(s)
6. Analyze and answer

**Result:** Method analysis using multiple bounded spans, never the whole file.

---

## Scenario 4: Dependencies

**User:** “What are the dependencies of the RLM core module?”

**Agent (via MCP):**

1. Session + roots `rlm/core`
2. `rlm.search.regex(session_id, pattern="^(import|from)", scope="rlm/core", k=50)`
3. Group by file; for each file read import section (e.g. first 50 lines) via `rlm.span.read`
4. Build dependency overview

**Result:** Dependency view from bounded span reads only.

---

## Scenario 5: Code review / security

**User:** “Review the changes in this file for security issues”

**Agent (via MCP):**

1. Session + roots `rlm`
2. Search for patterns: `eval(`, `exec(`, `subprocess.`, `os.system`, write-mode `open`, etc.
3. For each hit: create handle, read bounded span (e.g. ±10 lines)
4. Summarize security findings

**Result:** Security review using bounded spans only.

---

## Scenario 6: Large file (chunking)

**User:** “Analyze the entire RLM core implementation”

**Agent (via MCP):**

1. Session with higher `max_tool_calls`; roots `rlm/core`
2. `rlm.fs.handle.create(session_id, "rlm/core/rlm.py")`
3. `rlm.chunk.create(session_id, handle, chunk_size=100, budget=20)`
4. For each `chunk_id`: `rlm.chunk.get(session_id, chunk_id)` and analyze
5. Synthesize analysis across chunks

**Result:** Full-file analysis via chunks, never loading the whole file.

---

## Scenario 7: Multi-file cross-reference

**User:** “How does AgentRLM use the RLM core?”

**Agent (via MCP):**

1. Session + roots `rlm`
2. Search for AgentRLM and for RLM core usage (e.g. `from rlm.core`, `import.*RLM`)
3. Create handles for relevant files; read bounded spans from each
4. Reason over spans and explain the relationship

**Result:** Cross-file analysis using bounded spans from multiple files.

---

## Common patterns

### Search → read

```text
rlm.search.regex / rlm.search.query → get references
→ rlm.fs.handle.create(session_id, file_path)
→ rlm.span.read(session_id, handle, start_line, end_line)
```

### List → handle → read

```text
rlm.fs.list(session_id, root, depth)
→ rlm.fs.handle.create(session_id, file_path)
→ rlm.span.read(session_id, handle, start_line, end_line)
```

### Chunking for large files

```text
rlm.fs.handle.create → rlm.chunk.create(session_id, handle, chunk_size, budget)
→ for chunk_id: rlm.chunk.get(session_id, chunk_id)
```

---

## Best practices

- Always create a session and set roots before operations.
- Use handles for reading; do not pass raw paths in content.
- Respect bounds: max 200 lines / 8KB per span; use chunking for large files.
- Search first (references only), then read bounded spans.
- Use `rlm.fs.list` and `rlm.fs.manifest` for structure, not content.
- Call `rlm.provenance.report(session_id)` when you need an audit trail.

See also: [IDE setup](../guides/ide-setup.md) and [Quick reference](../reference/quick-reference.md).
