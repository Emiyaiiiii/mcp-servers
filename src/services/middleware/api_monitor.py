"""
API 调用监控中间件

记录每个 MCP 请求的耗时、状态码和客户端信息。
基于现有的 logger 系统，数据自动写入 logs/app.log。
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ApiMonitorMiddleware(BaseHTTPMiddleware):
    """API 调用监控中间件

    记录每个请求的：
    - 请求路径和方法
    - 客户端 session_id 或 IP
    - 响应状态码
    - 处理耗时
    """

    async def dispatch(self, request: Request, call_next):
        # 仅监控 /mcp 路径
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        start_time = time.time()
        session_id = request.headers.get("X-Session-Id", "N/A")
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response: Response = await call_next(request)
            elapsed_ms = (time.time() - start_time) * 1000
            status_code = response.status_code

            # 根据耗时选择日志级别
            if elapsed_ms > 5000:
                log_level = logger.warning
            elif elapsed_ms > 1000:
                log_level = logger.info
            else:
                log_level = logger.debug

            log_level(
                f"API调用 [method={method} path={path} status={status_code} "
                f"session={session_id} client={client_host} elapsed={elapsed_ms:.0f}ms]"
            )

            # 在响应头中添加耗时信息
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.0f}"

            return response
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"API异常 [method={method} path={path} session={session_id} "
                f"client={client_host} elapsed={elapsed_ms:.0f}ms error={e}]"
            )
            raise
