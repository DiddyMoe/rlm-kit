```instructions
# Debugging Module

The debugging module (`rlm/debugging/`) provides two tools for tracking and visualizing LLM calls during RLM execution.

## CallHistory

### File: `rlm/debugging/call_history.py`

Tracks all LLM calls (prompts, responses, token usage, timing) for debugging and analysis.

### Key Types

```python
@dataclass
class CallHistoryEntry:
    call_id: str                          # Auto-generated: "call_{N}_{timestamp}"
    timestamp: float                      # Unix timestamp
    model: str                            # Model name
    prompt: str | dict[str, Any]          # Prompt sent
    response: str                         # Response received
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None       # Auto-calculated if not provided
    execution_time: float | None = None
    metadata: dict[str, Any] | None = None
```

### Usage

```python
from rlm.debugging.call_history import CallHistory

history = CallHistory()

# Add calls manually
entry = history.add_call(
    model="gpt-4o",
    prompt="What is 2+2?",
    response="4",
    input_tokens=10,
    output_tokens=1,
)

# Add from RLMChatCompletion
entry = history.add_from_rlm_completion(completion, metadata={"task": "math"})

# Query with filters
recent = history.get_calls(model="gpt-4o", limit=10)
time_range = history.get_calls(start_time=t0, end_time=t1)

# Statistics
stats = history.get_statistics()
# → {"total_calls": N, "total_tokens": N, "total_execution_time": N, "models": {...}}

# Export
history.export_json("debug_history.json")

# Serialization
data = history.to_dict()
restored = CallHistory.from_dict(data)
```

## GraphTracker

### File: `rlm/debugging/graph_tracker.py`

Tracks recursive LLM call graphs for visualization. Maintains a tree of `GraphNode` entries and optionally builds a NetworkX `DiGraph` for graph operations and export.

### Key Types

```python
@dataclass
class GraphNode:
    node_id: str
    parent_id: str | None                 # None for root node
    depth: int                            # Recursion depth
    iteration: int                        # Iteration number
    model: str
    prompt_preview: str                   # Truncated to 200 chars
    response_preview: str                 # Truncated to 200 chars
    input_tokens: int | None = None
    output_tokens: int | None = None
    execution_time: float | None = None
    timestamp: float | None = None
    metadata: dict[str, Any] | None = None
```

### Usage

```python
from rlm.debugging.graph_tracker import GraphTracker

tracker = GraphTracker()

# Add nodes (prompt/response previews auto-truncated to 200 chars)
tracker.add_node(
    node_id="root",
    parent_id=None,
    depth=0,
    iteration=1,
    model="gpt-4o",
    prompt_preview="Analyze this dataset...",
    response_preview="I'll break this into steps...",
)

tracker.add_node(
    node_id="sub_1",
    parent_id="root",
    depth=1,
    iteration=1,
    model="gpt-4o-mini",
    prompt_preview="Summarize chunk 1...",
    response_preview="Chunk 1 contains...",
)

# Tree navigation
children = tracker.get_children("root")         # Direct children
path = tracker.get_path_to_root("sub_1")         # [root, sub_1]

# Statistics
stats = tracker.get_statistics()
# → {"total_nodes": 2, "max_depth": 1, "nodes_by_depth": {0: 1, 1: 1}, ...}

# Export
tracker.export_json("call_graph.json")
tracker.export_graphml("call_graph.graphml")    # Requires NetworkX
tracker.print_summary()                          # Console output
```

### NetworkX Integration

NetworkX is an **optional dependency** (in the `test` group). When available:
- A `DiGraph` is automatically built alongside the node dict
- `export_graphml()` produces GraphML for visualization tools
- Falls back gracefully when not installed

```python
from rlm.debugging.graph_tracker import NETWORKX_AVAILABLE
# NETWORKX_AVAILABLE = True/False depending on import success
```

## When to Use Each

| Need | Tool |
|------|------|
| Flat list of all LLM calls with filtering | `CallHistory` |
| Recursive call tree visualization | `GraphTracker` |
| Token usage statistics per model | `CallHistory.get_statistics()` |
| Depth/iteration analysis | `GraphTracker.get_statistics()` |
| JSON export for external tools | Both (`export_json()`) |
| Graph visualization (Gephi, etc.) | `GraphTracker.export_graphml()` |
| Reset all tracked data | `GraphTracker.clear()` |

## Serialization

Both follow the project's dataclass pattern:
- `to_dict()` / `from_dict()` on all dataclasses
- `to_dict()` / `from_dict()` on container classes (`CallHistory`, `GraphTracker`)
- JSON export via dedicated `export_json()` methods

```
```
