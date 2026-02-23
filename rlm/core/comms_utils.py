"""
Communication utilities for RLM socket protocol.

Protocol: 4-byte big-endian length prefix + JSON payload.
Used for communication between LMHandler and environment subprocesses.
Socket requests are retried on transient failures (see failure_modes.md).
"""

import json
import socket
import struct
from dataclasses import dataclass
from typing import Any, cast

from rlm.core.retry import retry_with_backoff
from rlm.core.types import RLMChatCompletion

JsonDict = dict[str, Any]

# =============================================================================
# Message Dataclasses
# =============================================================================


@dataclass
class LMRequest:
    """Request message sent to the LM Handler.

    Supports both single prompt (prompt field) and batched prompts (prompts field).
    """

    prompt: str | list[dict[str, Any]] | None = None
    prompts: list[str | list[dict[str, Any]]] | None = None
    model: str | None = None
    model_preferences: dict[str, Any] | None = None
    depth: int = 0

    @property
    def is_batched(self) -> bool:
        """Check if this is a batched request."""
        return self.prompts is not None and len(self.prompts) > 0

    def to_dict(self) -> JsonDict:
        """Convert to dict, excluding None values."""
        d: JsonDict = {}
        if self.prompt is not None:
            d["prompt"] = self.prompt
        if self.prompts is not None:
            d["prompts"] = self.prompts
        if self.model is not None:
            d["model"] = self.model
        if self.model_preferences is not None:
            d["model_preferences"] = self.model_preferences
        d["depth"] = self.depth
        return d

    @classmethod
    def from_dict(cls, data: JsonDict) -> "LMRequest":
        """Create from dict. depth defaults to 0 if omitted."""
        prompt_raw = data.get("prompt")
        prompt: str | list[dict[str, Any]] | None = None
        if isinstance(prompt_raw, str):
            prompt = prompt_raw
        elif isinstance(prompt_raw, list):
            prompt = cast(list[dict[str, Any]], prompt_raw)

        prompts_raw = data.get("prompts")
        prompts: list[str | list[dict[str, Any]]] | None = None
        if isinstance(prompts_raw, list):
            prompts = cast(list[str | list[dict[str, Any]]], prompts_raw)

        model = data.get("model")
        model_preferences_raw = data.get("model_preferences")
        model_preferences = (
            cast(dict[str, Any], model_preferences_raw)
            if isinstance(model_preferences_raw, dict)
            else None
        )
        depth = int(data.get("depth", 0) or 0)
        return cls(
            prompt=prompt,
            prompts=prompts,
            model=model if isinstance(model, str) else None,
            model_preferences=model_preferences,
            depth=depth,
        )


@dataclass
class LMResponse:
    """Response message from the LM Handler.

    Supports both single response (chat_completion) and batched responses (chat_completions).
    """

    error: str | None = None
    chat_completion: RLMChatCompletion | None = None
    chat_completions: list[RLMChatCompletion] | None = None

    def __post_init__(self) -> None:
        if self.error is None and self.chat_completion is None and self.chat_completions is None:
            raise ValueError("LMResponse requires error, chat_completion, or chat_completions")

    @property
    def success(self) -> bool:
        """Check if response was successful."""
        return self.error is None

    @property
    def is_batched(self) -> bool:
        """Check if this is a batched response."""
        return self.chat_completions is not None

    def to_dict(self) -> JsonDict:
        """Convert to dict, excluding None values."""
        if self.error is not None:
            return {
                "error": self.error,
                "chat_completion": None,
                "chat_completions": None,
            }
        if self.chat_completions is not None:
            return {
                "chat_completions": [c.to_dict() for c in self.chat_completions],
                "chat_completion": None,
                "error": None,
            }
        if self.chat_completion is not None:
            return {
                "chat_completion": self.chat_completion.to_dict(),
                "chat_completions": None,
                "error": None,
            }
        raise ValueError("LMResponse requires error, chat_completion, or chat_completions")

    @classmethod
    def from_dict(cls, data: JsonDict) -> "LMResponse":
        """Create from dict."""
        chat_completions: list[RLMChatCompletion] | None = None
        chat_completions_raw = data.get("chat_completions")
        if isinstance(chat_completions_raw, list):
            parsed: list[RLMChatCompletion] = []
            for item in cast(list[Any], chat_completions_raw):
                if isinstance(item, dict):
                    parsed.append(RLMChatCompletion.from_dict(cast(dict[str, Any], item)))
            chat_completions = parsed

        chat_completion: RLMChatCompletion | None = None
        chat_completion_raw = data.get("chat_completion")
        if isinstance(chat_completion_raw, dict):
            chat_completion = RLMChatCompletion.from_dict(cast(dict[str, Any], chat_completion_raw))

        error = data.get("error")

        return cls(
            error=error if isinstance(error, str) else None,
            chat_completion=chat_completion,
            chat_completions=chat_completions,
        )

    @classmethod
    def success_response(cls, chat_completion: RLMChatCompletion) -> "LMResponse":
        """Create a successful single response."""
        return cls(chat_completion=chat_completion)

    @classmethod
    def batched_success_response(cls, chat_completions: list[RLMChatCompletion]) -> "LMResponse":
        """Create a successful batched response."""
        return cls(chat_completions=chat_completions)

    @classmethod
    def error_response(cls, error: str) -> "LMResponse":
        """Create an error response."""
        return cls(error=error)


# =============================================================================
# Socket Protocol Helpers
# =============================================================================


def socket_send(sock: socket.socket, data: JsonDict) -> None:
    """Send a length-prefixed JSON message over socket.

    Protocol: 4-byte big-endian length prefix + UTF-8 JSON payload.
    """
    payload = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def socket_recv(sock: socket.socket) -> JsonDict:
    """Receive a length-prefixed JSON message from socket.

    Protocol: 4-byte big-endian length prefix + UTF-8 JSON payload.
    Returns empty dict if connection closed before length received.

    Raises:
        ConnectionError: If connection closes mid-message.
    """
    raw_len = sock.recv(4)
    if not raw_len:
        return {}

    length = struct.unpack(">I", raw_len)[0]
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            raise ConnectionError("Connection closed before message complete")
        payload += chunk

    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Socket payload must decode to a JSON object")
    return cast(JsonDict, decoded)


def socket_request(address: tuple[str, int], data: JsonDict, timeout: int = 300) -> JsonDict:
    """Send a request and receive a response over a new socket connection.

    Opens a new TCP connection, sends the request, waits for response, then closes.

    Args:
        address: (host, port) tuple to connect to.
        data: Dictionary to send as JSON.
        timeout: Socket timeout in seconds (default 300).

    Returns:
        Response dictionary.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(address)
        socket_send(sock, data)
        return socket_recv(sock)


# =============================================================================
# Typed Request Helpers
# =============================================================================


def send_lm_request(
    address: tuple[str, int], request: LMRequest, timeout: int = 300, depth: int | None = None
) -> LMResponse:
    """Send an LM request and return typed response.

    Socket I/O is retried on ConnectionError, TimeoutError, OSError (see retry_with_backoff).
    """
    try:
        if depth is not None:
            request.depth = depth

        def _do_request() -> JsonDict:
            return socket_request(address, request.to_dict(), timeout)

        response_data = retry_with_backoff(
            _do_request,
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            backoff_factor=2.0,
        )
        return LMResponse.from_dict(response_data)
    except Exception as e:
        return LMResponse.error_response(f"Request failed: {e}")


def send_lm_request_batched(
    address: tuple[str, int],
    prompts: list[str | list[dict[str, Any]]],
    model: str | None = None,
    timeout: int = 300,
    depth: int = 0,
) -> list[LMResponse]:
    """Send a batched LM request and return a list of typed responses.

    Args:
        address: (host, port) tuple of LM Handler server.
        prompts: List of prompts to send.
        model: Optional model name to use.
        timeout: Socket timeout in seconds.
        depth: Depth for routing (default 0).

    Returns:
        List of LMResponse objects, one per prompt, in the same order.
    """
    try:
        request = LMRequest(prompts=prompts, model=model, depth=depth)

        def _do_request() -> JsonDict:
            return socket_request(address, request.to_dict(), timeout)

        response_data = retry_with_backoff(
            _do_request,
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            backoff_factor=2.0,
        )
        response = LMResponse.from_dict(response_data)

        if not response.success:
            # Return error responses for all prompts
            error_message = response.error or "Unknown LM handler error"
            return [LMResponse.error_response(error_message)] * len(prompts)

        if response.chat_completions is None:
            return [LMResponse.error_response("No completions returned")] * len(prompts)

        # Convert batched response to list of individual responses
        return [
            LMResponse.success_response(chat_completion)
            for chat_completion in response.chat_completions
        ]
    except Exception as e:
        return [LMResponse.error_response(f"Request failed: {e}")] * len(prompts)


def normalize_model_preferences(raw: Any) -> dict[str, Any] | None:
    """Normalize model preference payloads from transport requests.

    Accepts both snake_case and camelCase variants used by different MCP
    clients and returns a canonical dictionary for LM routing.
    """
    if not isinstance(raw, dict):
        return None

    normalized: dict[str, Any] = {}
    key_aliases = {
        "model": "model",
        "modelname": "model_name",
        "model_name": "model_name",
        "preferredmodel": "preferred_model",
        "preferred_model": "preferred_model",
        "candidates": "candidates",
        "contains": "contains",
        "family": "family",
    }

    for key, value in cast(dict[str, Any], raw).items():
        normalized_key = key_aliases.get(str(key).replace("-", "").replace(" ", "").lower())
        if normalized_key is not None:
            normalized[normalized_key] = value

    return normalized or None
