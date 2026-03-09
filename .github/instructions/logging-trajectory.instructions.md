```instructions
# Logging & Trajectory System

## Overview

RLM has a two-part logging system in `rlm/logger/`:
- **`RLMLogger`** — JSONL trajectory logger for structured iteration data
- **`VerbosePrinter`** — Rich console printer for human-readable debug output

Both are instantiated by `RLM.__init__()` and called automatically during the iteration loop.

## RLMLogger

### File: `rlm/logger/rlm_logger.py`

Writes `RLMIteration` data to JSON-lines files. Also maintains an in-memory store for `get_trajectory()`.

### Modes

| Mode | `log_dir` | Disk Output | In-Memory |
|------|-----------|-------------|-----------|
| **Disk + memory** | `"/path/to/logs"` | JSONL files | Yes |
| **In-memory only** | `None` | None | Yes |

### File Naming

```
{file_name}_{timestamp}_{run_id}.jsonl
# Example: rlm_2025-03-02_14-30-00_a1b2c3d4.jsonl
```

### File Rotation

Optional `max_file_bytes` triggers rotation to a new JSONL file when the current file would exceed the size limit. Each rotated file is self-contained with its own metadata line first.

### JSONL Schema

Each file contains two types of lines:

**Line 1 — Metadata** (`type: "metadata"`):
```json
{
  "type": "metadata",
  "timestamp": "2025-03-02T14:30:00",
  "root_model": "gpt-4o",
  "max_depth": 1,
  "max_iterations": 30,
  "backend": "openai",
  "backend_kwargs": {},
  "environment_type": "local",
  "environment_kwargs": {},
  "max_root_tokens": null,
  "max_sub_tokens": null,
  "on_root_chunk": false,
  "enable_prefix_cache": false,
  "other_backends": null,
  "run_id": "a1b2c3d4"
}
```

**Lines 2..N — Iterations** (`type: "iteration"`):
```json
{
  "type": "iteration",
  "iteration": 1,
  "timestamp": "2025-03-02T14:30:05",
  "prompt": "...",
  "response": "...",
  "code_blocks": [
    {
      "code": "print(42)",
      "result": {
        "stdout": "42\n",
        "stderr": "",
        "execution_time": 0.001,
        "rlm_calls": []
      }
    }
  ],
  "iteration_time": 2.5,
  "final_answer": null
}
```

### Key API

```python
logger = RLMLogger(log_dir="/path/to/logs", max_file_bytes=10_000_000)
logger.log_metadata(metadata)             # Write metadata line (once)
logger.log(iteration)                     # Write iteration line
logger.get_trajectory()                   # → {"run_metadata": {...}, "iterations": [...]}
logger.clear_iterations()                 # Reset in-memory store for new completion
logger.iteration_count                    # Current iteration count
```

### Trajectory Data Flow

```
RLMLogger.log_metadata() → first line of JSONL
    ↓
RLMLogger.log() × N iterations → iteration lines in JSONL + in-memory list
    ↓
RLMLogger.get_trajectory() → {"run_metadata": ..., "iterations": [...]}
    ↓
RLMChatCompletion.metadata  → attached to completion result
```

`clear_iterations()` is called at the start of each `RLM.completion()` to reset the in-memory store while preserving metadata.

## VerbosePrinter

### File: `rlm/logger/verbose.py`

Rich console printer using a **Tokyo Night** color theme. All methods are no-ops when `enabled=False`.

### Color Theme

| Name | Hex | Usage |
|------|-----|-------|
| `primary` | `#7AA2F7` | Headers, titles |
| `secondary` | `#BB9AF7` | Emphasis |
| `success` | `#9ECE6A` | Code, success states |
| `warning` | `#E0AF68` | Warnings |
| `error` | `#F7768E` | Errors |
| `text` | `#A9B1D6` | Regular text |
| `muted` | `#565F89` | Less important info |
| `accent` | `#7DCFFF` | Accents |
| `bg_subtle` | `#1A1B26` | Dark background |
| `border` | `#3B4261` | Borders, rules |
| `code_bg` | `#24283B` | Code background |

### Methods

| Method | When Called |
|--------|-----------|
| `print_header()` | Start of RLM session — shows backend, model, environment, limits |
| `print_metadata()` | Wrapper around `print_header()` using `RLMMetadata` |
| `print_iteration_start()` | Before each iteration |
| `print_completion()` | After LLM response received |
| `print_code_execution()` | After code block execution — shows code, output, errors |
| `print_subcall()` | When a sub-LLM call is made |
| `print_compaction_status()` | Token usage vs. compaction threshold |
| `print_compaction()` | When compaction triggers |
| `print_iteration()` | Full iteration summary (calls code_execution, subcall, etc.) |
| `print_final_answer()` | When FINAL answer is found |
| `print_summary()` | End of completion — shows total iterations, time, usage |

### Pattern

```python
# VerbosePrinter is always safe to call — no conditional checks needed at call sites
self.verbose = VerbosePrinter(enabled=config.verbose)
self.verbose.print_iteration(iteration, iteration_number)  # no-op if disabled
```

## Integration with RLM

```python
config = RLMConfig(
    verbose=True,                              # Enable VerbosePrinter
    logger=RLMLogger(log_dir="./logs"),         # Enable JSONL logging
)
rlm = RLM(config)
result = rlm.completion("Analyze this data")
trajectory = result.metadata                    # JSONL trajectory dict
```

```
```
