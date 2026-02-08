#!/usr/bin/env python3
"""
RLM MCP Gateway Server - Entry Point

This script is a thin wrapper around the modular RLM MCP Gateway server.
The actual implementation is in rlm.mcp_gateway.server.

Usage:
    # HTTP server mode (remote isolation)
    python scripts/rlm_mcp_gateway.py --mode http --host 0.0.0.0 --port 8080 --repo-path /repo/rlm-kit --api-key KEY

    # stdio mode (local development) - PRIMARY METHOD
    python scripts/rlm_mcp_gateway.py --mode stdio
"""

import sys
from pathlib import Path

# Bootstrap: repo root on path so path_utils and rlm are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))

# Import and run the modular server
from rlm.mcp_gateway.server import main_http

if __name__ == "__main__":
    import argparse
    import asyncio
    import os

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
        import rlm.mcp_gateway.server as server_module

        # Initialize gateway (will be used by server handlers)
        if args.repo_path:
            server_module.gateway = server_module.RLMMCPGateway(repo_root=args.repo_path)
        else:
            # Local mode: use script location (default for local development)
            server_module.gateway = server_module.RLMMCPGateway()
        asyncio.run(server_module.main_stdio())
