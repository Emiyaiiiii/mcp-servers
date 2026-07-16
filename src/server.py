import os
import uvicorn
from fastmcp import FastMCP
from starlette.routing import WebSocketRoute, Route
from starlette.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src.config.settings import settings
from src.tools.warning_tools import register_warning_tools
from src.tools.simulation_tools import register_simulation_tools
from src.tools.plan_tools import register_plan_tools
from src.tools.data_api_tools import register_data_api_tools
from src.tools.forecast_models import register_forecast_models
from src.tools.reservoir_dispatch import register_reservoir_dispatch
from src.tools.ui_tools import register_ui_tools
from src.tools.skill_tools import register_skill_tools
from src.services.communication.websocket_manager import websocket_handler
from src.services.communication.session_context import set_current_session_id
from src.services.auth.mcp_auth_provider import JWTTokenVerifier, FloodControlOAuthProvider
from src.utils.logger import get_logger
from fastmcp.server.providers.skills import SkillsDirectoryProvider

logger = get_logger(__name__)


def get_frontend_path():
    """获取前端文件路径"""
    return os.path.join(os.path.dirname(__file__), "..", "frontend")


def serve_static_file(request):
    """处理静态文件请求（js, css, ico 等）"""
    path = request.url.path.lstrip("/")
    file_path = os.path.join(get_frontend_path(), path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return JSONResponse({"detail": "Not Found"}, status_code=404)


def index_handler(request):
    """处理根路径和 index.html 请求"""
    return FileResponse(os.path.join(get_frontend_path(), "index.html"))


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


def create_app() -> FastMCP:
    """创建 FastMCP 应用实例"""
    auth = None
    if settings.MCP_AUTH_ENABLED:
        if settings.MCP_AUTH_MODE == 'oauth':
            auth = FloodControlOAuthProvider()
            logger.info("MCP OAuth认证已启用")
        else:
            auth = JWTTokenVerifier(base_url=settings.MCP_SERVER_BASE_URL)
            logger.info("MCP 令牌验证已启用")

    mcp = FastMCP(
        settings.MCP_SERVER_NAME,
        auth=auth,
    )

    register_warning_tools(mcp)
    register_simulation_tools(mcp)
    register_plan_tools(mcp)
    register_data_api_tools(mcp)
    register_forecast_models(mcp)
    register_reservoir_dispatch(mcp)
    register_ui_tools(mcp)
    register_skill_tools(mcp)

    # 注册 Skills 提供者 — 将 skills/ 目录下的 SKILL.md 暴露为 MCP 资源
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    if os.path.isdir(skills_dir):
        skills_provider = SkillsDirectoryProvider(
            roots=[skills_dir],
            supporting_files="template",
        )
        mcp.add_provider(skills_provider)
        logger.info(f"Skills 提供者已注册: {skills_dir}")

    return mcp


def run_server(transport="streamable-http"):
    """运行 MCP 服务（集成 WebSocket 和前端页面）"""
    mcp_app = create_app()
    
    # 获取 FastMCP 的 Starlette 应用（使用 streamable-http 传输方式）
    starlette_app = mcp_app.http_app(transport='streamable-http', stateless_http=True)
    
    allow_origins = settings.MCP_ALLOWED_ORIGINS
    allow_credentials = settings.MCP_AUTH_ENABLED
    
    # 注册 SessionHeaderMiddleware — 从 HTTP 请求头提取 X-Session-Id
    # 必须先于其他中间件注册，确保在请求处理前提取 session_id
    starlette_app.add_middleware(SessionHeaderMiddleware)
    
    starlette_app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加 WebSocket 路由
    starlette_app.router.routes.append(
        WebSocketRoute("/browser", websocket_handler)
    )
    
    # 添加前端页面路由（根路径和 /wkld.html）
    starlette_app.router.routes.append(
        Route("/", index_handler)
    )
    starlette_app.router.routes.append(
        Route("/wkld.html", index_handler)
    )
    starlette_app.router.routes.append(
        Route("/{path:path}", serve_static_file)
    )
    
    logger.info(f"MCP 服务已启动: {settings.MCP_SERVER_BASE_URL}")
    logger.info(f"WebSocket 端点: {settings.MCP_SERVER_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://')}/browser")
    logger.info(f"前端页面: {settings.MCP_SERVER_BASE_URL}/index.html")
    
    # 使用 uvicorn 启动应用，log_level 设置为 warning 避免框架日志干扰
    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=8082,
        log_level="warning"
    )

mcp = create_app()

if __name__ == "__main__":
    run_server()