from collections.abc import Callable
from typing import Any

from fastmcp.tools import tool
from mcp.types import ToolAnnotations


def read_tool(
    *, tags: set[str] | None = None, timeout: float | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a Monarch tool as read-only for MCP clients."""
    return tool(
        tags=(tags or set()) | {"read"},
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
        timeout=timeout,
    )


def write_tool(
    *,
    tags: set[str] | None = None,
    destructive: bool = False,
    idempotent: bool = False,
    timeout: float | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a Monarch tool as mutating for MCP clients."""
    return tool(
        tags=(tags or set()) | {"write"},
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=destructive,
            idempotentHint=idempotent,
            openWorldHint=True,
        ),
        timeout=timeout,
    )
