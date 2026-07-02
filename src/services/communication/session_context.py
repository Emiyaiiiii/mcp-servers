"""Per-tool-call session_id context, propagated via ContextVar.

When the deerflow-side SessionInjectMiddleware injects a browser WebSocket
session_id into an MCP tool call, the FastMCP middleware on this server
extracts it from the arguments and stores it here.  CommandSender then reads
this context variable as a fallback when no explicit session_id is passed.
"""

from contextvars import ContextVar
from typing import Optional

_current_tool_session_id: ContextVar[Optional[str]] = ContextVar(
    "_current_tool_session_id", default=None
)


def get_current_session_id() -> Optional[str]:
    """Return the session_id (if any) for the currently executing tool call."""
    return _current_tool_session_id.get()


def set_current_session_id(session_id: Optional[str]) -> None:
    """Set the session_id for the current tool call context.

    This is called by the FastMCP middleware before the tool function runs.
    The value is automatically scoped to the current async task/tool call.
    """
    if session_id:
        _current_tool_session_id.set(session_id)
    else:
        _current_tool_session_id.set(None)
