from __future__ import annotations

import json
from pathlib import Path

import pytest

from rlm.debugging.graph_tracker import GraphNode, GraphTracker


class TestGraphNode:
    def test_round_trip_to_dict_from_dict(self) -> None:
        node = GraphNode(
            node_id="n1",
            parent_id=None,
            depth=0,
            iteration=1,
            model="gpt-4o",
            prompt_preview="prompt",
            response_preview="response",
            input_tokens=10,
            output_tokens=5,
            execution_time=0.2,
            timestamp=123.45,
            metadata={"k": "v"},
        )

        restored = GraphNode.from_dict(node.to_dict())

        assert restored == node


class TestGraphTracker:
    def test_add_node_and_get_node(self) -> None:
        tracker = GraphTracker()

        tracker.add_node(
            node_id="root",
            parent_id=None,
            depth=0,
            iteration=1,
            model="gpt-4o",
            prompt_preview="p",
            response_preview="r",
        )

        node = tracker.get_node("root")
        assert node is not None
        assert node.node_id == "root"
        assert tracker.root_node_id == "root"

    def test_get_children_returns_expected_nodes(self) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")
        tracker.add_node("c1", "root", 1, 2, "m", "p1", "r1")
        tracker.add_node("c2", "root", 1, 2, "m", "p2", "r2")

        children = tracker.get_children("root")

        assert sorted([child.node_id for child in children]) == ["c1", "c2"]

    def test_get_path_to_root_traverses_parent_chain(self) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")
        tracker.add_node("child", "root", 1, 2, "m", "p", "r")
        tracker.add_node("leaf", "child", 2, 3, "m", "p", "r")

        path = tracker.get_path_to_root("leaf")

        assert [node.node_id for node in path] == ["root", "child", "leaf"]

    def test_get_statistics_returns_expected_aggregates(self) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")
        tracker.add_node("child1", "root", 1, 2, "m", "p", "r")
        tracker.add_node("child2", "root", 1, 2, "m", "p", "r")

        stats = tracker.get_statistics()

        assert stats["total_nodes"] == 3
        assert stats["max_depth"] == 1
        assert stats["total_iterations"] == 2
        assert stats["nodes_by_depth"][0] == 1
        assert stats["nodes_by_depth"][1] == 2

    def test_to_dict_returns_serializable_structure(self) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")

        payload = tracker.to_dict()

        json.dumps(payload)
        assert payload["root_node_id"] == "root"
        assert "root" in payload["nodes"]

    def test_export_json_writes_valid_json_file(self, tmp_path: Path) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")

        output_file = tmp_path / "graph.json"
        tracker.export_json(str(output_file))

        loaded = json.loads(output_file.read_text(encoding="utf-8"))
        assert loaded["root_node_id"] == "root"
        assert loaded["statistics"]["total_nodes"] == 1

    def test_export_graphml_when_networkx_available(self, tmp_path: Path) -> None:
        pytest.importorskip("networkx")
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")
        tracker.add_node("child", "root", 1, 2, "m", "p", "r")

        output_file = tmp_path / "graph.graphml"
        tracker.export_graphml(str(output_file))

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_clear_resets_state(self) -> None:
        tracker = GraphTracker()
        tracker.add_node("root", None, 0, 1, "m", "p", "r")

        tracker.clear()

        assert tracker.nodes == {}
        assert tracker.root_node_id is None
        if tracker.graph is not None:
            assert tracker.graph.number_of_nodes() == 0
