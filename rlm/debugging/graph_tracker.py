"""Graph tracking for recursive LLM call visualization."""

import importlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

_networkx_module: Any | None
try:
    _networkx_module = importlib.import_module("networkx")
except ImportError:
    _networkx_module = None

nx: Any = _networkx_module
NETWORKX_AVAILABLE: bool = _networkx_module is not None


@dataclass
class GraphNode:
    """Node in the recursive call graph."""

    node_id: str
    parent_id: str | None
    depth: int
    iteration: int
    model: str
    prompt_preview: str
    response_preview: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    execution_time: float | None = None
    timestamp: float | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNode":
        """Create from dictionary."""
        return cls(**data)


class GraphTracker:
    """Track recursive LLM call graph for visualization."""

    def __init__(self) -> None:
        """Initialize empty graph tracker."""
        self.nodes: dict[str, GraphNode] = {}
        self.root_node_id: str | None = None
        self.graph: Any | None
        if NETWORKX_AVAILABLE:
            self.graph = nx.DiGraph()
        else:
            self.graph = None

    def add_node(
        self,
        node_id: str,
        parent_id: str | None,
        depth: int,
        iteration: int,
        model: str,
        prompt_preview: str,
        response_preview: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        execution_time: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a node to the graph."""
        node = GraphNode(
            node_id=node_id,
            parent_id=parent_id,
            depth=depth,
            iteration=iteration,
            model=model,
            prompt_preview=prompt_preview[:200] if len(prompt_preview) > 200 else prompt_preview,
            response_preview=response_preview[:200]
            if len(response_preview) > 200
            else response_preview,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            execution_time=execution_time,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self.nodes[node_id] = node

        # Set root node if this is the first node
        if self.root_node_id is None:
            self.root_node_id = node_id

        # Add to NetworkX graph if available
        if self.graph is not None:
            self.graph.add_node(
                node_id,
                **{
                    "depth": depth,
                    "iteration": iteration,
                    "model": model,
                    "prompt_preview": node.prompt_preview,
                    "response_preview": node.response_preview,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "execution_time": execution_time,
                },
            )
            if parent_id is not None and parent_id in self.nodes:
                self.graph.add_edge(parent_id, node_id)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        node = self.nodes.get(node_id)
        return node

    def get_children(self, node_id: str) -> list[GraphNode]:
        """Get all children of a node."""
        return [node for node in self.nodes.values() if node.parent_id == node_id]

    def get_path_to_root(self, node_id: str) -> list[GraphNode]:
        """Get path from node to root."""
        path: list[GraphNode] = []
        current_id: str | None = node_id
        while current_id is not None:
            node = self.nodes.get(current_id)
            if node is None:
                break
            path.append(node)
            current_id = node.parent_id
        return path[::-1]  # Reverse to get root-to-node path

    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        if not self.nodes:
            return {"total_nodes": 0, "max_depth": 0, "total_iterations": 0}

        depths = [node.depth for node in self.nodes.values()]
        iterations = [node.iteration for node in self.nodes.values()]

        stats: dict[str, Any] = {
            "total_nodes": len(self.nodes),
            "max_depth": max(depths) if depths else 0,
            "total_iterations": max(iterations) if iterations else 0,
            "nodes_by_depth": {},
            "nodes_by_iteration": {},
        }

        # Count nodes by depth
        for node in self.nodes.values():
            depth = node.depth
            stats["nodes_by_depth"][depth] = stats["nodes_by_depth"].get(depth, 0) + 1

        # Count nodes by iteration
        for node in self.nodes.values():
            iteration = node.iteration
            stats["nodes_by_iteration"][iteration] = (
                stats["nodes_by_iteration"].get(iteration, 0) + 1
            )

        return stats

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "root_node_id": self.root_node_id,
            "statistics": self.get_statistics(),
        }

    def export_json(self, file_path: str) -> None:
        """Export graph to JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    def export_graphml(self, file_path: str) -> None:
        """Export graph to GraphML format (requires NetworkX)."""
        if not NETWORKX_AVAILABLE or self.graph is None:
            raise ImportError(
                "NetworkX is required for GraphML export. Install with: pip install networkx"
            )

        nx.write_graphml(self.graph, file_path)

    def print_summary(self) -> None:
        """Print graph summary."""
        print(f"\n{'=' * 60}")
        print("Recursive Call Graph Summary")
        print(f"{'=' * 60}")
        stats = self.get_statistics()
        print(f"Total Nodes: {stats['total_nodes']}")
        print(f"Max Depth: {stats['max_depth']}")
        print(f"Total Iterations: {stats['total_iterations']}")

        if stats["nodes_by_depth"]:
            print("\nNodes by Depth:")
            for depth in sorted(stats["nodes_by_depth"].keys()):
                print(f"  Depth {depth}: {stats['nodes_by_depth'][depth]} nodes")

        if stats["nodes_by_iteration"]:
            print("\nNodes by Iteration:")
            for iteration in sorted(stats["nodes_by_iteration"].keys()):
                print(f"  Iteration {iteration}: {stats['nodes_by_iteration'][iteration]} nodes")

        print(f"{'=' * 60}\n")

    def clear(self) -> None:
        """Clear all graph data."""
        self.nodes.clear()
        self.root_node_id = None
        if self.graph is not None:
            self.graph.clear()
