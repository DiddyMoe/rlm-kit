# Overview

Recursive Language Models (RLMs) replace the canonical `llm.completion(prompt, model)` call with `rlm.completion(prompt, model)`. The context is offloaded into a REPL environment that the LM can interact with and use to launch sub-LM calls.

This repository is an extensible inference engine for RLMs around standard API-based and local LLMs. The idea was introduced in a [blog post](https://alexzhang13.github.io/blog/2025/rlm/) and expanded in the [arXiv preprint](https://arxiv.org/abs/2512.24601).

---

## Core concepts

- **REPL environment:** The input context is a variable in a REPL. The LM can run code, inspect data, and call sub-LMs via `llm_query()` / `llm_query_batched()`.
- **Recursive calls:** Sub-LM calls run inside the REPL; the host RLM orchestrates and uses their results.
- **Completion:** The LM signals the final answer with `FINAL(...)`.

---

## REPL environments

| Environment | Description |
|-------------|-------------|
| **Local** (default) | Same machine, same process; sandboxed builtins. |
| **Docker** | Containerized execution for stronger isolation. |
| **Modal** | Cloud sandboxes (full isolation). |
| **Prime** | Prime Intellect sandboxes (beta). |
| **Agent** | For AI assistants: tools, conversation memory, streaming. |

Example:

```python
from rlm import RLM

rlm = RLM(
    backend="openai",
    backend_kwargs={"model_name": "gpt-5-nano"},
    environment="local",  # or "docker", "modal", "prime"
)
print(rlm.completion("Print the first 100 powers of two, each on a newline.").response)
```

---

## AI agent integration

For conversational AI (Cursor, Copilot, etc.), use **AgentRLM** with the agent environment:

```python
from rlm import create_enforced_agent

agent = create_enforced_agent(
    backend="openai",
    backend_kwargs={"model_name": "gpt-4"},
)
agent.register_tool("search_web", lambda q: f"Searching for {q}...")
agent.add_context("user_info", {"name": "Alex"})

async for chunk in agent.chat("Analyze this document", stream=True):
    print(chunk, end="")
```

AI agents **must** use the RLM architecture (AgentRLM, agent environment, tools, streaming). See [Agents & contributors](../reference/agents.md) and [IDE setup](../guides/ide-setup.md).

---

## Built-in AI chat (MCP gateway)

The project includes an **RLM MCP Gateway** so IDE AI agents interact with the repo only through bounded MCP tools:

- **Bounded reading:** Max 200 lines / 8KB per span.
- **Handle-based access:** No raw file paths in responses.
- **Provenance:** Audit trail for operations.
- **Remote isolation:** Gateway can run on a separate host (thin workspace, no source on the IDE host).

See [MCP gateway quick start](../guides/mcp-gateway-quick-start.md) and [Remote isolation](../guides/remote-isolation.md).

---

## Model providers

Supported backends include OpenAI, Anthropic, OpenRouter, Portkey, LiteLLM, and local vLLM. See `rlm/clients/` and [API: RLM class](../reference/api/rlm.md) for configuration.

---

## Debugging: trajectory visualizer

Use **RLMLogger** to save trajectories and inspect them in the visualizer:

```python
from rlm.logger import RLMLogger
from rlm import RLM

logger = RLMLogger(log_dir="./logs")
rlm = RLM(..., logger=logger)
```

Then run the visualizer:

```bash
cd visualizer && npm run dev  # default: localhost:3001
```

---

## Citation

```bibtex
@misc{zhang2025recursivelanguagemodels,
  title={Recursive Language Models},
  author={Alex L. Zhang and Tim Kraska and Omar Khattab},
  year={2025},
  eprint={2512.24601},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2512.24601},
}
```
