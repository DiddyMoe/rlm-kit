"""RLM MCP Gateway - Modular implementation for IDE integration."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rlm.mcp_gateway.server import RLMMCPGateway


def __getattr__(name: str) -> Any:
    if name == "RLMMCPGateway":
        from rlm.mcp_gateway.server import RLMMCPGateway

        return RLMMCPGateway
    raise AttributeError(f"module 'rlm.mcp_gateway' has no attribute '{name}'")


__all__ = ["RLMMCPGateway"]
