"""Safe builtins definitions for sandboxed execution.

Two variants:
- get_safe_builtins(): For MCP rlm.exec.run (strict). No globals/locals/__import__/open.
- get_safe_builtins_for_repl(): For REPL environments. Adds globals, locals, __import__, open.
"""

from typing import Any


def get_safe_builtins() -> dict[str, Any]:
    """
    Get safe builtins dictionary for strict sandbox execution.

    Used by MCP rlm.exec.run only. Blocks eval/exec/input/compile and does
    not include globals/locals/__import__/open for maximum security.

    Returns:
        Dictionary of safe builtins for restricted execution
    """
    return {
        # Core types and functions
        "print": print,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "bool": bool,
        "type": type,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "range": range,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "any": any,
        "all": all,
        "pow": pow,
        "divmod": divmod,
        "chr": chr,
        "ord": ord,
        "hex": hex,
        "bin": bin,
        "oct": oct,
        "repr": repr,
        "ascii": ascii,
        "format": format,
        "hash": hash,
        "id": id,
        "iter": iter,
        "next": next,
        "slice": slice,
        "callable": callable,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "delattr": delattr,
        "dir": dir,
        "vars": vars,
        "bytes": bytes,
        "bytearray": bytearray,
        "memoryview": memoryview,
        "complex": complex,
        "object": object,
        "super": super,
        "property": property,
        "staticmethod": staticmethod,
        "classmethod": classmethod,
        # Exceptions
        "BaseException": BaseException,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "FileNotFoundError": FileNotFoundError,
        "OSError": OSError,
        "IOError": IOError,
        "RuntimeError": RuntimeError,
        "NameError": NameError,
        "ImportError": ImportError,
        "StopIteration": StopIteration,
        "AssertionError": AssertionError,
        "NotImplementedError": NotImplementedError,
        "ArithmeticError": ArithmeticError,
        "LookupError": LookupError,
        "Warning": Warning,
        # Blocked (set to None to prevent access)
        "input": None,
        "eval": None,
        "exec": None,
        "compile": None,
        "globals": None,
        "locals": None,
        "__import__": None,
        "open": None,
        "file": None,
    }


def get_safe_builtins_for_repl() -> dict[str, Any]:
    """
    Get safe builtins dictionary for REPL environments.

    Used by LocalREPL, DockerREPL, etc. Includes globals/locals so RLM code
    can inspect the REPL namespace; allows __import__ and open for context
    loading. Do not use for MCP rlm.exec.run (use get_safe_builtins() instead).

    Returns:
        Dictionary of safe builtins for REPL execution
    """
    import builtins as _builtins

    builtins = get_safe_builtins()
    # Override blocked items for REPL
    builtins["__import__"] = _builtins.__import__
    builtins["open"] = _builtins.open
    # Enable globals/locals for REPL functionality
    builtins["globals"] = globals
    builtins["locals"] = locals
    return builtins
