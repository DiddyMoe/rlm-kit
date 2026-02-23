"""RLM completion orchestration tools for RLM MCP Gateway."""

import os
from typing import Any, cast

from rlm.core.rlm import RLM, RLMConfig
from rlm.mcp_gateway.constants import MAX_SPAN_LINES
from rlm.mcp_gateway.session import SessionManager


class CompleteTools:
    """RLM completion orchestration tools."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize complete tools.

        Args:
            session_manager: Session manager instance
        """
        self.session_manager = session_manager

    def _resolve_backend_configuration(self) -> tuple[str, dict[str, Any]]:
        """Resolve backend configuration from environment with fail-fast validation."""
        backend = os.getenv("RLM_BACKEND", "openai")
        model_name = os.getenv("RLM_MODEL_NAME")

        backend_config_map: dict[str, tuple[str, str]] = {
            "openai": ("OPENAI_API_KEY", "gpt-4o-mini"),
            "anthropic": ("ANTHROPIC_API_KEY", "claude-3-5-sonnet-20241022"),
        }

        backend_config = backend_config_map.get(backend)
        if backend_config is None:
            raise ValueError(
                f"Unsupported RLM_BACKEND '{backend}'. Supported backends: {', '.join(sorted(backend_config_map))}."
            )

        api_key_env_var, default_model_name = backend_config
        api_key = os.getenv(api_key_env_var)
        if not api_key:
            raise ValueError(
                f"API key not found for backend '{backend}'. Set {api_key_env_var} environment variable."
            )

        backend_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "model_name": model_name or default_model_name,
        }
        return backend, backend_kwargs

    def _validate_constraints(self, constraints: dict[str, Any] | None) -> str | None:
        if not constraints:
            return None

        max_span_size = constraints.get("max_span_size", MAX_SPAN_LINES)
        if max_span_size > MAX_SPAN_LINES:
            return f"Max span size too large: {max_span_size} > {MAX_SPAN_LINES}"
        return None

    def _resolve_max_iterations(
        self, budgets: dict[str, Any] | None, default_max_iterations: int
    ) -> int:
        if not budgets:
            return default_max_iterations
        return budgets.get("max_iterations", default_max_iterations)

    def _create_rlm_instance(
        self, backend: str, backend_kwargs: dict[str, Any], max_iterations: int
    ) -> RLM:
        config = RLMConfig(
            backend=cast(Any, backend),
            backend_kwargs=backend_kwargs,
            environment="local",
            max_iterations=min(max_iterations, 10),
            verbose=False,
        )
        return RLM(config)

    def _build_structured_answer(self, response: str) -> dict[str, Any]:
        summary = response[:2000] + "..." if len(response) > 2000 else response
        return {
            "summary": summary,
            "citations": [],
            "confidence": None,
        }

    def _build_mcp_app_payload(self, result: Any, session_id: str, task: str) -> dict[str, Any]:
        usage_dict = result.usage_summary.to_dict()
        response_preview = (
            result.response[:1200] + "..." if len(result.response) > 1200 else result.response
        )
        return {
            "type": "rlm.trajectory.summary.v1",
            "title": "RLM Trajectory Summary",
            "version": "1.0.0",
            "data": {
                "response_preview": response_preview,
                "execution_time": result.execution_time,
                "usage": usage_dict,
                "session_id": session_id,
                "timeline": [
                    {
                        "event": "completion_started",
                        "timestamp": 0,
                        "details": {"task": task[:240]},
                    },
                    {
                        "event": "completion_finished",
                        "timestamp": result.execution_time,
                        "details": {"response_chars": len(result.response)},
                    },
                ],
                "views": [
                    {
                        "id": "summary",
                        "type": "markdown",
                        "title": "Summary",
                        "content": result.response,
                    },
                    {
                        "id": "usage",
                        "type": "table",
                        "title": "Token Usage",
                        "columns": ["model", "calls", "input_tokens", "output_tokens"],
                        "rows": [
                            [
                                model_name,
                                model_usage.get("total_calls", 0),
                                model_usage.get("total_input_tokens", 0),
                                model_usage.get("total_output_tokens", 0),
                            ]
                            for model_name, model_usage in usage_dict.get(
                                "model_usage_summaries", {}
                            ).items()
                        ],
                    },
                ],
            },
        }

    def _build_completion_output(
        self,
        result: Any,
        session_id: str,
        response_format: str,
        task: str,
    ) -> dict[str, Any]:
        output: dict[str, Any] = {
            "success": True,
            "answer": result.response,
            "usage": result.usage_summary.to_dict(),
            "execution_time": result.execution_time,
            "resource_link": {
                "type": "resource_link",
                "uri": f"rlm://sessions/{session_id}/trajectory",
                "name": f"RLM Trajectory {session_id}",
                "mimeType": "application/json",
            },
            "instructions": (
                "RLM reasoning completed. The response above is the result of recursive "
                "reasoning over the task. For further exploration, use rlm.span.read "
                "with bounded spans to examine specific code sections."
            ),
        }
        if response_format == "structured":
            output["structured_answer"] = self._build_structured_answer(result.response)
        if response_format == "mcp_app":
            output["app"] = self._build_mcp_app_payload(result, session_id, task)
        return output

    def complete(
        self,
        session_id: str,
        task: str,
        budgets: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        response_format: str = "text",
    ) -> dict[str, Any]:
        """Execute RLM completion with strict budgets.

        For local IDE integration, this actually executes RLM reasoning with bounded execution.
        The RLM uses the local environment for fast, seamless integration.

        Args:
            response_format: "text" (default), "structured", or "mcp_app".
                - "structured": includes summary/citations/confidence fields.
                - "mcp_app": includes an app-ready payload for trajectory visualization.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        constraint_error = self._validate_constraints(constraints)
        if constraint_error:
            return {"success": False, "error": constraint_error}

        max_iterations = self._resolve_max_iterations(budgets, session.config.max_iterations)

        try:
            backend, backend_kwargs = self._resolve_backend_configuration()
            rlm = self._create_rlm_instance(backend, backend_kwargs, max_iterations)
            result = rlm.completion(task)

            session.tool_call_count += 1
            return self._build_completion_output(result, session_id, response_format, task)
        except Exception as e:
            session.tool_call_count += 1
            return {"success": False, "error": f"RLM execution failed: {str(e)}"}
