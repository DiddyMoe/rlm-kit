import textwrap

MODAL_EXEC_SCRIPT_TEMPLATE = textwrap.dedent(
    '''
import sys
import io
import json
import base64
import traceback
import os
import requests

try:
    import dill
except ImportError:
    import pickle as dill

# =============================================================================
# LLM Query Functions (via local broker)
# =============================================================================

BROKER_URL = "http://127.0.0.1:__BROKER_PORT__"

def llm_query(prompt, model=None):
    """Query the LM via the broker."""
    try:
        response = requests.post(
            f"{BROKER_URL}/enqueue",
            json={"type": "single", "prompt": prompt, "model": model, "depth": __DEPTH__},
            timeout=300,
        )
        data = response.json()
        if data.get("error"):
            return f"Error: {data['error']}"
        return data.get("response", "Error: No response")
    except Exception as e:
        return f"Error: LM query failed - {e}"


def llm_query_batched(prompts, model=None):
    """Query the LM with multiple prompts."""
    try:
        response = requests.post(
            f"{BROKER_URL}/enqueue",
            json={"type": "batched", "prompts": prompts, "model": model, "depth": __DEPTH__},
            timeout=300,
        )
        data = response.json()
        if data.get("error"):
            return [f"Error: {data['error']}"] * len(prompts)
        return data.get("responses", ["Error: No response"] * len(prompts))
    except Exception as e:
        return [f"Error: LM query failed - {e}"] * len(prompts)


# =============================================================================
# State Management
# =============================================================================

STATE_FILE = "/tmp/rlm_state.dill"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "rb") as f:
                return dill.load(f)
        except:
            pass
    return {}

def save_state(state):
    clean_state = {}
    for k, v in state.items():
        if k.startswith("_"):
            continue
        try:
            dill.dumps(v)
            clean_state[k] = v
        except:
            pass
    with open(STATE_FILE, "wb") as f:
        dill.dump(clean_state, f)

def serialize_locals(state):
    result = {}
    for k, v in state.items():
        if k.startswith("_"):
            continue
        try:
            result[k] = repr(v)
        except:
            result[k] = f"<{type(v).__name__}>"
    return result

# =============================================================================
# Execution
# =============================================================================

_locals = load_state()

def FINAL_VAR(variable_name):
    variable_name = variable_name.strip().strip("\"\'")
    if variable_name in _locals:
        return str(_locals[variable_name])
    available = [k for k in _locals.keys() if not k.startswith("_")]
    if available:
        return f"Error: Variable '{variable_name}' not found. Available variables: {available}. You must create and assign a variable BEFORE calling FINAL_VAR on it."
    return f"Error: Variable '{variable_name}' not found. No variables have been created yet. You must create and assign a variable in a REPL block BEFORE calling FINAL_VAR on it."

def SHOW_VARS():
    available = {k: type(v).__name__ for k, v in _locals.items() if not k.startswith("_")}
    if not available:
        return "No variables created yet. Use ```repl``` blocks to create variables. When you have your final answer, assign it to a variable and return it with FINAL_VAR('variable_name')."
    return f"Available variables: {available}"

_globals = {
    "__builtins__": __builtins__,
    "__name__": "__main__",
    "llm_query": llm_query,
    "llm_query_batched": llm_query_batched,
    "FINAL_VAR": FINAL_VAR,
    "SHOW_VARS": SHOW_VARS,
}

code = base64.b64decode("__CODE_B64__").decode()

stdout_buf = io.StringIO()
stderr_buf = io.StringIO()
old_stdout, old_stderr = sys.stdout, sys.stderr

try:
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf
    combined = {**_globals, **_locals}
    exec(code, combined, combined)
    for key, value in combined.items():
        if key not in _globals and not key.startswith("_"):
            _locals[key] = value
except Exception as e:
    traceback.print_exc(file=stderr_buf)
finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr

save_state(_locals)

result = {
    "stdout": stdout_buf.getvalue(),
    "stderr": stderr_buf.getvalue(),
    "locals": serialize_locals(_locals),
}
print(json.dumps(result))
'''
)


DOCKER_EXEC_SCRIPT_TEMPLATE = textwrap.dedent(
    """
import sys, io, json, base64, traceback, os, requests
try:
    import dill
except ImportError:
    import pickle as dill

PROXY = "http://host.docker.internal:__PROXY_PORT__"
STATE = "/workspace/state.dill"

def llm_query(prompt, model=None):
    try:
        r = requests.post(f"{PROXY}/llm_query", json={"prompt": prompt, "model": model, "depth": __DEPTH__}, timeout=300)
        d = r.json()
        return d.get("response") or f"Error: {d.get('error')}"
    except Exception as e:
        return f"Error: {e}"

def llm_query_batched(prompts, model=None):
    try:
        r = requests.post(f"{PROXY}/llm_query_batched", json={"prompts": prompts, "model": model, "depth": __DEPTH__}, timeout=300)
        d = r.json()
        return d.get("responses") or [f"Error: {d.get('error')}"] * len(prompts)
    except Exception as e:
        return [f"Error: {e}"] * len(prompts)

def load_state():
    if os.path.exists(STATE):
        try:
            with open(STATE, "rb") as f:
                return dill.load(f)
        except:
            pass
    return {}

def save_state(s):
    clean = {k: v for k, v in s.items() if not k.startswith("_")}
    for k in list(clean.keys()):
        try:
            dill.dumps(clean[k])
        except:
            del clean[k]
    with open(STATE, "wb") as f:
        dill.dump(clean, f)

_locals = load_state()

def FINAL_VAR(name):
    name = name.strip().strip("\"\'")
    if name in _locals:
        return str(_locals[name])
    available = [k for k in _locals.keys() if not k.startswith("_")]
    if available:
        return f"Error: Variable '{name}' not found. Available variables: {available}. You must create and assign a variable BEFORE calling FINAL_VAR on it."
    return f"Error: Variable '{name}' not found. No variables have been created yet. You must create and assign a variable in a REPL block BEFORE calling FINAL_VAR on it."

def SHOW_VARS():
    available = {k: type(v).__name__ for k, v in _locals.items() if not k.startswith("_")}
    if not available:
        return "No variables created yet. Use ```repl``` blocks to create variables. When you have your final answer, assign it to a variable and return it with FINAL_VAR('variable_name')."
    return f"Available variables: {available}"

_globals = {"__builtins__": __builtins__, "__name__": "__main__", "llm_query": llm_query, "llm_query_batched": llm_query_batched, "FINAL_VAR": FINAL_VAR, "SHOW_VARS": SHOW_VARS}

code = base64.b64decode("__CODE_B64__").decode()
stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
old_stdout, old_stderr = sys.stdout, sys.stderr

try:
    sys.stdout, sys.stderr = stdout_buf, stderr_buf
    combined = {**_globals, **_locals}
    exec(code, combined, combined)
    for k, v in combined.items():
        if k not in _globals and not k.startswith("_"):
            _locals[k] = v
except:
    traceback.print_exc(file=stderr_buf)
finally:
    sys.stdout, sys.stderr = old_stdout, old_stderr

save_state(_locals)
print(json.dumps({"stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue(), "locals": {k: repr(v) for k, v in _locals.items() if not k.startswith("_")}}, ensure_ascii=False))
"""
)


def render_exec_script(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered
