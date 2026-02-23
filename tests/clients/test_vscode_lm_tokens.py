from __future__ import annotations

import threading
from typing import Any

from rlm.clients.vscode_lm import VsCodeLM


def test_vscode_lm_tracks_tokens_from_bridge_payload() -> None:
    pending: dict[str, tuple[threading.Event, dict[str, Any]]] = {}

    def send_fn(payload: dict[str, Any]) -> None:
        nonce = str(payload["nonce"])
        event, container = pending[nonce]
        container.update(
            {
                "text": "ok",
                "promptTokens": 12,
                "completionTokens": 7,
            }
        )
        event.set()

    def register_response_fn(nonce: str, event: threading.Event, container: dict[str, Any]) -> None:
        pending[nonce] = (event, container)

    client = VsCodeLM(
        model_name="vscode-lm",
        send_fn=send_fn,
        register_response_fn=register_response_fn,
    )

    result = client.completion("hello")
    summary = client.get_usage_summary().model_usage_summaries["vscode-lm"]

    assert result == "ok"
    assert summary.total_input_tokens == 12
    assert summary.total_output_tokens == 7
