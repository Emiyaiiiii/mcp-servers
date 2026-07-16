"""
API 限流中间件

基于 session_id 或客户端 IP 的滑动窗口限流。
限流数据存储在内存中，单进程内有效。
"""
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流中间件

    基于 session_id（优先）或客户端 IP 进行限流。
    对 /mcp 路径的请求进行限流，静态文件和前端页面不限流。
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        """
        Args:
            app: ASGI 应用
            max_requests: 窗口期内最大请求数
            window_seconds: 窗口期（秒）
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request: Request) -> str:
        """获取客户端标识（优先 session_id，其次 IP）"""
        session_id = request.headers.get("X-Session-Id")
        if session_id:
            return f"session:{session_id}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _clean_expired(self, key: str, now: float):
        """清理过期的请求记录"""
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        # 仅对 /mcp 路径限流
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        key = self._get_client_key(request)
        now = time.time()
        self._clean_expired(key, now)

        if len(self._requests[key]) >= self.max_requests:
            logger.warning(f"限流触发: {key}, 请求数={len(self._requests[key])}/{self.max_requests}")
            return JSONResponse(
                {"error": "请求过于频繁，请稍后再试", "retry_after": self.window_seconds},
                status_code=429,
                headers={"Retry-After": str(self.window_seconds)}
            )

        self._requests[key].append(now)
        return await call_next(request)
