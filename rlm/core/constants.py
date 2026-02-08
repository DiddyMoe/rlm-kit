"""Core RLM constants (shared by lm_handler, iteration, etc.)."""

# Sub-call prompt bound to avoid ContextWindowExceededError.
# Sub-LM calls (REPL llm_query, AgentRLM, RLM iterations) should keep prompts under this.
MAX_SUB_CALL_PROMPT_CHARS = 100_000  # ~25k tokens; adjust per model context
