from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src.services.communication.session_context import set_current_session_id


class SessionHeaderMiddleware(BaseHTTPMiddleware):
    """从 HTTP 请求头 X-Session-Id 提取 session_id 存入 ContextVar。

    deerflow 侧的 SessionHeaderInterceptor 在 MCP 工具调用时自动注入
    X-Session-Id 请求头，该中间件将其提取出来供 CommandSender 使用。
    """

    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("X-Session-Id")
        if session_id:
            set_current_session_id(session_id)
        return await call_next(request)
