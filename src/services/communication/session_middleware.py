"""FastMCP middleware that extracts browser session_id from tool call arguments.

This middleware runs before every tool invocation and:
1. Checks if the tool call arguments contain a ``session_id`` key
2. If found, stores it in a ContextVar (via session_context) and removes it
   from the arguments so the tool function itself does not need to declare it
3. Forwards the cleaned arguments to the actual tool handler

This works in conjunction with the deerflow-side SessionInjectMiddleware which
injects the browser WebSocket session_id into MCP tool calls initiated by the
LLM agent.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp.types import CallToolRequestParams

from src.services.communication.session_context import set_current_session_id
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SessionIDMiddleware(Middleware):
    """Extract 'session_id' from tool arguments and store it in ContextVar.

    The session_id is removed from the arguments before forwarding to the
    tool function so that tools do not need to declare a session_id parameter.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: Callable[
            [MiddlewareContext[CallToolRequestParams]],
            Coroutine[Any, Any, ToolResult],
        ],
    ) -> ToolResult:
        args = dict(context.message.arguments or {})

        # Extract and store session_id (if present)
        session_id = args.pop("session_id", None)
        if session_id:
            set_current_session_id(str(session_id))
            logger.debug(
                "Stored session_id=%s for tool call: %s",
                session_id,
                context.message.name,
            )

        # Create a new message with cleaned arguments (session_id removed)
        if session_id is not None or "session_id" in (context.message.arguments or {}):
            new_message = context.message.model_copy(update={"arguments": args})
            updated_context = context.copy(message=new_message)
        else:
            updated_context = context

        return await call_next(updated_context)
