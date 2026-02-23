"""RLM MCP Gateway Server - Modular implementation."""

import argparse
import asyncio
import hashlib
import importlib
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

_gateway_log = logging.getLogger("rlm.mcp_gateway")


@dataclass(frozen=True)
class ChunkCreateConfig:
    strategy: str = "line_based"
    chunk_size: int = 100
    overlap: int = 10
    budget: int = 10

    @classmethod
    def from_arguments(cls, arguments: dict[str, object]) -> "ChunkCreateConfig":
        strategy_value = arguments.get("strategy")
        chunk_size_value = arguments.get("chunk_size")
        overlap_value = arguments.get("overlap")
        budget_value = arguments.get("budget")
        return cls(
            strategy=strategy_value if isinstance(strategy_value, str) else "line_based",
            chunk_size=chunk_size_value if isinstance(chunk_size_value, int) else 100,
            overlap=overlap_value if isinstance(overlap_value, int) else 10,
            budget=budget_value if isinstance(budget_value, int) else 10,
        )


@dataclass(frozen=True)
class OAuthConfig:
    introspection_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


@dataclass(frozen=True)
class HttpServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    repo_path: str | None = None
    api_key: str | None = None
    oauth: OAuthConfig | None = None


mcp_module: Any | None
try:
    mcp_module = importlib.import_module("mcp")
except ImportError:
    mcp_module = None

if mcp_module is not None:
    Tool = cast(Any, getattr(mcp_module, "Tool", Any))
    mcp_server_module = importlib.import_module("mcp.server")
    Server = cast(Any, getattr(mcp_server_module, "Server", Any))
    stdio_server = cast(
        Any, getattr(importlib.import_module("mcp.server.stdio"), "stdio_server", None)
    )
    mcp_types_module = importlib.import_module("mcp.types")
    GetPromptResult = cast(Any, getattr(mcp_types_module, "GetPromptResult", Any))
    Prompt = cast(Any, getattr(mcp_types_module, "Prompt", Any))
    PromptArgument = cast(Any, getattr(mcp_types_module, "PromptArgument", Any))
    PromptMessage = cast(Any, getattr(mcp_types_module, "PromptMessage", Any))
    TextContent = cast(Any, getattr(mcp_types_module, "TextContent", Any))
    mcp_available = True
else:
    mcp_available = False

    class Tool:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class Prompt:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class PromptArgument:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class PromptMessage:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class TextContent:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class GetPromptResult:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class Server:
        def __init__(self, _name: str) -> None:
            self._name = _name

        @staticmethod
        def _decorator() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def wrap(function: Callable[..., Any]) -> Callable[..., Any]:
                return function

            return wrap

        def list_tools(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

        def call_tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

        def list_resources(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

        def read_resource(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

        def list_prompts(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

        def get_prompt(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._decorator()

    stdio_server = None

uvicorn: Any | None
FastAPI: Any | None
Header: Any | None
HTTPException: Any | None
Request: Any | None
CORSMiddleware: Any | None
try:
    uvicorn = importlib.import_module("uvicorn")
    fastapi_module = importlib.import_module("fastapi")
    FastAPI = cast(Any, getattr(fastapi_module, "FastAPI", Any))
    Header = cast(Any, getattr(fastapi_module, "Header", Any))
    HTTPException = cast(Any, getattr(fastapi_module, "HTTPException", Any))
    Request = cast(Any, getattr(fastapi_module, "Request", Any))
    cors_module = importlib.import_module("fastapi.middleware.cors")
    CORSMiddleware = cast(Any, getattr(cors_module, "CORSMiddleware", Any))
except ImportError:
    uvicorn = None
    FastAPI = None
    Header = None
    HTTPException = None
    Request = None
    CORSMiddleware = None

HTTP_AVAILABLE: bool = uvicorn is not None and FastAPI is not None

# Gateway imports (after optional deps so E402 is intentional)
from rlm.clients import get_client  # noqa: E402
from rlm.core.comms_utils import normalize_model_preferences  # noqa: E402
from rlm.core.lm_handler import LMHandler  # noqa: E402
from rlm.mcp_gateway.auth import GatewayAuth  # noqa: E402
from rlm.mcp_gateway.constants import (  # noqa: E402
    MAX_CHUNK_BYTES,
    MAX_EXEC_MEMORY_MB,
    MAX_EXEC_TIMEOUT_MS,
    MAX_SPAN_BYTES,
)
from rlm.mcp_gateway.handles import HandleManager  # noqa: E402
from rlm.mcp_gateway.provenance import ProvenanceTracker  # noqa: E402
from rlm.mcp_gateway.session import Session, SessionManager  # noqa: E402
from rlm.mcp_gateway.tools import (  # noqa: E402
    ChunkTools,
    CompleteTools,
    ExecTools,
    FilesystemTools,
    ProvenanceTools,
    SearchTools,
    SessionTools,
    SpanTools,
)
from rlm.mcp_gateway.tools.helpers import load_canary_token  # noqa: E402
from rlm.mcp_gateway.validation import PathValidator  # noqa: E402


class RLMMCPGateway:
    """RLM MCP Gateway Server with strict tool contract."""

    def __init__(
        self,
        repo_root: str | None = None,
        api_key: str | None = None,
        oauth_introspection_url: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
    ) -> None:
        """
        Initialize the RLM MCP Gateway.

        Args:
            repo_root: Path to repository root. If None, uses script location (local mode).
            api_key: Optional API key for authentication (required for remote mode).
        """
        self.repo_root = self._resolve_repo_root(repo_root)

        self.api_key = api_key or os.getenv("RLM_GATEWAY_API_KEY")
        self.auth_manager = GatewayAuth(
            api_key=self.api_key,
            oauth_introspection_url=oauth_introspection_url
            or os.getenv("RLM_GATEWAY_OAUTH_INTROSPECTION_URL"),
            oauth_client_id=oauth_client_id or os.getenv("RLM_GATEWAY_OAUTH_CLIENT_ID"),
            oauth_client_secret=oauth_client_secret or os.getenv("RLM_GATEWAY_OAUTH_CLIENT_SECRET"),
        )

        self.session_manager = SessionManager()
        self.handle_manager = HandleManager()
        self.path_validator = PathValidator()
        self.provenance_tracker = ProvenanceTracker()
        self.canary_token = load_canary_token(self.repo_root)
        self._init_tool_modules()

    @staticmethod
    def _resolve_repo_root(repo_root: str | None) -> Path:
        if repo_root:
            resolved = Path(repo_root).resolve()
            if not resolved.exists():
                raise ValueError(f"Repository root does not exist: {repo_root}")
            return resolved

        try:
            _repo_root = importlib.import_module("path_utils").REPO_ROOT
            return Path(str(_repo_root))
        except ImportError:
            current = Path(__file__).resolve().parent
            for _ in range(30):
                if (current / "pyproject.toml").is_file():
                    return current
                parent = current.parent
                if parent == current:
                    return Path(__file__).resolve().parents[2]
                current = parent
            return Path(__file__).resolve().parents[2]

    def _init_tool_modules(self) -> None:
        self.session_tools = SessionTools(self.session_manager, self.repo_root)
        self.filesystem_tools = FilesystemTools(
            self.session_manager, self.path_validator, self.repo_root
        )
        self.span_tools = SpanTools(
            self.session_manager,
            self.handle_manager,
            self.path_validator,
            self.provenance_tracker,
            self.repo_root,
            self.canary_token,
        )
        self.chunk_tools = ChunkTools(
            self.session_manager,
            self.handle_manager,
            self.path_validator,
            self.provenance_tracker,
            self.repo_root,
            self.canary_token,
        )
        self.search_tools = SearchTools(self.session_manager, self.path_validator, self.repo_root)
        self.exec_tools = ExecTools(self.session_manager)
        self.complete_tools = CompleteTools(self.session_manager)
        self.provenance_tools = ProvenanceTools(self.session_manager)

    def _validate_auth(self, api_key: str | None) -> bool:
        """Validate API key for remote mode."""
        return self.auth_manager.validate(api_key)

    def validate_auth(self, api_key: str | None) -> bool:
        """Public auth validation wrapper for request handlers."""
        return self._validate_auth(api_key)

    # Delegate methods to tool modules
    def session_create(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new RLM session."""
        return self.session_tools.session_create(config)

    def session_close(self, session_id: str) -> dict[str, Any]:
        """Close a session."""
        return self.session_tools.session_close(session_id)

    def roots_set(self, session_id: str, roots: list[str]) -> dict[str, Any]:
        """Set allowed root directories for a session."""
        return self.session_tools.roots_set(session_id, roots)

    def fs_list(
        self, session_id: str, root: str, depth: int = 2, patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """List directory contents (metadata only, no content)."""
        return self.filesystem_tools.fs_list(session_id, root, depth, patterns)

    def fs_handle_create(self, session_id: str, file_path: str) -> dict[str, Any]:
        """Create a file handle from a file path."""
        return self.filesystem_tools.fs_handle_create(session_id, file_path, self.handle_manager)

    def fs_manifest(self, session_id: str, root: str) -> dict[str, Any]:
        """Get file manifest (hashes and sizes only)."""
        return self.filesystem_tools.fs_manifest(session_id, root)

    def span_read(
        self,
        session_id: str,
        file_handle: str,
        start_line: int,
        end_line: int,
        max_bytes: int = MAX_SPAN_BYTES,
    ) -> dict[str, Any]:
        """Read a bounded span of a file."""
        return self.span_tools.span_read(session_id, file_handle, start_line, end_line, max_bytes)

    def chunk_create(
        self,
        session_id: str,
        file_handle: str,
        chunk_config: ChunkCreateConfig | None = None,
        **chunk_options: object,
    ) -> dict[str, Any]:
        """Create chunk IDs for a file."""
        resolved_chunk_config = (
            chunk_config
            if chunk_config is not None
            else ChunkCreateConfig.from_arguments(chunk_options)
        )
        return self.chunk_tools.chunk_create(
            session_id,
            file_handle,
            resolved_chunk_config.strategy,
            resolved_chunk_config.chunk_size,
            resolved_chunk_config.overlap,
            resolved_chunk_config.budget,
        )

    def chunk_get(
        self, session_id: str, chunk_id: str, max_bytes: int = MAX_CHUNK_BYTES
    ) -> dict[str, Any]:
        """Get a chunk by ID."""
        return self.chunk_tools.chunk_get(session_id, chunk_id, max_bytes)

    def search_query(
        self,
        session_id: str,
        query: str,
        scope: str,
        k: int = 5,
        include_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Semantic search returning span references only."""
        return self.search_tools.search_query(session_id, query, scope, k, include_patterns)

    def search_regex(
        self,
        session_id: str,
        pattern: str,
        scope: str,
        k: int = 10,
        include_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Regex search returning span references only."""
        return self.search_tools.search_regex(session_id, pattern, scope, k, include_patterns)

    def exec_run(
        self,
        session_id: str,
        code: str,
        timeout_ms: int = MAX_EXEC_TIMEOUT_MS,
        memory_limit_mb: int = MAX_EXEC_MEMORY_MB,
    ) -> dict[str, Any]:
        """Execute safe code in isolated sandbox."""
        return self.exec_tools.exec_run(session_id, code, timeout_ms, memory_limit_mb)

    def complete(
        self,
        session_id: str,
        task: str,
        budgets: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        response_format: str = "text",
    ) -> dict[str, Any]:
        """Execute RLM completion with strict budgets."""
        return self.complete_tools.complete(session_id, task, budgets, constraints, response_format)

    def provenance_report(self, session_id: str, export_json: bool = False) -> dict[str, Any]:
        """Get complete provenance graph for a session. export_json=True returns export_payload for file/SIEM."""
        return self.provenance_tools.provenance_report(session_id, export_json=export_json)

    def list_resources(self) -> list[dict[str, Any]]:
        """List MCP Resources for session and trajectory inspection."""
        resources: list[dict[str, Any]] = [
            {
                "uri": "rlm://sessions",
                "name": "RLM Sessions",
                "description": "Active RLM sessions and lightweight metadata.",
                "mimeType": "application/json",
            }
        ]
        for session_id in self.session_manager.list_session_ids():
            resources.append(
                {
                    "uri": f"rlm://sessions/{session_id}",
                    "name": f"RLM Session {session_id}",
                    "description": "Session config, budget counters, and roots.",
                    "mimeType": "application/json",
                }
            )
            resources.append(
                {
                    "uri": f"rlm://sessions/{session_id}/trajectory",
                    "name": f"RLM Trajectory {session_id}",
                    "description": "Session provenance and accessed spans.",
                    "mimeType": "application/json",
                }
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read MCP Resource payload by URI."""
        if uri == "rlm://sessions":
            return self._read_sessions_resource()

        if not uri.startswith("rlm://sessions/"):
            raise ValueError(f"Unknown resource URI: {uri}")

        parts = self._parse_session_resource_parts(uri)
        if not parts:
            raise ValueError(f"Invalid resource URI: {uri}")

        session_id = parts[0]
        session = self.session_manager.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        if len(parts) == 1:
            return self._read_session_resource(session)

        if len(parts) == 2 and parts[1] == "trajectory":
            return self._read_trajectory_resource(session_id, session)

        raise ValueError(f"Unknown resource URI: {uri}")

    def _read_sessions_resource(self) -> dict[str, Any]:
        sessions: list[dict[str, Any]] = []
        for session_id in self.session_manager.list_session_ids():
            session = self.session_manager.get_session(session_id)
            if session is None:
                continue
            sessions.append(
                {
                    "session_id": session.session_id,
                    "created_at": session.created_at,
                    "allowed_roots": session.allowed_roots,
                    "tool_call_count": session.tool_call_count,
                    "output_bytes": session.output_bytes,
                }
            )
        return {
            "success": True,
            "sessions": sessions,
        }

    @staticmethod
    def _parse_session_resource_parts(uri: str) -> list[str]:
        suffix = uri.removeprefix("rlm://sessions/")
        return [part for part in suffix.split("/") if part]

    @staticmethod
    def _read_session_resource(session: Session) -> dict[str, Any]:
        return {
            "success": True,
            "session": {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "allowed_roots": session.allowed_roots,
                "tool_call_count": session.tool_call_count,
                "output_bytes": session.output_bytes,
                "config": {
                    "max_depth": session.config.max_depth,
                    "max_iterations": session.config.max_iterations,
                    "max_tool_calls": session.config.max_tool_calls,
                    "timeout_ms": session.config.timeout_ms,
                    "max_output_bytes": session.config.max_output_bytes,
                },
            },
        }

    @staticmethod
    def _read_trajectory_resource(session_id: str, session: Session) -> dict[str, Any]:
        return {
            "success": True,
            "session_id": session_id,
            "provenance": [item.to_dict() for item in session.provenance or []],
            "accessed_spans": {
                file_path: [[start, end] for start, end in sorted(spans)]
                for file_path, spans in (session.accessed_spans or {}).items()
            },
        }


# ============================================================================
# MCP Server Setup
# ============================================================================

# Global gateway instance (initialized based on mode)
gateway: RLMMCPGateway | None = None
gateway_instance: RLMMCPGateway | None = None
server = Server("rlm-mcp-gateway")

_COMPLETE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "answer": {"type": "string"},
        "usage": {"type": "object"},
        "execution_time": {"type": ["number", "null"]},
        "response_format": {"type": "string"},
        "model": {"type": ["string", "null"]},
        "error": {"type": ["string", "null"]},
    },
    "required": ["success", "answer", "usage", "response_format"],
}

_SEARCH_QUERY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "start_line": {"type": "number"},
                    "end_line": {"type": "number"},
                    "relevance_score": {"type": "number"},
                    "snippet": {"type": "string"},
                    "snippet_hash": {"type": "string"},
                },
                "required": ["file_path", "start_line", "end_line"],
            },
        },
        "error": {"type": ["string", "null"]},
    },
    "required": ["success", "results"],
}

_FS_LIST_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "path": {"type": "string"},
                    "size": {"type": ["number", "null"]},
                    "hash": {"type": ["string", "null"]},
                    "item_count": {"type": ["number", "null"]},
                    "message": {"type": ["string", "null"]},
                },
                "required": ["type"],
            },
        },
        "error": {"type": ["string", "null"]},
    },
    "required": ["success", "entries"],
}


def _infer_primary_model(usage: dict[str, Any]) -> str | None:
    model_usage = usage.get("model_usage_summaries")
    if not isinstance(model_usage, dict) or not model_usage:
        return None
    keys = list(cast(dict[str, Any], model_usage).keys())
    return str(keys[0]) if keys else None


_TOOL_NAME_ALIASES: dict[str, str] = {
    "rlm.session.create": "rlm_session_create",
    "rlm.session.close": "rlm_session_close",
    "rlm.roots.set": "rlm_roots_set",
    "rlm.fs.list": "rlm_fs_list",
    "rlm.fs.manifest": "rlm_fs_manifest",
    "rlm.fs.handle.create": "rlm_fs_handle_create",
    "rlm.span.read": "rlm_span_read",
    "rlm.chunk.create": "rlm_chunk_create",
    "rlm.chunk.get": "rlm_chunk_get",
    "rlm.search.query": "rlm_search_query",
    "rlm.search.regex": "rlm_search_regex",
    "rlm.exec.run": "rlm_exec_run",
    "rlm.complete": "rlm_complete",
    "rlm.provenance.report": "rlm_provenance_report",
}

_CANONICAL_TOOL_NAMES: dict[str, str] = {
    **{legacy_name: legacy_name for legacy_name in _TOOL_NAME_ALIASES},
    **{safe_name: legacy_name for legacy_name, safe_name in _TOOL_NAME_ALIASES.items()},
}


def _canonical_tool_name(tool_name: str) -> str:
    """Normalize a tool name to the legacy dotted canonical form."""
    return _CANONICAL_TOOL_NAMES.get(tool_name, tool_name)


def _public_tool_name(tool_name: str) -> str:
    """Return a VS Code-compatible published tool name."""
    return _TOOL_NAME_ALIASES.get(tool_name, tool_name)


CANONICAL_TOOL_NAMES: dict[str, str] = _CANONICAL_TOOL_NAMES
canonical_tool_name: Callable[[str], str] = _canonical_tool_name
public_tool_name: Callable[[str], str] = _public_tool_name


def _build_structured_content(
    tool_name: str,
    tool_result: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    canonical_name = _canonical_tool_name(tool_name)
    builders: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
        "rlm.complete": _build_complete_structured_content,
        "rlm.search.query": _build_search_query_structured_content,
        "rlm.fs.list": _build_fs_list_structured_content,
    }
    builder = builders.get(canonical_name)
    if builder is None:
        return None
    return builder(tool_result, arguments)


def _build_complete_structured_content(
    tool_result: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    success = bool(tool_result.get("success", False))
    usage_raw: Any = tool_result.get("usage") if success else {}
    usage_dict = cast(dict[str, Any], usage_raw) if isinstance(usage_raw, dict) else {}
    return {
        "success": success,
        "answer": tool_result.get("answer", "") if success else "",
        "usage": usage_dict,
        "execution_time": tool_result.get("execution_time") if success else None,
        "response_format": str(arguments.get("response_format", "text")),
        "model": _infer_primary_model(usage_dict),
        "error": tool_result.get("error") if not success else None,
    }


def _build_search_query_structured_content(
    tool_result: dict[str, Any],
    _: dict[str, Any],
) -> dict[str, Any]:
    success = bool(tool_result.get("success", False))
    results_raw: Any = tool_result.get("results") if success else []
    results = cast(list[Any], results_raw) if isinstance(results_raw, list) else []
    return {
        "success": success,
        "results": results,
        "error": tool_result.get("error") if not success else None,
    }


def _build_fs_list_structured_content(
    tool_result: dict[str, Any],
    _: dict[str, Any],
) -> dict[str, Any]:
    success = bool(tool_result.get("success", False))
    entries_raw: Any = tool_result.get("entries") if success else []
    entries = cast(list[Any], entries_raw) if isinstance(entries_raw, list) else []
    return {
        "success": success,
        "entries": entries,
        "error": tool_result.get("error") if not success else None,
    }


def _make_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
    annotations: dict[str, Any] | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    }
    if output_schema is not None:
        kwargs["outputSchema"] = output_schema
    if annotations is not None:
        annotation_title = annotations.get("title")
        if isinstance(annotation_title, str) and annotation_title:
            kwargs["title"] = annotation_title

    if annotations is not None:
        try:
            return Tool(**kwargs, annotations=annotations)
        except TypeError:
            fallback_kwargs = kwargs.copy()
            fallback_kwargs.pop("title", None)
            try:
                return Tool(**fallback_kwargs, annotations=annotations)
            except TypeError:
                return Tool(**fallback_kwargs)
    return Tool(**kwargs)


_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "rlm.session.create",
        "description": "Create a new RLM session. Call this first; then set roots before any fs/list/span/search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "max_depth": {"type": "number", "default": 10},
                        "max_iterations": {"type": "number", "default": 30},
                        "max_tool_calls": {"type": "number", "default": 100},
                        "timeout_ms": {"type": "number", "default": 300000},
                        "max_output_bytes": {"type": "number", "default": 10485760},
                    },
                }
            },
        },
        "annotations": {
            "title": "Create RLM Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.session.close",
        "description": "Close an RLM session",
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string", "description": "Session ID"}},
            "required": ["session_id"],
        },
        "annotations": {
            "title": "Close RLM Session",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.roots.set",
        "description": "Set allowed root paths for this session. Required before fs.list, fs.handle.create, span.read, or search. Paths are relative to repo root (e.g. roots=['rlm/core']).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "roots": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of allowed root paths",
                },
            },
            "required": ["session_id", "roots"],
        },
        "annotations": {
            "title": "Set Session Roots",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.fs.list",
        "description": "List directory contents (metadata only: names, types; no file content). Use after roots.set. For content use span.read or chunk.get.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "root": {"type": "string"},
                "depth": {"type": "number", "default": 2},
                "patterns": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["session_id", "root"],
        },
        "output_schema": _FS_LIST_OUTPUT_SCHEMA,
        "annotations": {
            "title": "List Filesystem Metadata",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.fs.manifest",
        "description": "Get file manifest (hashes and sizes only)",
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}, "root": {"type": "string"}},
            "required": ["session_id", "root"],
        },
        "annotations": {
            "title": "Get Filesystem Manifest",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.fs.handle.create",
        "description": "Create a file handle from a file path",
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}, "file_path": {"type": "string"}},
            "required": ["session_id", "file_path"],
        },
        "annotations": {
            "title": "Create File Handle",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.span.read",
        "description": "Read a bounded line range of a file (max 200 lines/8KB). Use for specific line ranges. For pre-split chunks use chunk.get; for finding relevant spots use search.query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "file_handle": {"type": "string"},
                "start_line": {"type": "number"},
                "end_line": {"type": "number"},
                "max_bytes": {"type": "number", "default": 8192},
            },
            "required": ["session_id", "file_handle", "start_line", "end_line"],
        },
        "annotations": {
            "title": "Read File Span",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.chunk.create",
        "description": "Create chunk IDs for a file (line-based or overlap). Use chunk.get to read a chunk by ID. Prefer span.read for single range; chunks for repeated access by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "file_handle": {"type": "string"},
                "strategy": {"type": "string", "default": "line_based"},
                "chunk_size": {"type": "number", "default": 100},
                "overlap": {"type": "number", "default": 10},
                "budget": {"type": "number", "default": 10},
            },
            "required": ["session_id", "file_handle"],
        },
        "annotations": {
            "title": "Create Chunks",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.chunk.get",
        "description": "Get chunk content by ID (max 200 lines/8KB). Use after chunk.create. For ad-hoc line ranges use span.read; for finding where to look use search.query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "chunk_id": {"type": "string"},
                "max_bytes": {"type": "number", "default": 8192},
            },
            "required": ["session_id", "chunk_id"],
        },
        "annotations": {
            "title": "Get Chunk",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.search.query",
        "description": "Semantic search over repo; returns references (path, line range) only, not full content. Use to find relevant files/ranges; then span.read or chunk.get to read content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "query": {"type": "string"},
                "scope": {"type": "string"},
                "k": {"type": "number", "default": 5},
                "include_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional glob patterns (e.g. ['*.py', '*.ts', '*.md'])",
                },
            },
            "required": ["session_id", "query", "scope"],
        },
        "output_schema": _SEARCH_QUERY_OUTPUT_SCHEMA,
        "annotations": {
            "title": "Semantic Search",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.search.regex",
        "description": "Regex search over repo; returns references (path, line range) only, not full content. Use to find matches; then span.read to read those ranges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "pattern": {"type": "string"},
                "scope": {"type": "string"},
                "k": {"type": "number", "default": 10},
                "include_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional glob patterns (e.g. ['*.py', '*.ts', '*.md'])",
                },
            },
            "required": ["session_id", "pattern", "scope"],
        },
        "annotations": {
            "title": "Regex Search",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.exec.run",
        "description": "Execute safe code in isolated sandbox (network/process denied)",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "code": {"type": "string"},
                "timeout_ms": {"type": "number", "default": 5000},
                "memory_limit_mb": {"type": "number", "default": 256},
            },
            "required": ["session_id", "code"],
        },
        "annotations": {
            "title": "Execute Sandbox Code",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.complete",
        "description": "Execute RLM completion with strict budgets (returns plan, not full dumps). Use response_format='structured' for summary/citations/confidence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "task": {"type": "string"},
                "response_format": {
                    "type": "string",
                    "enum": ["text", "structured", "mcp_app"],
                    "default": "text",
                    "description": "Use 'structured' for JSON summary/citations/confidence, or 'mcp_app' for app-ready structured payload.",
                },
                "budgets": {
                    "type": "object",
                    "properties": {
                        "max_depth": {"type": "number"},
                        "max_iterations": {"type": "number"},
                        "max_tool_calls": {"type": "number"},
                        "max_output_bytes": {"type": "number"},
                    },
                },
                "constraints": {
                    "type": "object",
                    "properties": {
                        "allowed_roots": {"type": "array", "items": {"type": "string"}},
                        "max_span_size": {"type": "number"},
                    },
                },
            },
            "required": ["session_id", "task"],
        },
        "output_schema": _COMPLETE_OUTPUT_SCHEMA,
        "annotations": {
            "title": "Run RLM Completion",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "rlm.provenance.report",
        "description": "Get complete provenance graph for a session. Use export_json=true for JSON string to save (audit/SIEM).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "export_json": {"type": "boolean", "default": False},
            },
            "required": ["session_id"],
        },
        "annotations": {
            "title": "Get Provenance Report",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
]

TOOL_SPECS: list[dict[str, Any]] = _TOOL_SPECS


@server.list_tools()
async def handle_list_tools() -> list[Any]:
    """List available RLM tools."""
    return [
        _make_tool(
            name=_public_tool_name(str(spec["name"])),
            description=str(spec["description"]),
            input_schema=cast(dict[str, Any], spec["input_schema"]),
            output_schema=cast(dict[str, Any] | None, spec.get("output_schema")),
            annotations=cast(dict[str, Any] | None, spec.get("annotations")),
        )
        for spec in _TOOL_SPECS
    ]


# Tool dispatch map for O(1) lookup (optimized for local stdio)
_tool_handlers: dict[str, Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]]


def _tool_to_method_name(tool_name: str) -> str:
    canonical_name = _canonical_tool_name(tool_name)
    if not canonical_name.startswith("rlm."):
        raise ValueError(f"Unsupported tool prefix: {tool_name}")
    return canonical_name.removeprefix("rlm.").replace(".", "_")


def _tool_default_values(spec: dict[str, Any]) -> dict[str, Any]:
    input_schema = cast(dict[str, Any], spec.get("input_schema", {}))
    properties = cast(dict[str, Any], input_schema.get("properties", {}))
    defaults: dict[str, Any] = {}
    for param_name, config in properties.items():
        if isinstance(config, dict) and "default" in config:
            defaults[param_name] = config["default"]
    return defaults


def _build_handler_from_spec(
    spec: dict[str, Any],
) -> Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]:
    method_name = _tool_to_method_name(str(spec["name"]))
    input_schema = cast(dict[str, Any], spec.get("input_schema", {}))
    properties = cast(dict[str, Any], input_schema.get("properties", {}))
    required = set(cast(list[str], input_schema.get("required", [])))
    defaults = _tool_default_values(spec)
    ordered_params = list(properties.keys())

    def handler(gateway_instance: RLMMCPGateway, args: dict[str, Any]) -> dict[str, Any]:
        method = getattr(gateway_instance, method_name)
        call_kwargs: dict[str, Any] = {}
        for param in ordered_params:
            if param in required:
                call_kwargs[param] = args[param]
            elif param in defaults:
                call_kwargs[param] = args.get(param, defaults[param])
            else:
                call_kwargs[param] = args.get(param)
        return cast(dict[str, Any], method(**call_kwargs))

    return handler


def _build_tool_handlers() -> dict[str, Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]]:
    """Build tool handler dispatch map for efficient O(1) lookup."""
    handlers: dict[str, Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]] = {
        str(spec["name"]): _build_handler_from_spec(spec) for spec in _TOOL_SPECS
    }
    for legacy_name, safe_name in _TOOL_NAME_ALIASES.items():
        handler = handlers.get(legacy_name)
        if handler is not None:
            handlers[safe_name] = handler
    return handlers


def _error_response(
    *,
    code: str,
    message: str,
    tool: str,
    extra: dict[str, Any] | None = None,
) -> list[Any]:
    payload: dict[str, Any] = {
        "success": False,
        "error": message,
        "error_code": code,
        "tool": tool,
    }
    if extra:
        payload.update(extra)
    return [TextContent(type="text", text=json.dumps(payload))]


def _serialize_tool_result(name: str, result: dict[str, Any], arguments: dict[str, Any]) -> Any:
    is_stdio_mode = gateway is not None
    json_text = json.dumps(
        result,
        indent=None if is_stdio_mode else 2,
        ensure_ascii=False,
        separators=(",", ":") if is_stdio_mode else (", ", ": "),
    )
    structured_content = _build_structured_content(name, result, arguments)
    if structured_content is None:
        return [TextContent(type="text", text=json_text)]

    content_items: list[Any] = [TextContent(type="text", text=json_text)]
    if _canonical_tool_name(name) == "rlm.complete":
        resource_link = result.get("resource_link")
        if isinstance(resource_link, dict):
            content_items.append(resource_link)

    return {
        "content": content_items,
        "structuredContent": structured_content,
    }


serialize_tool_result: Callable[[str, dict[str, Any], dict[str, Any]], Any] = _serialize_tool_result


# Initialize tool handlers at module load (optimized for fast startup)
_tool_handlers = _build_tool_handlers()


def _resolve_sampling_backend() -> tuple[str, dict[str, Any]]:
    """Resolve backend config for sampling bridge calls."""
    backend = os.getenv("RLM_BACKEND", "openai")
    model_name = os.getenv("RLM_MODEL_NAME")

    backend_config_map: dict[str, tuple[str, str]] = {
        "openai": ("OPENAI_API_KEY", "gpt-4o-mini"),
        "anthropic": ("ANTHROPIC_API_KEY", "claude-3-5-sonnet-20241022"),
    }
    backend_config = backend_config_map.get(backend)
    if backend_config is None:
        raise ValueError(
            f"Unsupported RLM_BACKEND '{backend}' for sampling bridge. "
            f"Supported backends: {', '.join(sorted(backend_config_map))}."
        )

    api_key_env_var, default_model = backend_config
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        raise ValueError(
            f"Sampling bridge requires {api_key_env_var} environment variable for backend '{backend}'."
        )

    backend_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model_name": model_name or default_model,
    }
    return backend, backend_kwargs


def _sampling_prompt(messages: list[dict[str, Any]]) -> str:
    """Convert MCP sampling messages into a single prompt string."""
    if not messages:
        raise ValueError("sampling/createMessage requires at least one message")

    def render_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return str(cast(dict[str, Any], content).get("text", ""))
        if isinstance(content, list):
            content_items = cast(list[Any], content)
            return "\n".join(
                str(cast(dict[str, Any], item).get("text", ""))
                if isinstance(item, dict)
                else str(item)
                for item in content_items
            )
        return str(content)

    def render_message(message: dict[str, Any]) -> str:
        role = str(message.get("role", "user"))
        return f"[{role}] {render_content(message.get('content', ''))}"

    rendered_parts = [render_message(message) for message in messages]

    if not rendered_parts:
        raise ValueError("sampling/createMessage received no renderable message content")
    return "\n\n".join(rendered_parts)


def _sampling_create_message(params: dict[str, Any]) -> dict[str, Any]:
    """Bridge MCP sampling/createMessage to configured backend completion.

    This bridge uses model_preferences routing via LMHandler so future MCP
    sampling preference shapes can be applied consistently with gateway routing.
    """
    messages_raw = params.get("messages")
    if not isinstance(messages_raw, list):
        raise ValueError("sampling/createMessage requires a 'messages' list")

    model_preferences = normalize_model_preferences(
        params.get("model_preferences", params.get("modelPreferences"))
    )

    backend, backend_kwargs = _resolve_sampling_backend()
    client = get_client(cast(Any, backend), backend_kwargs)
    lm_handler = LMHandler(client)

    selected_model = lm_handler.resolve_model_name(model_preferences=model_preferences)
    prompt_text = _sampling_prompt(cast(list[dict[str, Any]], messages_raw))
    text = lm_handler.completion(
        prompt_text,
        model=selected_model,
        model_preferences=model_preferences,
    )

    stop_reason = "endTurn" if params.get("maxTokens") is None else "maxTokens"
    return {
        "model": selected_model,
        "role": "assistant",
        "content": {
            "type": "text",
            "text": text,
        },
        "stopReason": stop_reason,
    }


def _build_prompt_templates() -> dict[str, dict[str, Any]]:
    """Build MCP prompt templates for common RLM workflows."""
    return {
        "analyze": _ANALYZE_TEMPLATE,
        "summarize": _SUMMARIZE_TEMPLATE,
        "search": _SEARCH_TEMPLATE,
    }


_ANALYZE_TEMPLATE: dict[str, Any] = {
    "description": "Analyze a file recursively with RLM and produce actionable findings.",
    "arguments": [
        PromptArgument(
            name="path",
            description="Workspace-relative file or directory path to analyze.",
            required=True,
        ),
        PromptArgument(
            name="focus",
            description="Optional analysis focus (e.g. architecture, bugs, performance).",
            required=False,
        ),
    ],
    "template": (
        "Analyze `{path}` recursively using RLM. "
        "Prioritize root-cause findings and include concrete next steps."
    ),
}

_SUMMARIZE_TEMPLATE: dict[str, Any] = {
    "description": "Summarize a codebase area with key architecture and risk notes.",
    "arguments": [
        PromptArgument(
            name="scope",
            description="Workspace-relative directory or glob-like scope to summarize.",
            required=True,
        ),
        PromptArgument(
            name="audience",
            description="Optional audience (e.g. maintainer, reviewer, new contributor).",
            required=False,
        ),
    ],
    "template": (
        "Summarize `{scope}` with architecture, important symbols, and current risks. "
        "Keep it concise and tailored for `{audience}` when provided."
    ),
}

_SEARCH_TEMPLATE: dict[str, Any] = {
    "description": "Search with context decomposition and explain the most relevant matches.",
    "arguments": [
        PromptArgument(
            name="query",
            description="Natural-language or regex-like query to search for.",
            required=True,
        ),
        PromptArgument(
            name="scope",
            description="Optional search scope (path or module area).",
            required=False,
        ),
    ],
    "template": (
        "Search for `{query}`{scope_suffix}. "
        "Use context decomposition to identify the best matches, then explain why they matter."
    ),
}


_PROMPT_TEMPLATES = _build_prompt_templates()


def _prompt_message_text(name: str, arguments: dict[str, str] | None) -> str:
    """Render prompt text from template name and argument values."""
    prompt_data = _PROMPT_TEMPLATES.get(name)
    if prompt_data is None:
        raise ValueError(f"Unknown prompt: {name}")

    args = arguments or {}

    if name == "analyze":
        path = args.get("path", "./")
        focus = args.get("focus")
        focus_suffix = f" Focus on: {focus}." if focus else ""
        return f"{prompt_data['template'].format(path=path)}{focus_suffix}"

    if name == "summarize":
        scope = args.get("scope", "./")
        audience = args.get("audience", "engineering stakeholders")
        return prompt_data["template"].format(scope=scope, audience=audience)

    query = args.get("query", "")
    scope = args.get("scope")
    scope_suffix = f" within `{scope}`" if scope else " across the current workspace"
    return prompt_data["template"].format(query=query, scope_suffix=scope_suffix)


@server.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    """List available MCP prompts for common RLM workflows."""
    return [
        Prompt(
            name=name,
            description=prompt_data["description"],
            arguments=prompt_data["arguments"],
        )
        for name, prompt_data in _PROMPT_TEMPLATES.items()
    ]


@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Return a rendered prompt template for an RLM workflow."""
    prompt_data = _PROMPT_TEMPLATES.get(name)
    if prompt_data is None:
        raise ValueError(f"Unknown prompt: {name}")

    prompt_text = _prompt_message_text(name, arguments)
    return GetPromptResult(
        description=prompt_data["description"],
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=prompt_text),
            )
        ],
    )


async def _resource_list_payload() -> list[dict[str, Any]]:
    current_gateway = gateway if gateway else gateway_instance
    if not current_gateway:
        return []
    return current_gateway.list_resources()


async def _resource_read_payload(uri: str) -> dict[str, Any]:
    current_gateway = gateway if gateway else gateway_instance
    if not current_gateway:
        raise ValueError("Gateway not initialized")

    resource_data = current_gateway.read_resource(uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(resource_data, ensure_ascii=False),
            }
        ]
    }


def _resolve_gateway_for_tool(name: str) -> RLMMCPGateway | list[Any]:
    current_gateway = gateway if gateway else gateway_instance
    if current_gateway:
        return current_gateway
    return _error_response(
        code="GATEWAY_NOT_INIT",
        message="Gateway not initialized",
        tool=name,
    )


def _resolve_tool_handler(name: str) -> Callable[[RLMMCPGateway, dict[str, Any]], Any] | None:
    return _tool_handlers.get(name)


def _execute_tool_handler(
    name: str,
    handler: Callable[[RLMMCPGateway, dict[str, Any]], Any],
    current_gateway: RLMMCPGateway,
    arguments: dict[str, Any],
) -> Any:
    result = handler(current_gateway, arguments)
    if not isinstance(result, dict):
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    result_dict = cast(dict[str, Any], result)
    return _serialize_tool_result(name, result_dict, arguments)


def _handle_tool_exception(name: str, session_id: str, error: Exception) -> Any:
    if isinstance(error, KeyError):
        return _error_response(
            code="MISSING_ARGUMENT",
            message=f"Missing required argument: {error}",
            tool=name,
        )

    if isinstance(error, ValueError):
        return _error_response(
            code="INVALID_ARGUMENT",
            message=f"Invalid argument: {error}",
            tool=name,
        )

    _gateway_log.warning(
        "tool_error tool=%s session_id=%s error=%s",
        name,
        session_id or "(none)",
        str(error),
        extra={"tool": name, "session_id": session_id or None, "error": str(error)},
    )
    return _error_response(
        code="EXECUTION_ERROR",
        message=str(error),
        tool=name,
        extra={"error_type": type(error).__name__},
    )


if hasattr(server, "list_resources"):

    @server.list_resources()  # type: ignore[attr-defined]
    async def handle_list_resources() -> list[dict[str, Any]]:
        """List MCP resources for session and trajectory introspection."""
        return await _resource_list_payload()


if hasattr(server, "read_resource"):

    @server.read_resource()  # type: ignore[attr-defined]
    async def handle_read_resource(uri: str) -> dict[str, Any]:
        """Read an MCP resource payload."""
        return await _resource_read_payload(uri)


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """
    Handle tool calls with O(1) dispatch lookup.

    Optimized for local IDE integration (stdio mode):
    - Fast O(1) tool dispatch
    - Efficient JSON serialization (compact for local use)
    - Minimal allocations in hot path
    - Cached gateway instance lookup
    - Structured error responses
    """
    current_gateway = _resolve_gateway_for_tool(name)
    if isinstance(current_gateway, list):
        return current_gateway

    session_id = arguments.get("session_id", "")
    _gateway_log.info(
        "tool_call tool=%s session_id=%s",
        name,
        session_id or "(none)",
        extra={"tool": name, "session_id": session_id or None},
    )
    try:
        handler = _resolve_tool_handler(name)
        if not handler:
            return _error_response(
                code="UNKNOWN_TOOL",
                message=f"Unknown tool: {name}",
                tool=name,
                extra={"available_tools": list(_tool_handlers.keys())[:10]},
            )

        return _execute_tool_handler(name, handler, current_gateway, arguments)

    except Exception as e:
        return _handle_tool_exception(name, session_id, e)


# ============================================================================
# HTTP Server Mode (Remote Isolation)
# ============================================================================

if HTTP_AVAILABLE:
    fastapi_ctor = cast(Any, FastAPI)
    cors_middleware = cast(Any, CORSMiddleware)
    app = fastapi_ctor(title="RLM MCP Gateway", version="1.0.0")

    _MAX_STREAM_EVENTS = 200
    _stream_events: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    _pending_elicitations: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def _push_stream_event(session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event: dict[str, Any] = {
            "type": event_type,
            "timestamp": time.time(),
            "payload": payload,
        }
        queue = _stream_events[session_id]
        queue.append(event)
        while len(queue) > _MAX_STREAM_EVENTS:
            queue.popleft()

    def _push_progress_event(
        session_id: str,
        progress_token: str,
        progress: int,
        message: str,
    ) -> None:
        _push_stream_event(
            session_id,
            "notifications/progress",
            {
                "method": "notifications/progress",
                "params": {
                    "progressToken": progress_token,
                    "progress": progress,
                    "message": message,
                },
            },
        )

    def _drain_stream_events(session_id: str) -> list[dict[str, Any]]:
        queue = _stream_events[session_id]
        events = list(queue)
        queue.clear()
        return events

    def _create_elicitation(
        session_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        elicitation_id = f"elicitation-{uuid4().hex[:10]}"
        request_payload: dict[str, Any] = {
            "id": elicitation_id,
            "title": params.get("title", "RLM clarification required"),
            "message": params.get("message", "Please provide additional input."),
            "options": params.get("options", []),
            "allowFreeform": bool(params.get("allowFreeform", True)),
            "session_id": params.get("session_id"),
            "created_at": time.time(),
            "resolved": False,
            "response": None,
        }
        _pending_elicitations[session_id][elicitation_id] = request_payload
        _push_stream_event(
            session_id,
            "notifications/elicitation/request",
            {
                "method": "notifications/elicitation/request",
                "params": request_payload,
            },
        )
        return {
            "elicitationId": elicitation_id,
            "status": "requested",
        }

    def _respond_elicitation(session_id: str, params: dict[str, Any]) -> dict[str, Any]:
        elicitation_id = params.get("elicitationId")
        if not isinstance(elicitation_id, str) or elicitation_id == "":
            return {
                "status": "error",
                "error": "Missing or invalid elicitationId",
            }

        pending = _pending_elicitations[session_id].get(elicitation_id)
        if pending is None:
            return {
                "status": "error",
                "error": f"Elicitation not found: {elicitation_id}",
            }

        response_payload: dict[str, Any] = {
            "selection": params.get("selection"),
            "text": params.get("text"),
            "submitted_at": time.time(),
        }
        pending["resolved"] = True
        pending["response"] = response_payload

        _push_stream_event(
            session_id,
            "notifications/elicitation/response",
            {
                "method": "notifications/elicitation/response",
                "params": {
                    "elicitationId": elicitation_id,
                    "response": response_payload,
                },
            },
        )
        return {
            "status": "accepted",
            "elicitationId": elicitation_id,
        }

    def _poll_elicitations(session_id: str) -> dict[str, Any]:
        return {
            "elicitations": list(_pending_elicitations[session_id].values()),
        }

    # CORS middleware for IDE connections.
    # Restrict origins via RLM_CORS_ORIGINS env var (comma-separated).
    # Defaults to localhost patterns for development safety.
    cors_env = os.environ.get("RLM_CORS_ORIGINS", "")
    cors_origins: list[str] = (
        [o.strip() for o in cors_env.split(",") if o.strip()]
        if cors_env
        else ["http://localhost:*", "http://127.0.0.1:*", "https://localhost:*"]
    )
    app.add_middleware(
        cors_middleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "rlm-mcp-gateway"}

    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource() -> dict[str, Any]:
        """OAuth 2.1 protected resource metadata for MCP clients."""
        metadata = gateway_instance.auth_manager.oauth_metadata() if gateway_instance else {}
        return {
            "resource": "rlm-mcp-gateway",
            "authorization_servers": [os.getenv("RLM_GATEWAY_OAUTH_AUTHORIZATION_SERVER", "")],
            "introspection_endpoint": metadata.get("introspection_endpoint"),
            "oauth_enabled": metadata.get("oauth_enabled", False),
        }

    @app.get("/.well-known/oauth-authorization-server")
    async def oauth_authorization_server() -> dict[str, Any]:
        """OAuth authorization server metadata proxy for MCP client bootstrap."""
        issuer = os.getenv("RLM_GATEWAY_OAUTH_ISSUER", "")
        authorization_endpoint = os.getenv("RLM_GATEWAY_OAUTH_AUTHORIZATION_ENDPOINT", "")
        token_endpoint = os.getenv("RLM_GATEWAY_OAUTH_TOKEN_ENDPOINT", "")
        return {
            "issuer": issuer,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
        }

    _session_toolset_fingerprints: dict[str, str] = {}

    def _toolset_fingerprint(tools_payload: list[dict[str, Any]]) -> str:
        serialized = json.dumps(tools_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _rpc_tools_list(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = params
        tools = await handle_list_tools()
        tools_dict: list[dict[str, Any]] = []
        for tool in tools:
            if hasattr(tool, "model_dump"):
                tools_dict.append(tool.model_dump())
            elif hasattr(tool, "dict"):
                tools_dict.append(tool.dict())
            else:
                tools_dict.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                )

        current_fingerprint = _toolset_fingerprint(tools_dict)
        previous_fingerprint = _session_toolset_fingerprints.get(session_id)
        if previous_fingerprint != current_fingerprint:
            _session_toolset_fingerprints[session_id] = current_fingerprint
            _push_stream_event(
                session_id,
                "notifications/tools/list_changed",
                {
                    "method": "notifications/tools/list_changed",
                    "toolset_fingerprint": current_fingerprint,
                },
            )
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools_dict}}

    async def _rpc_tools_call(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        progress_token = f"{request_id or 'no-id'}:tools/call"
        _push_progress_event(
            session_id,
            progress_token,
            0,
            f"Starting tool call: {tool_name}",
        )
        result_payload = await handle_call_tool(tool_name, arguments)
        structured_content: dict[str, Any] | None = None
        if isinstance(result_payload, dict):
            payload_dict = cast(dict[str, Any], result_payload)
            raw_content = payload_dict.get("content", [])
            raw_structured = payload_dict.get("structuredContent")
            if isinstance(raw_structured, dict):
                structured_content = cast(dict[str, Any], raw_structured)
        else:
            raw_content = result_payload

        content: list[dict[str, Any]] = []
        for item in raw_content:
            if hasattr(item, "text"):
                content.append({"type": "text", "text": item.text})
            elif isinstance(item, dict):
                content.append(cast(dict[str, Any], item))
            else:
                content.append({"type": "text", "text": str(item)})
        _push_progress_event(
            session_id,
            progress_token,
            100,
            f"Completed tool call: {tool_name}",
        )
        response_result: dict[str, Any] = {"content": content}
        if structured_content is not None:
            response_result["structuredContent"] = structured_content
        return {"jsonrpc": "2.0", "id": request_id, "result": response_result}

    async def _rpc_prompts_list(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = params
        _ = session_id
        prompts = await handle_list_prompts()
        prompts_dict: list[dict[str, Any]] = []
        for prompt in prompts:
            if hasattr(prompt, "model_dump"):
                prompts_dict.append(prompt.model_dump())
            elif hasattr(prompt, "dict"):
                prompts_dict.append(prompt.dict())
            else:
                prompts_dict.append(
                    {
                        "name": prompt.name,
                        "description": prompt.description,
                        "arguments": [
                            {
                                "name": getattr(argument, "name", ""),
                                "description": getattr(argument, "description", ""),
                                "required": bool(getattr(argument, "required", False)),
                            }
                            for argument in cast(list[Any], (prompt.arguments or []))
                        ],
                    }
                )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"prompts": prompts_dict},
        }

    async def _rpc_prompts_get(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = session_id
        prompt_name = params.get("name")
        prompt_arguments = params.get("arguments")
        prompt_result = await handle_get_prompt(prompt_name, prompt_arguments)
        prompt_payload: dict[str, Any]
        if hasattr(prompt_result, "model_dump"):
            prompt_payload = cast(dict[str, Any], prompt_result.model_dump())
        elif hasattr(prompt_result, "dict"):
            prompt_payload = cast(dict[str, Any], prompt_result.dict())
        else:
            prompt_payload = {
                "description": prompt_result.description,
                "messages": [
                    {
                        "role": message.role,
                        "content": {
                            "type": message.content.type,
                            "text": message.content.text,
                        },
                    }
                    for message in prompt_result.messages
                ],
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": prompt_payload}

    async def _rpc_resources_list(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = params
        _ = session_id
        resources = await _resource_list_payload()
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": resources}}

    async def _rpc_resources_read(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = session_id
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "Missing required param: uri"},
            }
        resource_payload = await _resource_read_payload(uri)
        return {"jsonrpc": "2.0", "id": request_id, "result": resource_payload}

    async def _rpc_sampling_create_message(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = session_id
        try:
            sampling_result = _sampling_create_message(params)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": sampling_result,
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"sampling/createMessage failed: {str(e)}",
                },
            }

    async def _rpc_elicitation_create(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        result = _create_elicitation(session_id, params)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    async def _rpc_elicitation_respond(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        result = _respond_elicitation(session_id, params)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    async def _rpc_elicitation_poll(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = params
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _poll_elicitations(session_id),
        }

    async def _rpc_completion_complete(
        request_id: Any,
        params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        _ = session_id
        current_gateway = gateway_instance
        if current_gateway is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Gateway not initialized",
                },
            }

        argument = params.get("argument", {})
        argument_name = argument.get("name")
        argument_value = argument.get("value", "")
        prefix = argument_value if isinstance(argument_value, str) else ""

        suggestions: list[str] = []
        if argument_name == "session_id":
            suggestions = current_gateway.session_manager.list_session_ids(prefix=prefix)
        elif argument_name in {"file_handle", "handle_id"}:
            requested_session_id = params.get("session_id")
            session_filter = requested_session_id if isinstance(requested_session_id, str) else None
            suggestions = current_gateway.handle_manager.list_file_handle_ids(
                prefix=prefix,
                session_id=session_filter,
            )
        elif argument_name == "chunk_id":
            suggestions = current_gateway.handle_manager.list_chunk_ids(prefix=prefix)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "completion": {
                    "values": suggestions[:50],
                }
            },
        }

    _MCP_RPC_HANDLERS: dict[
        str,
        Callable[[Any, dict[str, Any], str], Awaitable[dict[str, Any]]],
    ] = {
        "tools/list": _rpc_tools_list,
        "tools/call": _rpc_tools_call,
        "prompts/list": _rpc_prompts_list,
        "prompts/get": _rpc_prompts_get,
        "resources/list": _rpc_resources_list,
        "resources/read": _rpc_resources_read,
        "sampling/createMessage": _rpc_sampling_create_message,
        "elicitation/create": _rpc_elicitation_create,
        "elicitation/respond": _rpc_elicitation_respond,
        "elicitation/poll": _rpc_elicitation_poll,
        "completion/complete": _rpc_completion_complete,
    }

    async def _dispatch_mcp_rpc(body: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Dispatch an MCP JSON-RPC request body to gateway handlers."""
        if body.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32600, "message": "Invalid MCP protocol message"},
            }

        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        if not isinstance(method, str) or method == "":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"},
            }

        handler = _MCP_RPC_HANDLERS.get(method)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        params_dict = cast(dict[str, Any], params) if isinstance(params, dict) else {}
        return await handler(request_id, params_dict, session_id)

    async def _handle_batch_request(batch_body: list[Any], session_id: str) -> list[dict[str, Any]]:
        _push_stream_event(
            session_id,
            "request.received",
            {
                "method": "batch",
                "request_id": None,
                "batch_size": len(batch_body),
            },
        )

        responses = [await _dispatch_single_batch_item(item, session_id) for item in batch_body]

        _push_stream_event(
            session_id,
            "response.ready",
            {
                "method": "batch",
                "request_id": None,
                "success": True,
                "batch_size": len(batch_body),
            },
        )
        return responses

    async def _dispatch_single_batch_item(item: Any, session_id: str) -> dict[str, Any]:
        """Dispatch a single batch item, returning JSON-RPC response or error."""
        if not isinstance(item, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: batch items must be objects",
                },
            }

        try:
            return await _dispatch_mcp_rpc(cast(dict[str, Any], item), session_id)
        except Exception as item_error:
            return {
                "jsonrpc": "2.0",
                "id": cast(dict[str, Any], item).get("id"),
                "error": {
                    "code": -32603,
                    "message": str(item_error),
                },
            }

    def _extract_api_key(authorization: str | None) -> str | None:
        if authorization and authorization.startswith("Bearer "):
            return authorization[7:]
        return None

    def _request_meta(body: Any) -> tuple[Any, Any]:
        if isinstance(body, dict):
            body_dict = cast(dict[str, Any], body)
            return body_dict.get("method"), body_dict.get("id")
        return None, None

    def _rpc_error_response(session_id: str, body: Any, error: Exception) -> dict[str, Any]:
        request_id = cast(dict[str, Any], body).get("id") if isinstance(body, dict) else None
        _push_stream_event(
            session_id,
            "request.failed",
            {
                "error": str(error),
                "request_id": request_id,
            },
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": str(error)},
            "mcp_session_id": session_id,
        }

    def _validate_mcp_request(
        request: Any,
    ) -> tuple[str, dict[str, Any] | None]:
        """Parse headers and validate auth. Returns (session_id, error_or_None)."""
        request_headers = cast(dict[str, Any], getattr(request, "headers", {}))
        authorization = cast(str | None, request_headers.get("Authorization"))
        mcp_session_id = cast(
            str | None,
            request_headers.get("Mcp-Session-Id") or request_headers.get("mcp-session-id"),
        )

        session_id = mcp_session_id or str(uuid4())
        if not gateway_instance:
            return session_id, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": "Gateway not initialized"},
                "mcp_session_id": session_id,
            }

        api_key = _extract_api_key(authorization)
        if not gateway_instance.validate_auth(api_key):
            return session_id, {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32001, "message": "Invalid API key"},
                "mcp_session_id": session_id,
            }

        return session_id, None

    async def _dispatch_single_rpc_with_events(
        body_dict: dict[str, Any], session_id: str
    ) -> dict[str, Any]:
        """Dispatch single JSON-RPC request with lifecycle stream events."""
        method_name, request_id = _request_meta(body_dict)
        _push_stream_event(
            session_id,
            "request.received",
            {
                "method": method_name,
                "request_id": request_id,
            },
        )

        response = await _dispatch_mcp_rpc(body_dict, session_id)
        _push_stream_event(
            session_id,
            "response.ready",
            {
                "method": method_name,
                "request_id": request_id,
                "success": "error" not in response,
            },
        )
        response["mcp_session_id"] = session_id
        return response

    @app.post("/mcp")
    async def mcp_endpoint(request: Any) -> dict[str, Any] | list[dict[str, Any]]:
        """
        MCP protocol endpoint for remote IDE connections.

        Accepts MCP protocol messages and returns responses.
        """
        session_id, error = _validate_mcp_request(request)
        if error is not None:
            return error

        body: Any = None
        try:
            body = await request.json()

            if not isinstance(body, (dict, list)):
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid request payload"},
                    "mcp_session_id": session_id,
                }

            if isinstance(body, list):
                return await _handle_batch_request(cast(list[Any], body), session_id)

            return await _dispatch_single_rpc_with_events(cast(dict[str, Any], body), session_id)

        except Exception as e:
            return _rpc_error_response(session_id, body, e)

    @app.post("/mcp/messages")
    async def mcp_streamable_messages_endpoint(
        request: Any,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Streamable HTTP-compatible POST endpoint for MCP messages."""
        return await mcp_endpoint(request)

    @app.get("/mcp/messages")
    async def mcp_streamable_messages_stream(request: Any) -> dict[str, Any]:
        """Streamable HTTP-compatible GET endpoint for server-initiated streams.

        This returns queued request/response lifecycle events for the provided
        MCP session identifier.
        """
        request_headers = cast(dict[str, Any], getattr(request, "headers", {}))
        session_id = cast(
            str | None,
            request_headers.get("Mcp-Session-Id") or request_headers.get("mcp-session-id"),
        ) or str(uuid4())
        events = _drain_stream_events(session_id)
        if not events:
            heartbeat_event: dict[str, Any] = {
                "type": "heartbeat",
                "timestamp": time.time(),
                "payload": {"status": "idle"},
            }
            events = [heartbeat_event]
        return {
            "jsonrpc": "2.0",
            "result": {"events": events},
            "mcp_session_id": session_id,
        }


# ============================================================================
# Main Entry Point
# ============================================================================


async def main_stdio() -> None:
    """
    Run the MCP gateway server in stdio mode (local development).

    Optimized for local IDE integration:
    - Fast startup with minimal initialization
    - Efficient stdio communication
    - Low latency for tool calls
    """
    global gateway
    if not gateway:
        # Initialize with default (local mode)
        # Optimized: use script location for fast local access
        gateway = RLMMCPGateway()

    # Use MCP SDK's optimized stdio server for local IDE communication
    if not mcp_available or stdio_server is None:
        raise RuntimeError("MCP stdio server not available")

    server_runtime = cast(Any, server)
    async with stdio_server() as (read_stream, write_stream):
        initialization_options = server_runtime.create_initialization_options()
        await server_runtime.run(read_stream, write_stream, initialization_options)


def main_http(config: HttpServerConfig) -> None:
    """Run the MCP gateway server in HTTP mode (remote isolation)."""
    if not HTTP_AVAILABLE:
        print(
            "ERROR: FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    oauth_config = config.oauth if config.oauth is not None else OAuthConfig()

    global gateway_instance
    gateway_instance = RLMMCPGateway(
        repo_root=config.repo_path,
        api_key=config.api_key,
        oauth_introspection_url=oauth_config.introspection_url,
        oauth_client_id=oauth_config.client_id,
        oauth_client_secret=oauth_config.client_secret,
    )

    print(f"Starting RLM MCP Gateway HTTP server on {config.host}:{config.port}", file=sys.stderr)
    if config.repo_path:
        print(f"Repository root: {config.repo_path}", file=sys.stderr)
    if config.api_key:
        print("Authentication: ENABLED", file=sys.stderr)
    else:
        print("Authentication: DISABLED (not recommended for production)", file=sys.stderr)

    uvicorn_module = cast(Any, uvicorn)
    uvicorn_module.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RLM MCP Gateway Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode: stdio (default, primary method for local IDE integration) or http (remote isolation, optional)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP server host (http mode only)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP server port (http mode only)")
    parser.add_argument(
        "--repo-path",
        help="Repository root path (required for remote isolation, optional for local)",
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication (http mode only, or set RLM_GATEWAY_API_KEY env var)",
    )
    parser.add_argument(
        "--oauth-introspection-url",
        help="OAuth 2.1 introspection endpoint URL for bearer-token validation (http mode)",
    )
    parser.add_argument(
        "--oauth-client-id",
        help="OAuth client ID for introspection endpoint basic auth (optional)",
    )
    parser.add_argument(
        "--oauth-client-secret",
        help="OAuth client secret for introspection endpoint basic auth (optional)",
    )

    args = parser.parse_args()

    if args.mode == "http":
        # HTTP mode (remote isolation): require repo_path and api_key
        if not args.repo_path:
            print(
                "ERROR: --repo-path is required for HTTP mode (remote isolation)", file=sys.stderr
            )
            print(
                "Usage: python scripts/rlm_mcp_gateway.py --mode http --repo-path /repo/rlm-kit --api-key KEY",
                file=sys.stderr,
            )
            sys.exit(1)

        # R4 Compliance: Fail-closed - require API key for remote isolation
        if not args.api_key and not os.getenv("RLM_GATEWAY_API_KEY"):
            print(
                "ERROR: API key required for remote isolation mode (R4 compliance).",
                file=sys.stderr,
            )
            print(
                "Set --api-key or RLM_GATEWAY_API_KEY environment variable.",
                file=sys.stderr,
            )
            print(
                "For local development only, use: --mode stdio",
                file=sys.stderr,
            )
            sys.exit(1)

        main_http(
            HttpServerConfig(
                host=args.host,
                port=args.port,
                repo_path=args.repo_path,
                api_key=args.api_key,
                oauth=OAuthConfig(
                    introspection_url=args.oauth_introspection_url,
                    client_id=args.oauth_client_id,
                    client_secret=args.oauth_client_secret,
                ),
            )
        )
    else:
        # stdio mode: PRIMARY METHOD for seamless local IDE integration
        # No Docker/HTTP overhead - direct local communication for optimal performance
        if args.repo_path:
            gateway = RLMMCPGateway(repo_root=args.repo_path)
        else:
            # Local mode: use script location (default for local development)
            gateway = RLMMCPGateway()
        asyncio.run(main_stdio())
