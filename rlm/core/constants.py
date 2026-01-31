"""Core RLM constants (shared by lm_handler, iteration, etc.)."""

# Sub-call prompt bound to avoid ContextWindowExceededError (upstream #42).
# Sub-LM calls (REPL llm_query, AgentRLM, RLM iterations) should keep prompts under this.
# Gateway uses the same value in rlm/mcp_gateway/constants.py for documentation.
MAX_SUB_CALL_PROMPT_CHARS = 100_000  # ~25k tokens; adjust per model context
