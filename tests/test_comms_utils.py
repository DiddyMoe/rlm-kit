import json
import socket
import struct
from typing import Any

import pytest

from rlm.core.comms_utils import (
    LMRequest,
    LMResponse,
    send_lm_request,
    send_lm_request_batched,
    socket_recv,
    socket_send,
)
from rlm.core.types import ModelUsageSummary, RLMChatCompletion, UsageSummary


def _make_completion(response: str) -> RLMChatCompletion:
    usage = UsageSummary(
        model_usage_summaries={
            "gpt-test": ModelUsageSummary(
                total_calls=1,
                total_input_tokens=10,
                total_output_tokens=5,
            )
        }
    )
    return RLMChatCompletion("gpt-test", "hello", response, usage, 0.25, {"source": "test"})


class TestLMRequestSerialization:
    def test_roundtrip_preserves_all_fields(self) -> None:
        request = LMRequest(
            prompt=[{"role": "user", "content": "hi"}],
            prompts=["a", [{"role": "user", "content": "b"}]],
            model="gpt-test",
            model_preferences={"family": "gpt"},
            depth=2,
        )

        restored = LMRequest.from_dict(request.to_dict())

        assert restored.prompt == request.prompt
        assert restored.prompts == request.prompts
        assert restored.model == request.model
        assert restored.model_preferences == request.model_preferences
        assert restored.depth == request.depth
        assert restored.is_batched is True

    def test_from_dict_defaults_depth_to_zero(self) -> None:
        restored = LMRequest.from_dict({"prompt": "hello"})
        assert restored.depth == 0


class TestLMResponseSerialization:
    def test_all_none_fields_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="LMResponse requires"):
            LMResponse()

    def test_roundtrip_single_success_response(self) -> None:
        completion = _make_completion("done")
        response = LMResponse.success_response(completion)

        restored = LMResponse.from_dict(response.to_dict())

        assert restored.success is True
        assert restored.chat_completion is not None
        assert restored.chat_completion.response == "done"
        assert restored.chat_completions is None

    def test_roundtrip_batched_success_response(self) -> None:
        completions = [_make_completion("one"), _make_completion("two")]
        response = LMResponse.batched_success_response(completions)

        restored = LMResponse.from_dict(response.to_dict())

        assert restored.success is True
        assert restored.chat_completion is None
        assert restored.chat_completions is not None
        assert [item.response for item in restored.chat_completions] == ["one", "two"]

    def test_roundtrip_error_response(self) -> None:
        response = LMResponse.error_response("failure")

        restored = LMResponse.from_dict(response.to_dict())

        assert restored.success is False
        assert restored.error == "failure"
        assert restored.chat_completion is None
        assert restored.chat_completions is None

    def test_roundtrip_preserves_empty_batched_list(self) -> None:
        response = LMResponse(chat_completions=[])

        restored = LMResponse.from_dict(response.to_dict())

        assert restored.chat_completions == []
        assert restored.is_batched is True


class TestSocketWireFormat:
    def test_socket_send_uses_length_prefixed_json(self) -> None:
        payload: dict[str, Any] = {"message": "hello", "value": 42}
        sender, receiver = socket.socketpair()
        try:
            socket_send(sender, payload)
            raw = receiver.recv(4096)
        finally:
            sender.close()
            receiver.close()

        message_length = struct.unpack(">I", raw[:4])[0]
        message_bytes = raw[4:]
        assert message_length == len(message_bytes)
        assert json.loads(message_bytes.decode("utf-8")) == payload

    def test_socket_recv_reconstructs_original_payload(self) -> None:
        payload: dict[str, Any] = {"status": "ok", "items": [1, 2, 3]}
        encoded = json.dumps(payload).encode("utf-8")
        sender, receiver = socket.socketpair()
        try:
            sender.sendall(struct.pack(">I", len(encoded)) + encoded)
            restored = socket_recv(receiver)
        finally:
            sender.close()
            receiver.close()

        assert restored == payload

    def test_socket_recv_returns_empty_dict_on_closed_connection(self) -> None:
        sender, receiver = socket.socketpair()
        sender.close()
        try:
            restored = socket_recv(receiver)
        finally:
            receiver.close()

        assert restored == {}

    def test_socket_recv_raises_on_truncated_payload(self) -> None:
        sender, receiver = socket.socketpair()
        try:
            sender.sendall(struct.pack(">I", 10) + b"abc")
            sender.close()
            with pytest.raises(ConnectionError, match="message complete"):
                socket_recv(receiver)
        finally:
            receiver.close()

    def test_send_lm_request_connection_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts = {"count": 0}

        def _fail_socket_request(*_args: object, **_kwargs: object) -> dict[str, Any]:
            attempts["count"] += 1
            raise ConnectionRefusedError("connection refused")

        def _no_sleep(_delay: float) -> None:
            return None

        monkeypatch.setattr("rlm.core.comms_utils.socket_request", _fail_socket_request)
        monkeypatch.setattr("rlm.core.retry.time.sleep", _no_sleep)

        response = send_lm_request(("127.0.0.1", 9999), LMRequest(prompt="hello"))

        assert attempts["count"] == 3
        assert response.success is False
        assert response.error is not None
        assert "Request failed" in response.error
        assert "connection refused" in response.error

    def test_send_lm_request_batched_connection_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts = {"count": 0}

        def _fail_socket_request(*_args: object, **_kwargs: object) -> dict[str, Any]:
            attempts["count"] += 1
            raise ConnectionRefusedError("connection refused")

        def _no_sleep(_delay: float) -> None:
            return None

        monkeypatch.setattr("rlm.core.comms_utils.socket_request", _fail_socket_request)
        monkeypatch.setattr("rlm.core.retry.time.sleep", _no_sleep)

        prompts: list[str | list[dict[str, Any]]] = ["hello", "world"]
        responses = send_lm_request_batched(("127.0.0.1", 9999), prompts)

        assert attempts["count"] == 3
        assert len(responses) == 2
        assert all(response.success is False for response in responses)
        assert all(response.error is not None for response in responses)
        assert all("Request failed" in str(response.error) for response in responses)
        assert all("connection refused" in str(response.error) for response in responses)

    def test_send_lm_request_batched_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict[str, Any]] = []

        def _mock_socket_request(
            _address: tuple[str, int], data: dict[str, Any], _timeout: int = 300
        ) -> dict[str, Any]:
            calls.append(data)
            completions = [_make_completion("one"), _make_completion("two")]
            return LMResponse.batched_success_response(completions).to_dict()

        monkeypatch.setattr("rlm.core.comms_utils.socket_request", _mock_socket_request)

        prompts: list[str | list[dict[str, Any]]] = [
            "hello",
            [{"role": "user", "content": "world"}],
        ]
        responses = send_lm_request_batched(
            ("127.0.0.1", 9999),
            prompts,
            model="gpt-test",
            depth=2,
        )

        assert len(calls) == 1
        request = LMRequest.from_dict(calls[0])
        assert request.prompts == prompts
        assert request.model == "gpt-test"
        assert request.depth == 2
        assert request.is_batched is True

        assert len(responses) == 2
        assert all(response.success for response in responses)
        assert responses[0].chat_completion is not None
        assert responses[1].chat_completion is not None
        assert responses[0].chat_completion.response == "one"
        assert responses[1].chat_completion.response == "two"
