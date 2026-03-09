# Python Code Conventions

## Setup

- Python >= 3.11 required
- Package manager: `uv` (not pip)
- Install: `uv sync` or `uv pip install -e .`
- Dev deps: `uv sync --group dev --group test`

## Formatting and Linting

- **Formatter/linter**: ruff (line-length=100, target Python 3.11)
- **Rules**: E, W, F, I, B, UP (pycodestyle, pyflakes, isort, flake8-bugbear, pyupgrade)
- **Ignored**: E501 (line length handled by formatter)
- **Quote style**: double quotes
- **Type checker**: `ty` (not mypy or pyright)
- **Pre-commit**: ruff + ruff-format + ty hooks

```bash
make lint         # ruff check
make format       # ruff format
make test         # pytest
make typecheck    # ty check --exit-zero --output-format=concise
make check        # lint + format + test
```

## Typing

- Explicit type annotations on ALL function parameters and return types
- Use `X | Y` union syntax (Python 3.11+) — never `Union[X, Y]` or `Optional[X]`
- `cast()` and `assert isinstance()` for type narrowing — OK
- `# type: ignore` — NOT OK without documented justification
- No `Any` without documented justification
- `from __future__ import annotations` only if needed for forward references
- `TYPE_CHECKING` guards for circular imports (see `rlm/utils/parsing.py` for example)

## Naming

- **Methods/functions/variables**: `snake_case`
- **Classes**: `PascalCase` (e.g., `LocalREPL`, `PortkeyClient`, `RLMChatCompletion`)
- **Constants**: `UPPER_CASE` (e.g., `_SAFE_BUILTINS`, `RLM_SYSTEM_PROMPT`, `MAX_SUB_CALL_PROMPT_CHARS`)
- Do NOT use `_` prefix for private methods unless explicitly requested

## Error Handling

- **Fail fast, fail loud** — no defensive programming or silent fallbacks
- **Minimize branching** — prefer single code paths; every `if`/`try` needs justification
- Missing API key → immediate `ValueError`, not graceful fallback
- No bare `except:` — always specify exception types
- No silent exception swallowing — catch blocks must handle or re-raise
- Prefer early returns / guard clauses over nested if/else

## Complexity Constraints

- Maximum 3 levels of nesting inside any function body
- Maximum cyclomatic complexity 8 per function (verify with `uv run radon cc {file} -s -n B`)
- Maximum 50 lines per function (excluding docstring)
- Maximum 5 parameters per function (use dataclass/TypedDict for more)
- Extract helper functions to flatten deep nesting

## Dataclass Pattern

All data types use `@dataclass` with manual `to_dict()` and `from_dict()` — no Pydantic, no dataclasses-json.

```python
from dataclasses import dataclass

@dataclass
class MyType:
    field_a: str
    field_b: int
    field_c: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"field_a": self.field_a, "field_b": self.field_b}
        if self.field_c is not None:
            result["field_c"] = self.field_c
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MyType":
        return cls(
            field_a=str(data["field_a"]),
            field_b=int(data["field_b"]),
            field_c=cast(list[str] | None, data.get("field_c")),
        )
```

Key rules:
- `to_dict()` and `from_dict()` must be inverse operations
- Use `cast()` for typed deserialization in `from_dict`
- Use `field(default_factory=...)` for mutable defaults — never mutable default arguments
- No Pydantic `BaseModel` or `dataclasses_json` anywhere

## Other Patterns

- **Context managers everywhere**: `RLM`, `LMHandler`, `LocalREPL` all support `with` blocks
- **`textwrap.dedent`** for long string constants (see `rlm/utils/prompts.py`)
- **`defaultdict(int)`** for all token/usage tracking
- **`frozenset`** for immutable sets (e.g., `RESERVED_TOOL_NAMES`)
- **`runtime_checkable Protocol`** for duck typing (e.g., `SupportsPersistence`)
- **Factory functions with lazy imports**: `get_client()` and `get_environment()` use `importlib.import_module`
- **`VerbosePrinter`** methods are no-ops when `enabled=False` — no conditional checks at call sites
- **Thread-safe IO**: Use `threading.Lock()` for stdout in multi-threaded contexts

## Dependencies

- Avoid new core dependencies
- Use optional extras for non-essential features (e.g., `[modal]`, `[mcp]`, `[e2b]`, `[daytona]`, `[prime]`)
- Exception: tiny deps that simplify widely-used code

## Scope and Diffs

- Small, focused diffs — one concern per change
- Delete dead code (don't guard it)
- Backward compatibility is only desirable if achievable without excessive maintenance burden
