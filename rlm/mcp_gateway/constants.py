"""Constants and limits for RLM MCP Gateway."""

MAX_SPAN_LINES = 200
MAX_SPAN_BYTES = 8192
MAX_CHUNK_LINES = 200
MAX_CHUNK_BYTES = 8192
MAX_FS_LIST_ITEMS = 1000
MAX_SEARCH_RESULTS = 10
MAX_EXEC_CODE_SIZE = 10240  # 10KB
MAX_EXEC_TIMEOUT_MS = 5000
MAX_EXEC_MEMORY_MB = 256
MAX_SESSION_OUTPUT_BYTES = 10485760  # 10MB per session

# Sub-call prompt bound (mirrors rlm.core.constants.MAX_SUB_CALL_PROMPT_CHARS).
# Sub-LM calls exceeding this log a warning; see quick-reference "Limits and budgets".
MAX_SUB_CALL_PROMPT_CHARS = 100_000  # ~25k tokens
