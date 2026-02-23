"""
LMHandler - Routes LLM requests from the RLM process and environment subprocesses.

Uses a multi-threaded socket server. Protocol: 4-byte length prefix + JSON payload.
"""

import asyncio
import time
from collections.abc import Callable
from socketserver import StreamRequestHandler, ThreadingTCPServer
from threading import Thread
from types import TracebackType
from typing import Any, cast

from rlm.clients.base_lm import BaseLM
from rlm.core.comms_utils import LMRequest, LMResponse, socket_recv, socket_send
from rlm.core.types import RLMChatCompletion, UsageSummary


class LMRequestHandler(StreamRequestHandler):
    """Socket handler for LLM completion requests."""

    def handle(self):
        try:
            request_data = socket_recv(self.connection)
            request = LMRequest.from_dict(request_data)
            server_handler = getattr(self.server, "lm_handler", None)
            if not isinstance(server_handler, LMHandler):
                response = LMResponse.error_response("LM handler is not configured on server")
                self._safe_send(response)
                return
            handler = server_handler

            if request.is_batched:
                # Batched request: process multiple prompts concurrently
                response = self._handle_batched(request, handler)
            elif request.prompt:
                # Single request: process one prompt
                response = self._handle_single(request, handler)
            else:
                response = LMResponse.error_response("Missing 'prompt' or 'prompts' in request.")

            self._safe_send(response)

        except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError):
            # Client disconnected - this is expected during parallel execution
            # when workers complete and close their sockets. Silently ignore.
            pass

        except Exception as e:
            # Try to send error response, but don't fail if socket is broken
            response = LMResponse.error_response(str(e))
            self._safe_send(response)

    def _safe_send(self, response: LMResponse) -> bool:
        """Send response, returning False if the socket is broken."""
        try:
            socket_send(self.connection, response.to_dict())
            return True
        except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError):
            # Client disconnected - silently ignore
            return False

    def _handle_single(self, request: LMRequest, handler: "LMHandler") -> LMResponse:
        """Handle a single prompt request."""
        if request.prompt is None:
            return LMResponse.error_response("Missing 'prompt' for single request")

        client = handler.get_client(request.model, request.depth, request.model_preferences)
        budget_error = handler.get_budget_error(request.depth, client)
        if budget_error is not None:
            return LMResponse.error_response(budget_error)

        start_time = time.perf_counter()
        content = client.completion(request.prompt)
        end_time = time.perf_counter()

        budget_error = handler.get_budget_error(request.depth, client)
        if budget_error is not None:
            return LMResponse.error_response(budget_error)

        model_usage = client.get_last_usage()
        root_model = request.model or client.model_name
        usage_summary = UsageSummary(model_usage_summaries={root_model: model_usage})
        return LMResponse.success_response(
            chat_completion=RLMChatCompletion(
                root_model,
                request.prompt,
                content,
                usage_summary,
                end_time - start_time,
            )
        )

    def _handle_batched(self, request: LMRequest, handler: "LMHandler") -> LMResponse:
        """Handle a batched prompts request using async for concurrency."""
        if request.prompts is None:
            return LMResponse.error_response("Missing 'prompts' for batched request")

        prompts = request.prompts
        client = handler.get_client(request.model, request.depth, request.model_preferences)
        budget_error = handler.get_budget_error(request.depth, client)
        if budget_error is not None:
            return LMResponse.error_response(budget_error)

        start_time = time.perf_counter()

        async def run_all():
            tasks = [client.acompletion(prompt) for prompt in prompts]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_all())
        end_time = time.perf_counter()

        budget_error = handler.get_budget_error(request.depth, client)
        if budget_error is not None:
            return LMResponse.error_response(budget_error)

        total_time = end_time - start_time
        model_usage = client.get_last_usage()
        root_model = request.model or client.model_name
        usage_summary = UsageSummary(model_usage_summaries={root_model: model_usage})

        chat_completions = [
            RLMChatCompletion(
                root_model,
                prompt,
                content,
                usage_summary,
                total_time / len(prompts),  # approximate per-prompt time
            )
            for prompt, content in zip(prompts, results, strict=True)
        ]

        return LMResponse.batched_success_response(chat_completions=chat_completions)


class ThreadingLMServer(ThreadingTCPServer):
    """Multi-threaded TCP server for LM requests."""

    daemon_threads = True
    allow_reuse_address = True


class LMHandler:
    """
    Handles all LM calls from the RLM main process and environment subprocesses.

    Uses a multi-threaded socket server for concurrent requests.
    Protocol: 4-byte big-endian length prefix + JSON payload.
    """

    def __init__(
        self,
        client: BaseLM,
        host: str = "127.0.0.1",
        port: int = 0,  # auto-assign available port
        other_backend_client: BaseLM | None = None,
        max_root_tokens: int | None = None,
        max_sub_tokens: int | None = None,
    ):
        self.default_client = client
        self.other_backend_client = other_backend_client
        self.max_root_tokens = max_root_tokens
        self.max_sub_tokens = max_sub_tokens
        self.clients: dict[str, BaseLM] = {}
        self.host = host
        self._server: ThreadingLMServer | None = None
        self._thread: Thread | None = None
        self._port = port

        self.register_client(client.model_name, client)

    def register_client(self, model_name: str, client: BaseLM) -> None:
        """Register a client for a specific model name."""
        self.clients[model_name] = client

    def get_client(
        self,
        model: str | None = None,
        depth: int = 0,
        model_preferences: dict[str, Any] | None = None,
    ) -> BaseLM:
        """Get client by model name or depth, or return default.

        Routing logic:
        - If model is specified and exists in clients, use that.
        - If model_preferences are provided, resolve to the first matching registered client.
        - depth=0: use default_client (main backend)
        - depth>=1: use other_backend_client if it exists, otherwise default_client
        """
        if model and model in self.clients:
            return self.clients[model]

        preference_client = self._resolve_preferred_client(model_preferences)
        if preference_client is not None:
            return preference_client

        # Route based on depth
        if depth >= 1 and self.other_backend_client is not None:
            return self.other_backend_client

        return self.default_client

    def _resolve_preferred_client(self, model_preferences: dict[str, Any] | None) -> BaseLM | None:
        """Resolve a client from preference hints.

        This is intentionally permissive and forward-compatible to support future
        MCP Sampling modelPreferences payloads without coupling to a fixed schema.
        """
        if not model_preferences:
            return None

        direct_match = self._resolve_direct_preference(model_preferences)
        if direct_match is not None:
            return direct_match

        candidate_match = self._resolve_candidate_preference(model_preferences)
        if candidate_match is not None:
            return candidate_match

        return self._resolve_contains_preference(model_preferences)

    def _resolve_direct_preference(self, model_preferences: dict[str, Any]) -> BaseLM | None:
        for key in ("model", "model_name", "preferred_model"):
            model_name = model_preferences.get(key)
            matched_client = self._client_by_model_name(model_name)
            if matched_client is not None:
                return matched_client
        return None

    def _resolve_candidate_preference(self, model_preferences: dict[str, Any]) -> BaseLM | None:
        candidates = model_preferences.get("candidates")
        if not isinstance(candidates, list):
            return None
        for candidate in cast(list[Any], candidates):
            matched_client = self._client_by_model_name(candidate)
            if matched_client is not None:
                return matched_client
        return None

    def _resolve_contains_preference(self, model_preferences: dict[str, Any]) -> BaseLM | None:
        for key in ("contains", "family"):
            hint = model_preferences.get(key)
            matched_client = self._client_by_name_substring(hint)
            if matched_client is not None:
                return matched_client
        return None

    def _client_by_model_name(self, model_name: Any) -> BaseLM | None:
        if not isinstance(model_name, str):
            return None
        return self.clients.get(model_name)

    def _client_by_name_substring(self, hint: Any) -> BaseLM | None:
        if not isinstance(hint, str):
            return None
        hint_lower = hint.lower()
        for model_name, client in self.clients.items():
            if hint_lower in model_name.lower():
                return client
        return None

    def resolve_model_name(
        self,
        model: str | None = None,
        depth: int = 0,
        model_preferences: dict[str, Any] | None = None,
    ) -> str:
        """Resolve and return the selected model name for a request shape."""
        selected_client = self.get_client(
            model=model,
            depth=depth,
            model_preferences=model_preferences,
        )
        return selected_client.model_name

    @property
    def port(self) -> int:
        """Get the actual port (useful when auto-assigned)."""
        if self._server:
            return self._server.server_address[1]
        return self._port

    @property
    def address(self) -> tuple[str, int]:
        """Get (host, port) tuple for connecting."""
        return (self.host, self.port)

    def start(self) -> tuple[str, int]:
        """Start the socket server in a background thread. Returns (host, port)."""
        if self._server is not None:
            return self.address

        self._server = ThreadingLMServer((self.host, self._port), LMRequestHandler)
        self._server.lm_handler = self  # type: ignore

        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        return self.address

    def stop(self) -> None:
        """Stop the socket server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None

    def completion(
        self,
        prompt: str | list[dict[str, Any]],
        model: str | None = None,
        model_preferences: dict[str, Any] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """Direct completion call (for main process use)."""
        client = self.get_client(model, depth=0, model_preferences=model_preferences)
        budget_error = self.get_budget_error(0, client)
        if budget_error is not None:
            raise RuntimeError(budget_error)

        if on_chunk is not None:
            response = client.stream_completion(prompt, on_chunk, model=model)
        else:
            response = client.completion(prompt)
        budget_error = self.get_budget_error(0, client)
        if budget_error is not None:
            raise RuntimeError(budget_error)
        return response

    async def acompletion(
        self,
        prompt: str | list[dict[str, Any]],
        model: str | None = None,
        model_preferences: dict[str, Any] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """Async wrapper for direct completion calls."""
        return await asyncio.to_thread(
            self.completion,
            prompt,
            model,
            model_preferences,
            on_chunk,
        )

    def get_budget_error(self, depth: int, client: BaseLM) -> str | None:
        """Return token budget error text if a budget is set and exceeded; otherwise None."""
        max_tokens = self.max_root_tokens if depth == 0 else self.max_sub_tokens
        if max_tokens is None:
            return None

        total_tokens = client.get_total_tokens()
        if total_tokens <= max_tokens:
            return None

        bucket_name = "root" if depth == 0 else "sub"
        return f"Token budget exceeded for {bucket_name} calls: {total_tokens} > {max_tokens}"

    def __enter__(self) -> "LMHandler":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.stop()
        return False

    def get_usage_summary(self) -> UsageSummary:
        """Get the usage summary for all clients, merged into a single dict."""
        merged: dict[str, Any] = {}
        # Include default client
        default_summary = self.default_client.get_usage_summary()
        merged.update(default_summary.model_usage_summaries)
        # Include other backend client if it exists
        if self.other_backend_client is not None:
            other_summary = self.other_backend_client.get_usage_summary()
            merged.update(other_summary.model_usage_summaries)
        # Include all registered clients
        for client in self.clients.values():
            client_summary = client.get_usage_summary()
            merged.update(client_summary.model_usage_summaries)
        return UsageSummary(model_usage_summaries=merged)
