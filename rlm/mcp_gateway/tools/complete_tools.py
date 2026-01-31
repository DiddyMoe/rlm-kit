"""RLM completion orchestration tools for RLM MCP Gateway."""

import os
from typing import Any

from rlm.core.rlm import RLM
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
            response_format: "text" (default) or "structured". When "structured", the
                return includes structured_answer with summary, citations, confidence.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Check budget
        within_budget, error = self.session_manager.check_budget(session)
        if not within_budget:
            return {"success": False, "error": error}

        # Validate constraints
        if constraints:
            max_span_size = constraints.get("max_span_size", MAX_SPAN_LINES)
            if max_span_size > MAX_SPAN_LINES:
                return {
                    "success": False,
                    "error": f"Max span size too large: {max_span_size} > {MAX_SPAN_LINES}",
                }

        # Extract budget limits
        max_iterations = (
            budgets.get("max_iterations", session.config.max_iterations)
            if budgets
            else session.config.max_iterations
        )
        max_tokens = budgets.get("max_tokens") if budgets else None
        max_cost = budgets.get("max_cost") if budgets else None

        # Execute RLM reasoning with local environment (optimized for IDE integration)
        try:
            # Get backend configuration from environment or use defaults
            backend = os.getenv("RLM_BACKEND", "openai")
            backend_kwargs: dict[str, Any] = {}

            # Load API keys from environment (flattened conditionals)
            api_key: str | None = None
            model_name: str | None = None

            if backend == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                model_name = os.getenv("RLM_MODEL_NAME", "gpt-4o-mini")
            elif backend == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
                model_name = os.getenv("RLM_MODEL_NAME", "claude-3-5-sonnet-20241022")

            # Early return if API key not configured
            if not api_key:
                raise ValueError(
                    f"API key not found for backend '{backend}'. "
                    f"Set {backend.upper()}_API_KEY environment variable."
                )

            backend_kwargs["api_key"] = api_key
            if model_name:
                backend_kwargs["model_name"] = model_name

            # Create RLM instance with local environment (fast, no Docker/HTTP overhead)
            rlm = RLM(
                backend=backend,
                backend_kwargs=backend_kwargs,
                environment="local",  # Use local environment for seamless IDE integration
                max_iterations=min(max_iterations, 10),  # Limit iterations for bounded execution
                max_tokens=max_tokens,
                max_cost=max_cost,
                verbose=False,  # Disable verbose output for cleaner IDE integration
            )

            # Execute RLM completion
            result = rlm.completion(task)

            session.tool_call_count += 1

            out: dict[str, Any] = {
                "success": True,
                "response": result.response,
                "usage": result.usage_summary.to_dict(),
                "execution_time": result.execution_time,
                "instructions": (
                    "RLM reasoning completed. The response above is the result of recursive "
                    "reasoning over the task. For further exploration, use rlm.span.read "
                    "with bounded spans to examine specific code sections."
                ),
            }
            if response_format == "structured":
                # Optional structured output (upstream issue #50): summary, citations, confidence
                summary = (
                    result.response[:2000] + "..."
                    if len(result.response) > 2000
                    else result.response
                )
                out["structured_answer"] = {
                    "summary": summary,
                    "citations": [],  # Could be populated from provenance if needed
                    "confidence": None,  # Optional: model could provide later
                }
            return out
        except Exception as e:
            # Fallback to plan-based approach if RLM execution fails
            plan = [
                {
                    "step": 1,
                    "tool": "rlm.fs.list",
                    "params": {
                        "session_id": session_id,
                        "root": session.allowed_roots[0] if session.allowed_roots else ".",
                    },
                    "description": "List repository structure",
                },
                {
                    "step": 2,
                    "tool": "rlm.search.query",
                    "params": {
                        "session_id": session_id,
                        "query": task,
                        "scope": session.allowed_roots[0] if session.allowed_roots else ".",
                        "k": 5,
                    },
                    "description": "Search for relevant code",
                },
            ]

            session.tool_call_count += 1

            fallback: dict[str, Any] = {
                "success": True,
                "plan": plan,
                "error": f"RLM execution failed, returning plan: {str(e)}",
                "instructions": (
                    "RLM execution encountered an error. The IDE's built-in model should execute "
                    "these tool calls in sequence, using the results to build understanding. "
                    "NEVER attempt to read entire files - use rlm.span.read with bounded spans only."
                ),
                "budgets": budgets or {},
                "constraints": constraints or {},
            }
            if response_format == "structured":
                fallback["structured_answer"] = {
                    "summary": "",
                    "citations": [],
                    "confidence": None,
                }
            return fallback
