# FINAL / FINAL_VAR format (REPL)

How RLM extracts the final answer from model output in the REPL loop.

---

## Overview

In RLM, the model writes code that runs in a REPL. The final answer is signaled with either:

- **`FINAL(...)`** — literal content (string, number, expression) as the answer.
- **`FINAL_VAR(variable_name)`** — name of a REPL variable whose value is the answer.

The RLM core uses **balanced-parenthesis parsing** (not regex-only) to extract the content inside the parentheses, so nested parentheses (e.g. `FINAL("a (b) c")`) are handled correctly.

---

## Format rules

1. **Start of line:** `FINAL(` or `FINAL_VAR(` must appear at the start of a line (optional leading whitespace). Inline `FINAL(42)` in the middle of a sentence is not recognized.

2. **Balanced parentheses:** Content is extracted by matching the opening `(` with its closing `)`. Nested parens are supported (e.g. `FINAL(answer (with (nested)) parens)`).

3. **Precedence:** If both appear, `FINAL_VAR` is checked first. If `FINAL_VAR` is found but no environment is provided to resolve the variable, the result is `None` (no fallback to `FINAL`).

4. **FINAL_VAR:** Requires an environment. The runtime executes code to read the variable value (e.g. `print(FINAL_VAR('result'))`) and uses stdout as the final answer.

---

## Examples

| Output snippet | Extracted answer |
|----------------|------------------|
| `FINAL(42)` | `42` |
| `FINAL("hello")` | `"hello"` (including quotes in content) |
| `FINAL(answer (with nested) parens)` | `answer (with nested) parens` |
| `FINAL_VAR(result)` + env with `result = "ok"` | `ok` |

---

## Implementation

- **Parsing:** `rlm.utils.parsing.find_final_answer()` and `_extract_balanced_paren_content()`.
- **Usage:** `rlm.core.iteration` uses `find_final_answer(iteration.response, environment=environment)` to detect completion.

When upstream PR [#41](https://github.com/alexzhang13/rlm/pull/41) (FINAL/FINAL_VAR docs) merges, system-prompt wording may be aligned with that repo; extraction semantics in rlm-kit remain balanced-paren based.
