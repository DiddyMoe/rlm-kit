# Reproducing paper benchmarks

How (or if) rlm-kit can run the benchmarks from the RLM paper ([arXiv 2512.24601](https://arxiv.org/abs/2512.24601)) and the upstream repository.

---

## Paper benchmarks

The paper evaluates RLMs on:

- **CodeQA (LongBench-v2):** Code repository understanding, multi-choice.
- **BrowseComp-Plus (1K):** Multi-hop QA over 1K documents.
- **OOLONG (trec_coarse):** Long reasoning; transform chunks semantically, aggregate.
- **OOLONG-Pairs:** Pairs of chunks; quadratic complexity.
- **S-NIAH:** Single needle-in-haystack (RULER-style).

See the [paper](https://arxiv.org/abs/2512.24601) and [upstream RLM repo](https://github.com/alexzhang13/rlm) for dataset and evaluation details.

---

## Using rlm-kit

- **Core RLM loop:** rlm-kit uses the same core (`rlm/core/rlm.py`, iteration, LM handler) as upstream. You can run RLM completion with local, Docker, Modal, or Prime environments via `RLM(..., environment="local"|"docker"|"modal"|"prime").completion(prompt)`.
- **Agent environment:** rlm-kit adds `environment="agent"` for AgentRLM; this is for conversational AI with tools, not for reproducing paper benchmarks. For benchmarks, use `environment="local"` or `environment="docker"` (or isolated envs if needed).
- **Datasets and scripts:** Upstream may provide benchmark scripts and dataset loaders; check [alexzhang13/rlm](https://github.com/alexzhang13/rlm) (e.g. `examples/`, `docs/`). rlm-kit does not ship benchmark runner scripts by default; you can copy or adapt them from upstream and run with rlm-kit’s clients and environments.
- **Prompts:** For in-process RLM completion, reuse or adapt upstream REPL system prompts (see [alexzhang13/rlm](https://github.com/alexzhang13/rlm)); ensure `rlm.complete` and tool descriptions match RLM semantics. When upstream merges FINAL/FINAL_VAR or batching docs (#41, etc.), pull those into rlm-kit.
- **Differences:** rlm-kit adds MCP gateway, AgentRLM, enforcement, and sandbox constants; these do not change the core RLM completion semantics. Any divergence in prompts or iteration logic should be documented; when upstream merges changes (e.g. FINAL docs, streaming), pull those into rlm-kit.

---

## Quick check

```bash
# Install and run a single RLM completion (quickstart)
make quickstart   # needs OPENAI_API_KEY
```

For full benchmark reproduction, follow upstream’s documentation and use rlm-kit’s `RLM` and environments as the inference backend.
