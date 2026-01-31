# Agents & contributors

Guidelines for contributing to the RLM library and for developing LM clients, environments, and AI agent integrations.

---

## Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init && uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .

# Optional
uv pip install -e ".[modal]"
uv pip install -e ".[prime]"
```

---

## Code style and typing

- **Formatting:** Ruff. All PRs must pass `ruff check --fix .` and `ruff format .`.
- **Typing:** Prefer explicit types. `cast(...)` and `assert` for narrowing are OK; avoid `# type: ignore` without justification.
- **Naming:** snake_case (methods, variables), PascalCase (classes), UPPER_CASE (constants). Do not use `_` prefix for private methods unless requested.
- **Errors:** Fail fast and loud; no silent fallbacks. Minimize branching.

---

## Core development

```bash
git clone https://github.com/alexzhang13/rlm.git
cd rlm
uv sync
uv sync --group dev --group test
uv run pre-commit install
```

Before a PR:

```bash
uv run ruff check --fix .
uv run ruff format .
uv run pre-commit run --all-files
uv run pytest
```

- Avoid new core deps; use optional extras when possible.
- Write deterministic unit tests; mock external services.
- Keep docs concise; update README when behavior changes.
- Prefer small, focused diffs; delete dead code.

---

## Developing LM clients

Clients live in `rlm/clients/` and must inherit from `BaseLM`.

- Implement: `completion`, `acompletion`, `get_usage_summary`, `get_last_usage`.
- Track per-model usage (calls, input/output tokens).
- Support both string and message-list prompts.
- Register in `rlm/clients/__init__.py`.
- Use env vars only for API keys; hardcode defaults; essential options via `__init__()`.

---

## Developing environments

Environments live in `rlm/environments/`. Choose the right base class:

| Pattern | Base class | Use case |
|--------|------------|----------|
| Non-isolated | `NonIsolatedEnv` | Local, same machine |
| Isolated | `IsolatedEnv` | Cloud (Modal, Prime) |
| AI Agent | `AgentEnvironment` | Conversational AI with tools |

- Implement: `setup`, `load_context`, `execute_code`, `cleanup`.
- Return `REPLResult` from `execute_code`.
- Provide `llm_query` and `llm_query_batched` in globals; handle `lm_handler_address`.
- Globals for executed code: `context`, `llm_query`, `llm_query_batched`, `FINAL_VAR(variable_name)`.

---

## AI agent integrations

Use **AgentRLM** for conversational AI. The **default and recommended** path is `create_enforced_agent`; it guarantees correct configuration (environment=agent, enable_tools, enable_streaming). Direct LLM calls for agent chats are not allowed.

**Recommended (default path):**

```python
from rlm import create_enforced_agent

agent = create_enforced_agent(
    backend="openai",
    backend_kwargs={"model_name": "gpt-4"},
)
agent.register_tool("web_search", search_fn)
agent.add_context("user_profile", user_data)
# Chat: stream=True is required for agent chats
async for chunk in agent.chat(user_message, stream=True):
    print(chunk, end="")
```

**Manual (advanced):** Use `AgentRLM(...)` directly only if you need full control. You must set `environment="agent"`, `enable_tools=True`, and `enable_streaming=True`; enforcement will reject invalid configs.

```python
from rlm import AgentRLM

agent = AgentRLM(
    backend="openai",
    environment="agent",  # required
    enable_tools=True,
    enable_streaming=True,
)
```

**Streaming:** `stream=True` is required for agent chats. Enforcement rejects `agent.chat(..., stream=False)`.

**Registering MCP tools as agent tools:** You can register MCP tool functions (e.g. `rlm_span_read` wrapping the MCP span read) with `agent.register_tool("rlm_span_read", rlm_span_read)` so a single agent uses both RLM and MCP in one flow. The agent then calls your wrapper, which can invoke the MCP gateway or use the RLM client. See [Quick reference](quick-reference.md) for the MCP tool list.

**Context persistence:** `save_context` / `load_context` are subject to session and output limits (e.g. MAX_SESSION_OUTPUT_BYTES 10MB per session). Long conversations may need to be split or summarized; see [Limits and budgets](quick-reference.md#limits-and-budgets).

Agent environment features: `call_tool`, `get_agent_context`, `analyze_text`, `reason_step_by_step`, `evaluate_options`, `make_decision`, streaming, context save/load.

**Trajectory and visualizer:** When using AgentRLM or RLM completion in-process, you can use **RLMLogger** to record trajectory `.jsonl` and inspect it with the **visualizer** (Next.js app in `visualizer/`). Useful for debugging long-context reasoning and sub-call behavior.

---

## Architecture: environment ↔ LM handler

**Non-isolated (e.g. LocalREPL):** TCP socket to `LMHandler`; length-prefixed JSON. Flow: `llm_query(prompt)` → `send_lm_request(address, request)` → TCP → `LMHandler` → `LMResponse`.

**Isolated (Modal/Prime):** HTTP broker inside sandbox. Code in sandbox POSTs to `/enqueue`; host polls `/pending`, forwards to `LMHandler` via socket, POSTs response to `/respond`. Broker endpoints: `/enqueue`, `/pending`, `/respond`, `/health`.

See `rlm/core/lm_handler.py`, `rlm/core/comms_utils.py`, and `rlm/environments/modal_repl.py` for reference.
