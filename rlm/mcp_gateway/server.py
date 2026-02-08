"""RLM MCP Gateway Server - Modular implementation."""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_gateway_log = logging.getLogger("rlm.mcp_gateway")

# Import MCP SDK
try:
    from mcp import Tool
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# HTTP server support (optional, for remote isolation)
try:
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware

    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

# Gateway imports (after optional deps so E402 is intentional)
from rlm.mcp_gateway.constants import (  # noqa: E402
    MAX_CHUNK_BYTES,
    MAX_EXEC_MEMORY_MB,
    MAX_EXEC_TIMEOUT_MS,
    MAX_SPAN_BYTES,
)
from rlm.mcp_gateway.handles import HandleManager  # noqa: E402
from rlm.mcp_gateway.provenance import ProvenanceTracker  # noqa: E402
from rlm.mcp_gateway.session import SessionManager  # noqa: E402
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

    def __init__(self, repo_root: str | None = None, api_key: str | None = None) -> None:
        """
        Initialize the RLM MCP Gateway.

        Args:
            repo_root: Path to repository root. If None, uses script location (local mode).
            api_key: Optional API key for authentication (required for remote mode).
        """
        if repo_root:
            self.repo_root = Path(repo_root).resolve()
            if not self.repo_root.exists():
                raise ValueError(f"Repository root does not exist: {repo_root}")
        else:
            # Local mode: use path_utils when run from repo (e.g. scripts/rlm_mcp_gateway.py)
            try:
                from path_utils import REPO_ROOT as _repo_root

                self.repo_root = Path(_repo_root)
            except ImportError:
                # Installed package or no path_utils: walk up until pyproject.toml
                _cur = Path(__file__).resolve().parent
                for _ in range(30):
                    if (_cur / "pyproject.toml").is_file():
                        self.repo_root = _cur
                        break
                    _cur, _prev = _cur.parent, _cur
                    if _cur == _prev:
                        self.repo_root = Path(__file__).resolve().parents[2]
                        break
                else:
                    self.repo_root = Path(__file__).resolve().parents[2]  # fallback

        self.api_key = api_key or os.getenv("RLM_GATEWAY_API_KEY")

        # Initialize managers
        self.session_manager = SessionManager()
        self.handle_manager = HandleManager()
        self.path_validator = PathValidator()
        self.provenance_tracker = ProvenanceTracker()

        # Load canary token for bypass detection (if exists in repo)
        self.canary_token = load_canary_token(self.repo_root)

        # Initialize tool modules
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
        if not self.api_key:
            # No auth required (local mode or auth disabled)
            return True
        return api_key == self.api_key

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
        strategy: str = "line_based",
        chunk_size: int = 100,
        overlap: int = 10,
        budget: int = 10,
    ) -> dict[str, Any]:
        """Create chunk IDs for a file."""
        return self.chunk_tools.chunk_create(
            session_id, file_handle, strategy, chunk_size, overlap, budget
        )

    def chunk_get(
        self, session_id: str, chunk_id: str, max_bytes: int = MAX_CHUNK_BYTES
    ) -> dict[str, Any]:
        """Get a chunk by ID."""
        return self.chunk_tools.chunk_get(session_id, chunk_id, max_bytes)

    def search_query(self, session_id: str, query: str, scope: str, k: int = 5) -> dict[str, Any]:
        """Semantic search returning span references only."""
        return self.search_tools.search_query(session_id, query, scope, k)

    def search_regex(
        self, session_id: str, pattern: str, scope: str, k: int = 10
    ) -> dict[str, Any]:
        """Regex search returning span references only."""
        return self.search_tools.search_regex(session_id, pattern, scope, k)

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


# ============================================================================
# MCP Server Setup
# ============================================================================

# Global gateway instance (initialized based on mode)
gateway: RLMMCPGateway | None = None
server = Server("rlm-mcp-gateway")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available RLM tools."""
    return [
        # Session management
        Tool(
            name="rlm.session.create",
            description="Create a new RLM session. Call this first; then set roots before any fs/list/span/search.",
            inputSchema={
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
        ),
        Tool(
            name="rlm.session.close",
            description="Close an RLM session",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string", "description": "Session ID"}},
                "required": ["session_id"],
            },
        ),
        Tool(
            name="rlm.roots.set",
            description="Set allowed root paths for this session. Required before fs.list, fs.handle.create, span.read, or search. Paths are relative to repo root (e.g. roots=['rlm/core']).",
            inputSchema={
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
        ),
        # Filesystem metadata
        Tool(
            name="rlm.fs.list",
            description="List directory contents (metadata only: names, types; no file content). Use after roots.set. For content use span.read or chunk.get.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "root": {"type": "string"},
                    "depth": {"type": "number", "default": 2},
                    "patterns": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["session_id", "root"],
            },
        ),
        Tool(
            name="rlm.fs.manifest",
            description="Get file manifest (hashes and sizes only)",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string"}, "root": {"type": "string"}},
                "required": ["session_id", "root"],
            },
        ),
        Tool(
            name="rlm.fs.handle.create",
            description="Create a file handle from a file path",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string"}, "file_path": {"type": "string"}},
                "required": ["session_id", "file_path"],
            },
        ),
        # Bounded reading
        Tool(
            name="rlm.span.read",
            description="Read a bounded line range of a file (max 200 lines/8KB). Use for specific line ranges. For pre-split chunks use chunk.get; for finding relevant spots use search.query.",
            inputSchema={
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
        ),
        Tool(
            name="rlm.chunk.create",
            description="Create chunk IDs for a file (line-based or overlap). Use chunk.get to read a chunk by ID. Prefer span.read for single range; chunks for repeated access by ID.",
            inputSchema={
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
        ),
        Tool(
            name="rlm.chunk.get",
            description="Get chunk content by ID (max 200 lines/8KB). Use after chunk.create. For ad-hoc line ranges use span.read; for finding where to look use search.query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "chunk_id": {"type": "string"},
                    "max_bytes": {"type": "number", "default": 8192},
                },
                "required": ["session_id", "chunk_id"],
            },
        ),
        # Search
        Tool(
            name="rlm.search.query",
            description="Semantic search over repo; returns references (path, line range) only, not full content. Use to find relevant files/ranges; then span.read or chunk.get to read content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "query": {"type": "string"},
                    "scope": {"type": "string"},
                    "k": {"type": "number", "default": 5},
                },
                "required": ["session_id", "query", "scope"],
            },
        ),
        Tool(
            name="rlm.search.regex",
            description="Regex search over repo; returns references (path, line range) only, not full content. Use to find matches; then span.read to read those ranges.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "pattern": {"type": "string"},
                    "scope": {"type": "string"},
                    "k": {"type": "number", "default": 10},
                },
                "required": ["session_id", "pattern", "scope"],
            },
        ),
        # Provenance
        Tool(
            name="rlm.exec.run",
            description="Execute safe code in isolated sandbox (network/process denied)",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "code": {"type": "string"},
                    "timeout_ms": {"type": "number", "default": 5000},
                    "memory_limit_mb": {"type": "number", "default": 256},
                },
                "required": ["session_id", "code"],
            },
        ),
        Tool(
            name="rlm.complete",
            description="Execute RLM completion with strict budgets (returns plan, not full dumps). Use response_format='structured' for summary/citations/confidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "task": {"type": "string"},
                    "response_format": {
                        "type": "string",
                        "enum": ["text", "structured"],
                        "default": "text",
                        "description": "Use 'structured' for JSON-style summary, citations, confidence.",
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
        ),
        Tool(
            name="rlm.provenance.report",
            description="Get complete provenance graph for a session. Use export_json=true for JSON string to save (audit/SIEM).",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "export_json": {"type": "boolean", "default": False},
                },
                "required": ["session_id"],
            },
        ),
    ]


# Tool dispatch map for O(1) lookup (optimized for local stdio)
_TOOL_HANDLERS: dict[str, Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]] = {}


def _build_tool_handlers() -> dict[str, Callable[[RLMMCPGateway, dict[str, Any]], dict[str, Any]]]:
    """Build tool handler dispatch map for efficient O(1) lookup."""
    return {
        "rlm.session.create": lambda gw, args: gw.session_create(args.get("config")),
        "rlm.session.close": lambda gw, args: gw.session_close(args["session_id"]),
        "rlm.roots.set": lambda gw, args: gw.roots_set(args["session_id"], args["roots"]),
        "rlm.fs.list": lambda gw, args: gw.fs_list(
            args["session_id"],
            args["root"],
            args.get("depth", 2),
            args.get("patterns"),
        ),
        "rlm.fs.manifest": lambda gw, args: gw.fs_manifest(args["session_id"], args["root"]),
        "rlm.fs.handle.create": lambda gw, args: gw.fs_handle_create(
            args["session_id"], args["file_path"]
        ),
        "rlm.span.read": lambda gw, args: gw.span_read(
            args["session_id"],
            args["file_handle"],
            args["start_line"],
            args["end_line"],
            args.get("max_bytes", MAX_SPAN_BYTES),
        ),
        "rlm.chunk.create": lambda gw, args: gw.chunk_create(
            args["session_id"],
            args["file_handle"],
            args.get("strategy", "line_based"),
            args.get("chunk_size", 100),
            args.get("overlap", 10),
            args.get("budget", 10),
        ),
        "rlm.chunk.get": lambda gw, args: gw.chunk_get(
            args["session_id"],
            args["chunk_id"],
            args.get("max_bytes", MAX_CHUNK_BYTES),
        ),
        "rlm.search.query": lambda gw, args: gw.search_query(
            args["session_id"],
            args["query"],
            args["scope"],
            args.get("k", 5),
        ),
        "rlm.search.regex": lambda gw, args: gw.search_regex(
            args["session_id"],
            args["pattern"],
            args["scope"],
            args.get("k", 10),
        ),
        "rlm.exec.run": lambda gw, args: gw.exec_run(
            args["session_id"],
            args["code"],
            args.get("timeout_ms", MAX_EXEC_TIMEOUT_MS),
            args.get("memory_limit_mb", MAX_EXEC_MEMORY_MB),
        ),
        "rlm.complete": lambda gw, args: gw.complete(
            args["session_id"],
            args["task"],
            args.get("budgets"),
            args.get("constraints"),
            args.get("response_format", "text"),
        ),
        "rlm.provenance.report": lambda gw, args: gw.provenance_report(
            args["session_id"], args.get("export_json", False)
        ),
    }


# Initialize tool handlers at module load (optimized for fast startup)
_TOOL_HANDLERS = _build_tool_handlers()


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool calls with O(1) dispatch lookup.

    Optimized for local IDE integration (stdio mode):
    - Fast O(1) tool dispatch
    - Efficient JSON serialization (compact for local use)
    - Minimal allocations in hot path
    - Cached gateway instance lookup
    - Structured error responses
    """
    # Cache gateway instance lookup (optimized for repeated calls)
    current_gateway = gateway if gateway else gateway_instance
    if not current_gateway:
        error_response = json.dumps(
            {"success": False, "error": "Gateway not initialized", "error_code": "GATEWAY_NOT_INIT"}
        )
        return [TextContent(type="text", text=error_response)]

    session_id = arguments.get("session_id", "")
    _gateway_log.info(
        "tool_call tool=%s session_id=%s",
        name,
        session_id or "(none)",
        extra={"tool": name, "session_id": session_id or None},
    )
    try:
        # O(1) tool dispatch using dict lookup (optimized for local IDE)
        handler = _TOOL_HANDLERS.get(name)
        if not handler:
            error_response = json.dumps(
                {
                    "success": False,
                    "error": f"Unknown tool: {name}",
                    "error_code": "UNKNOWN_TOOL",
                    "available_tools": list(_TOOL_HANDLERS.keys())[:10],  # First 10 for reference
                }
            )
            return [TextContent(type="text", text=error_response)]

        # Execute handler
        result = handler(current_gateway, arguments)

        # Optimize JSON serialization for local IDE (compact, no indentation for speed)
        # Use compact JSON for stdio mode (local), indented for HTTP mode (remote)
        # Compact JSON reduces serialization overhead for fast local IDE communication
        is_stdio_mode = gateway is not None
        json_text = json.dumps(
            result,
            indent=None if is_stdio_mode else 2,
            ensure_ascii=False,
            separators=(",", ":") if is_stdio_mode else (", ", ": "),
        )

        return [TextContent(type="text", text=json_text)]

    except KeyError as e:
        # Missing required argument
        error_response = json.dumps(
            {
                "success": False,
                "error": f"Missing required argument: {e}",
                "error_code": "MISSING_ARGUMENT",
                "tool": name,
            }
        )
        return [TextContent(type="text", text=error_response)]
    except ValueError as e:
        # Invalid argument value
        error_response = json.dumps(
            {
                "success": False,
                "error": f"Invalid argument: {e}",
                "error_code": "INVALID_ARGUMENT",
                "tool": name,
            }
        )
        return [TextContent(type="text", text=error_response)]
    except Exception as e:
        _gateway_log.warning(
            "tool_error tool=%s session_id=%s error=%s",
            name,
            session_id or "(none)",
            str(e),
            extra={"tool": name, "session_id": session_id or None, "error": str(e)},
        )
        # Generic error with context
        error_response = json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_code": "EXECUTION_ERROR",
                "tool": name,
                "error_type": type(e).__name__,
            }
        )
        return [TextContent(type="text", text=error_response)]


# ============================================================================
# HTTP Server Mode (Remote Isolation)
# ============================================================================

if HTTP_AVAILABLE:
    app = FastAPI(title="RLM MCP Gateway", version="1.0.0")

    # CORS middleware for IDE connections
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to IDE origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global gateway instance (initialized in main)
    gateway_instance: RLMMCPGateway | None = None

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "rlm-mcp-gateway"}

    @app.post("/mcp")
    async def mcp_endpoint(
        request: Request, authorization: str | None = Header(None)
    ) -> dict[str, Any]:
        """
        MCP protocol endpoint for remote IDE connections.

        Accepts MCP protocol messages and returns responses.
        """
        if not gateway_instance:
            raise HTTPException(status_code=500, detail="Gateway not initialized")

        # Validate authentication
        api_key = None
        if authorization and authorization.startswith("Bearer "):
            api_key = authorization[7:]

        if not gateway_instance._validate_auth(api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

        try:
            body = await request.json()

            # Handle MCP protocol messages
            if body.get("jsonrpc") == "2.0":
                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")

                if method == "tools/list":
                    # List available tools
                    tools = await handle_list_tools()
                    # Convert Tool objects to dicts
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
                    return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools_dict}}
                elif method == "tools/call":
                    # Call a tool
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    result_content = await handle_call_tool(tool_name, arguments)
                    # Extract text from TextContent
                    content: list[dict[str, Any]] = []
                    for item in result_content:
                        if hasattr(item, "text"):
                            content.append({"type": "text", "text": item.text})
                        elif isinstance(item, dict):
                            content.append(item)
                        else:
                            content.append({"type": "text", "text": str(item)})
                    return {"jsonrpc": "2.0", "id": request_id, "result": {"content": content}}
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
            else:
                raise HTTPException(status_code=400, detail="Invalid MCP protocol message")

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": body.get("id") if isinstance(body, dict) else None,
                "error": {"code": -32603, "message": str(e)},
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
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main_http(
    host: str = "0.0.0.0",
    port: int = 8080,
    repo_path: str | None = None,
    api_key: str | None = None,
) -> None:
    """Run the MCP gateway server in HTTP mode (remote isolation)."""
    if not HTTP_AVAILABLE:
        print(
            "ERROR: FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    global gateway_instance
    gateway_instance = RLMMCPGateway(repo_root=repo_path, api_key=api_key)

    print(f"Starting RLM MCP Gateway HTTP server on {host}:{port}", file=sys.stderr)
    if repo_path:
        print(f"Repository root: {repo_path}", file=sys.stderr)
    if api_key:
        print("Authentication: ENABLED", file=sys.stderr)
    else:
        print("Authentication: DISABLED (not recommended for production)", file=sys.stderr)

    uvicorn.run(app, host=host, port=port, log_level="info")


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

        main_http(host=args.host, port=args.port, repo_path=args.repo_path, api_key=args.api_key)
    else:
        # stdio mode: PRIMARY METHOD for seamless local IDE integration
        # No Docker/HTTP overhead - direct local communication for optimal performance
        if args.repo_path:
            gateway = RLMMCPGateway(repo_root=args.repo_path)
        else:
            # Local mode: use script location (default for local development)
            gateway = RLMMCPGateway()
        asyncio.run(main_stdio())
