import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

pytest.importorskip("mcp")

import rlm.mcp_gateway.server as gateway_server
from rlm.mcp_gateway.server import RLMMCPGateway, handle_get_prompt, handle_list_prompts


class _SamplingStubClient:
    def __init__(self) -> None:
        self.model_name = "stub-model"

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        selected = model or self.model_name
        return f"sampled:{selected}:{str(prompt)[:24]}"

    def stream_completion(
        self,
        prompt: str | list[dict[str, Any]],
        on_chunk: Callable[[str], None],
        model: str | None = None,
    ) -> str:
        text = self.completion(prompt, model=model)
        on_chunk(text)
        return text

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        return self.completion(prompt, model=model)

    def get_usage_summary(self) -> Any:
        from rlm.core.types import ModelUsageSummary, UsageSummary

        return UsageSummary(
            model_usage_summaries={
                self.model_name: ModelUsageSummary(
                    total_calls=1,
                    total_input_tokens=0,
                    total_output_tokens=0,
                )
            }
        )

    def get_last_usage(self) -> Any:
        from rlm.core.types import ModelUsageSummary

        return ModelUsageSummary(total_calls=1, total_input_tokens=0, total_output_tokens=0)


def _prompt_name(prompt_obj: object) -> str:
    if hasattr(prompt_obj, "name"):
        return str(getattr(prompt_obj, "name", ""))
    if isinstance(prompt_obj, dict):
        prompt_dict = cast(dict[str, Any], prompt_obj)
        return str(prompt_dict.get("name", ""))
    raise TypeError(f"Unsupported prompt object type: {type(prompt_obj)}")


def _prompt_text_from_result(result_obj: object) -> str:
    messages: list[Any] | None = cast(list[Any] | None, getattr(result_obj, "messages", None))
    if messages is None and isinstance(result_obj, dict):
        result_dict = cast(dict[str, Any], result_obj)
        messages_obj = result_dict.get("messages")
        messages = cast(list[Any], messages_obj) if isinstance(messages_obj, list) else []

    if not messages:
        return ""

    first_message = messages[0]
    content = getattr(first_message, "content", None)
    if content is None and isinstance(first_message, dict):
        first_message_dict = cast(dict[str, Any], first_message)
        content = first_message_dict.get("content", {})

    text = getattr(content, "text", None)
    if text is None and isinstance(content, dict):
        content_dict = cast(dict[str, Any], content)
        text = content_dict.get("text", "")

    return str(text or "")


def _tool_to_dict(tool_obj: object) -> dict[str, object]:
    model_dump = getattr(tool_obj, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return cast(dict[str, object], dumped)

    dict_method = getattr(tool_obj, "dict", None)
    if callable(dict_method):
        dumped = dict_method()
        if isinstance(dumped, dict):
            return cast(dict[str, object], dumped)

    raise TypeError(f"Unsupported tool object type: {type(tool_obj)}")


def _extract_text_payload(result_obj: dict[str, object]) -> dict[str, object]:
    content_obj = result_obj.get("content")
    if not isinstance(content_obj, list) or not content_obj:
        raise AssertionError("Expected non-empty content list")
    content = cast(list[object], content_obj)
    first_item: Any = content[0]
    text_value: Any = getattr(first_item, "text", None)
    if text_value is None and isinstance(first_item, dict):
        first_item_dict = cast(dict[str, object], first_item)
        text_value = first_item_dict.get("text")
    if not isinstance(text_value, str):
        raise AssertionError("Expected text content to be a string")
    payload = json.loads(text_value)
    if not isinstance(payload, dict):
        raise AssertionError("Expected JSON payload object")
    return cast(dict[str, object], payload)


def _create_test_client() -> Any:
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    test_client_cls = getattr(fastapi_testclient, "TestClient", None)
    if test_client_cls is None:
        raise RuntimeError("fastapi.testclient.TestClient not available")
    return test_client_cls(gateway_server.app)


def test_list_prompts_contains_expected_workflows() -> None:
    prompts = asyncio.run(handle_list_prompts())
    prompt_names = {_prompt_name(prompt) for prompt in prompts}

    assert "analyze" in prompt_names
    assert "summarize" in prompt_names
    assert "search" in prompt_names


def test_list_tools_exposes_output_schema_for_structured_tools() -> None:
    tools = asyncio.run(gateway_server.handle_list_tools())
    by_name = {_tool_to_dict(tool).get("name", ""): _tool_to_dict(tool) for tool in tools}

    for tool_name in ("rlm_complete", "rlm_search_query", "rlm_fs_list"):
        tool_dict = by_name.get(tool_name)
        assert isinstance(tool_dict, dict)
        assert "outputSchema" in tool_dict
        assert isinstance(tool_dict["outputSchema"], dict)


def test_list_tools_include_title_field() -> None:
    tools = asyncio.run(gateway_server.handle_list_tools())
    tool_dicts = [_tool_to_dict(tool) for tool in tools]

    assert tool_dicts
    for tool_dict in tool_dicts:
        assert "title" in tool_dict
        assert isinstance(tool_dict["title"], str)
        assert tool_dict["title"]


def test_list_tools_matches_declared_tool_specs() -> None:
    tools = asyncio.run(gateway_server.handle_list_tools())
    published_names = {str(_tool_to_dict(tool).get("name", "")) for tool in tools}
    public_tool_name = gateway_server.public_tool_name
    expected_names = {
        public_tool_name(str(spec.get("name", ""))) for spec in gateway_server.TOOL_SPECS
    }
    assert published_names == expected_names


def test_tool_name_alias_round_trip() -> None:
    tool_specs = gateway_server.TOOL_SPECS
    public_tool_name = gateway_server.public_tool_name
    canonical_tool_name = gateway_server.canonical_tool_name

    for spec in tool_specs:
        spec_name = str(spec["name"])
        public_name = public_tool_name(spec_name)
        canonical_name = canonical_tool_name(public_name)
        assert canonical_name == spec_name


def test_serialize_tool_result_envelope() -> None:
    serialize_tool_result = gateway_server.serialize_tool_result

    session_id = "session-envelope"
    complete_result: dict[str, Any] = {
        "success": True,
        "answer": "mock answer",
        "usage": {
            "model_usage_summaries": {
                "gpt-4o-mini": {
                    "total_calls": 1,
                    "total_input_tokens": 10,
                    "total_output_tokens": 20,
                }
            }
        },
        "execution_time": 0.2,
        "resource_link": {
            "type": "resource_link",
            "uri": f"rlm://sessions/{session_id}/trajectory",
            "name": f"RLM Trajectory {session_id}",
            "mimeType": "application/json",
        },
    }
    complete_serialized = serialize_tool_result(
        "rlm.complete",
        complete_result,
        {"response_format": "text"},
    )

    assert isinstance(complete_serialized, dict)
    assert "content" in complete_serialized
    assert "structuredContent" in complete_serialized

    complete_payload = _extract_text_payload(cast(dict[str, object], complete_serialized))
    assert complete_payload["answer"] == "mock answer"
    assert complete_serialized["structuredContent"]["answer"] == "mock answer"

    content_items = cast(list[Any], complete_serialized["content"])
    assert any(
        isinstance(item, dict) and cast(dict[str, Any], item).get("type") == "resource_link"
        for item in content_items
    )

    unstructured_result: dict[str, Any] = {"success": True, "stdout": "ok", "stderr": ""}
    unstructured_serialized = serialize_tool_result(
        "rlm.exec.run",
        unstructured_result,
        {},
    )

    assert isinstance(unstructured_serialized, list)
    unstructured_items = cast(list[Any], unstructured_serialized)
    first_item: object = unstructured_items[0]
    text_value: Any = getattr(first_item, "text", None)
    if text_value is None and isinstance(first_item, dict):
        text_value = cast(dict[str, Any], first_item).get("text")
    assert isinstance(text_value, str)
    assert json.loads(text_value) == unstructured_result


def test_get_prompt_renders_analyze_path() -> None:
    result = asyncio.run(handle_get_prompt("analyze", {"path": "rlm/core/rlm.py"}))
    prompt_text = _prompt_text_from_result(result)

    assert "Analyze `rlm/core/rlm.py` recursively using RLM." in prompt_text


def test_get_prompt_renders_search_scope_suffix() -> None:
    result = asyncio.run(handle_get_prompt("search", {"query": "LMHandler", "scope": "rlm/core"}))
    prompt_text = _prompt_text_from_result(result)

    assert "Search for `LMHandler` within `rlm/core`." in prompt_text


def test_gateway_resources_include_session_and_trajectory_uris() -> None:
    gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
    session = gateway.session_create()
    session_id = session["session_id"]

    resources = gateway.list_resources()
    uris = {resource["uri"] for resource in resources}

    assert "rlm://sessions" in uris
    assert f"rlm://sessions/{session_id}" in uris
    assert f"rlm://sessions/{session_id}/trajectory" in uris


def test_gateway_read_resource_returns_session_payload() -> None:
    gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
    session = gateway.session_create()
    session_id = session["session_id"]

    payload = gateway.read_resource(f"rlm://sessions/{session_id}")

    assert payload["success"] is True
    assert payload["session"]["session_id"] == session_id


def test_chunk_get_uses_metadata_from_chunk_create() -> None:
    gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
    session = gateway.session_create()
    session_id = session["session_id"]

    root = str(Path(__file__).resolve().parents[1])
    roots_result = gateway.roots_set(session_id, [root])
    assert roots_result["success"] is True

    file_path = str(Path(__file__).resolve())
    handle_result = gateway.fs_handle_create(session_id, file_path)
    assert handle_result["success"] is True
    file_handle = handle_result["file_handle"]

    create_result = gateway.chunk_create(
        session_id=session_id,
        file_handle=file_handle,
        chunk_size=7,
        overlap=2,
        budget=3,
    )
    assert create_result["success"] is True
    assert create_result["total_chunks"] == 3

    second_chunk_id = create_result["chunk_ids"][1]
    second_chunk = gateway.chunk_get(session_id, second_chunk_id)
    assert second_chunk["success"] is True
    assert second_chunk["start_line"] == 6
    assert second_chunk["end_line"] == 12


def test_chunk_create_rejects_invalid_overlap() -> None:
    gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
    session = gateway.session_create()
    session_id = session["session_id"]

    root = str(Path(__file__).resolve().parents[1])
    gateway.roots_set(session_id, [root])
    file_path = str(Path(__file__).resolve())
    handle_result = gateway.fs_handle_create(session_id, file_path)
    file_handle = handle_result["file_handle"]

    create_result = gateway.chunk_create(
        session_id=session_id,
        file_handle=file_handle,
        chunk_size=10,
        overlap=10,
        budget=1,
    )
    assert create_result["success"] is False
    assert "Invalid overlap" in create_result["error"]


def test_complete_fails_fast_without_backend_api_key() -> None:
    gateway = RLMMCPGateway(repo_root=str(Path(__file__).resolve().parents[1]))
    session = gateway.session_create()
    session_id = session["session_id"]

    env_updates = dict(os.environ)
    env_updates["RLM_BACKEND"] = "openai"
    env_updates["OPENAI_API_KEY"] = ""

    with patch.dict(os.environ, env_updates, clear=True):
        complete_result = gateway.complete(session_id=session_id, task="Summarize this repository")

    assert complete_result["success"] is False
    assert "API key not found" in complete_result["error"]
    assert "plan" not in complete_result


def test_call_tool_includes_structured_content_for_supported_tools() -> None:
    gateway_server.gateway = None
    gateway_server.gateway_instance = RLMMCPGateway(
        repo_root=str(Path(__file__).resolve().parents[1])
    )

    session = gateway_server.gateway_instance.session_create()
    session_id = session["session_id"]
    root = str(Path(__file__).resolve().parents[1])
    roots_result = gateway_server.gateway_instance.roots_set(session_id, [root])
    assert roots_result["success"] is True

    fs_result = asyncio.run(
        gateway_server.handle_call_tool(
            "rlm.fs.list",
            {
                "session_id": session_id,
                "root": root,
            },
        )
    )
    assert isinstance(fs_result, dict)
    assert "structuredContent" in fs_result
    assert fs_result["structuredContent"]["success"] is True
    assert isinstance(fs_result["structuredContent"]["entries"], list)

    search_result = asyncio.run(
        gateway_server.handle_call_tool(
            "rlm.search.query",
            {
                "session_id": session_id,
                "query": "RLM",
                "scope": root,
                "k": 3,
                "include_patterns": ["*.py"],
            },
        )
    )
    assert isinstance(search_result, dict)
    assert "structuredContent" in search_result
    assert search_result["structuredContent"]["success"] is True
    assert isinstance(search_result["structuredContent"]["results"], list)

    mocked_complete: dict[str, Any] = {
        "success": True,
        "answer": "mock answer",
        "usage": {
            "model_usage_summaries": {
                "gpt-4o-mini": {
                    "total_calls": 1,
                    "total_input_tokens": 10,
                    "total_output_tokens": 20,
                }
            }
        },
        "execution_time": 0.2,
        "resource_link": {
            "type": "resource_link",
            "uri": f"rlm://sessions/{session_id}/trajectory",
            "name": f"RLM Trajectory {session_id}",
            "mimeType": "application/json",
        },
    }
    with patch.object(
        gateway_server.gateway_instance,
        "complete",
        return_value=mocked_complete,
    ):
        complete_result = asyncio.run(
            gateway_server.handle_call_tool(
                "rlm.complete",
                {
                    "session_id": session_id,
                    "task": "hello",
                    "response_format": "text",
                },
            )
        )

    assert isinstance(complete_result, dict)
    assert "structuredContent" in complete_result
    assert complete_result["structuredContent"]["answer"] == "mock answer"
    assert complete_result["structuredContent"]["model"] == "gpt-4o-mini"
    assert "content" in complete_result
    assert any(
        isinstance(item, dict) and cast(dict[str, Any], item).get("type") == "resource_link"
        for item in cast(list[Any], complete_result["content"])
    )


def test_tool_text_content_matches_declared_output_schema_keys() -> None:
    gateway_server.gateway = None
    gateway_server.gateway_instance = RLMMCPGateway(
        repo_root=str(Path(__file__).resolve().parents[1])
    )

    session = gateway_server.gateway_instance.session_create()
    session_id = session["session_id"]
    root = str(Path(__file__).resolve().parents[1])
    roots_result = gateway_server.gateway_instance.roots_set(session_id, [root])
    assert roots_result["success"] is True

    fs_result = asyncio.run(
        gateway_server.handle_call_tool(
            "rlm.fs.list",
            {
                "session_id": session_id,
                "root": root,
            },
        )
    )
    assert isinstance(fs_result, dict)
    fs_payload = _extract_text_payload(cast(dict[str, object], fs_result))
    assert "entries" in fs_payload
    assert "items" not in fs_payload

    mocked_complete: dict[str, Any] = {
        "success": True,
        "answer": "mock answer",
        "usage": {
            "model_usage_summaries": {
                "gpt-4o-mini": {
                    "total_calls": 1,
                    "total_input_tokens": 10,
                    "total_output_tokens": 20,
                }
            }
        },
        "execution_time": 0.2,
        "resource_link": {
            "type": "resource_link",
            "uri": f"rlm://sessions/{session_id}/trajectory",
            "name": f"RLM Trajectory {session_id}",
            "mimeType": "application/json",
        },
    }
    with patch.object(
        gateway_server.gateway_instance,
        "complete",
        return_value=mocked_complete,
    ):
        complete_result = asyncio.run(
            gateway_server.handle_call_tool(
                "rlm.complete",
                {
                    "session_id": session_id,
                    "task": "hello",
                    "response_format": "text",
                },
            )
        )

    assert isinstance(complete_result, dict)
    complete_payload = _extract_text_payload(cast(dict[str, object], complete_result))
    assert "answer" in complete_payload
    assert "response" not in complete_payload


@pytest.mark.skipif(not gateway_server.HTTP_AVAILABLE, reason="FastAPI not installed")
def test_streamable_http_routes_registered() -> None:
    route_map = {
        route.path: set(getattr(route, "methods", set[str]()))
        for route in gateway_server.app.routes
    }

    assert "/mcp/messages" in route_map
    assert "GET" in route_map["/mcp/messages"]
    assert "POST" in route_map["/mcp/messages"]


@pytest.mark.skipif(not gateway_server.HTTP_AVAILABLE, reason="FastAPI not installed")
def test_streamable_http_get_returns_lifecycle_events() -> None:
    gateway_server.gateway_instance = RLMMCPGateway(
        repo_root=str(Path(__file__).resolve().parents[1])
    )
    client = _create_test_client()
    session_id = "test-session-events"

    post_response = client.post(
        "/mcp/messages",
        headers={"Mcp-Session-Id": session_id},
        json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}},
    )
    assert post_response.status_code == 200

    stream_response = client.get("/mcp/messages", headers={"Mcp-Session-Id": session_id})
    assert stream_response.status_code == 200
    stream_payload = stream_response.json()
    events = stream_payload["result"]["events"]
    event_types = {event["type"] for event in events}

    assert "request.received" in event_types
    assert "response.ready" in event_types
    assert "notifications/tools/list_changed" in event_types


@pytest.mark.skipif(not gateway_server.HTTP_AVAILABLE, reason="FastAPI not installed")
def test_sampling_create_message_bridge_uses_model_preferences() -> None:
    gateway_server.gateway_instance = RLMMCPGateway(
        repo_root=str(Path(__file__).resolve().parents[1])
    )
    client = _create_test_client()

    with patch.dict(
        os.environ, {"RLM_BACKEND": "openai", "OPENAI_API_KEY": "test-key"}, clear=False
    ):
        with patch.object(gateway_server, "get_client", return_value=_SamplingStubClient()):
            response = client.post(
                "/mcp/messages",
                headers={"Mcp-Session-Id": "sampling-session"},
                json={
                    "jsonrpc": "2.0",
                    "id": "s1",
                    "method": "sampling/createMessage",
                    "params": {
                        "messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}],
                        "modelPreferences": {"model": "stub-model"},
                    },
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["model"] == "stub-model"
    assert payload["result"]["content"]["type"] == "text"
    assert "sampled:stub-model" in payload["result"]["content"]["text"]


@pytest.mark.skipif(not gateway_server.HTTP_AVAILABLE, reason="FastAPI not installed")
def test_elicitation_lifecycle_over_http() -> None:
    gateway_server.gateway_instance = RLMMCPGateway(
        repo_root=str(Path(__file__).resolve().parents[1])
    )
    client = _create_test_client()
    session_id = "elicitation-session"

    create_response = client.post(
        "/mcp/messages",
        headers={"Mcp-Session-Id": session_id},
        json={
            "jsonrpc": "2.0",
            "id": "e1",
            "method": "elicitation/create",
            "params": {
                "title": "Need confirmation",
                "message": "Proceed?",
                "options": ["yes", "no"],
            },
        },
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    elicitation_id = create_payload["result"]["elicitationId"]

    poll_response = client.post(
        "/mcp/messages",
        headers={"Mcp-Session-Id": session_id},
        json={
            "jsonrpc": "2.0",
            "id": "e2",
            "method": "elicitation/poll",
            "params": {},
        },
    )
    assert poll_response.status_code == 200
    poll_payload = poll_response.json()["result"]["elicitations"]
    assert any(item["id"] == elicitation_id for item in poll_payload)

    respond_response = client.post(
        "/mcp/messages",
        headers={"Mcp-Session-Id": session_id},
        json={
            "jsonrpc": "2.0",
            "id": "e3",
            "method": "elicitation/respond",
            "params": {
                "elicitationId": elicitation_id,
                "selection": "yes",
            },
        },
    )
    assert respond_response.status_code == 200
    assert respond_response.json()["result"]["status"] == "accepted"
