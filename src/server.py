import os
import uvicorn
from fastmcp import FastMCP
from starlette.routing import WebSocketRoute, Route
from starlette.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from src.config.settings import settings
from src.tools.warning_tools import register_warning_tools
from src.tools.simulation_tools import register_simulation_tools
from src.tools.plan_tools import register_plan_tools
from src.tools.data_api_tools import register_data_api_tools
from src.tools.forecast_models import register_forecast_models
from src.tools.reservoir_dispatch import register_reservoir_dispatch
from src.tools.ui_tools import register_ui_tools
from src.services.communication.websocket_manager import websocket_handler
from src.services.communication.session_middleware import SessionIDMiddleware
from src.utils.logger import get_logger

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


def create_app() -> FastMCP:
    """创建 FastMCP 应用实例"""
    mcp = FastMCP(
        settings.MCP_SERVER_NAME,
    )

    register_warning_tools(mcp)
    register_simulation_tools(mcp)
    register_plan_tools(mcp)
    register_data_api_tools(mcp)
    register_forecast_models(mcp)
    register_reservoir_dispatch(mcp)
    register_ui_tools(mcp)

    # 注册 SessionIDMiddleware — 从工具调用参数中提取 session_id
    # 并存入 ContextVar，使 CommandSender 能够将指令路由到正确的
    # 前端 WebSocket 连接，而非广播给所有连接。
    mcp.add_middleware(SessionIDMiddleware())

    # 为所有已注册的工具添加 session_id 到参数 schema 中。
    # session_id 由 deerflow 侧的 SessionInjectMiddleware 自动注入，
    # 对工具函数透明（由 SessionIDMiddleware 提取并移除）。
    try:
        import asyncio

        async def _enrich_tool_schemas():
            tools = await mcp.list_tools()
            for tool in tools:
                if tool.parameters is not None:
                    props = tool.parameters.setdefault("properties", {})
                    if "session_id" not in props:
                        props["session_id"] = {
                            "type": "string",
                            "description": "Browser WebSocket session_id (auto-populated)",
                        }

        asyncio.run(_enrich_tool_schemas())
    except Exception:
        from src.utils.logger import get_logger

        get_logger(__name__).warning(
            "Failed to enrich tool schemas with session_id", exc_info=True
        )

    return mcp


def run_server(transport="streamable-http"):
    """运行 MCP 服务（集成 WebSocket 和前端页面）"""
    mcp_app = create_app()
    
    # 获取 FastMCP 的 Starlette 应用（使用 streamable-http 传输方式）
    starlette_app = mcp_app.http_app(transport='streamable-http', stateless_http=True)
    
    # 添加CORS中间件，允许MCP Inspector连接
    starlette_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
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
    
    logger.info(f"MCP 服务已启动: http://localhost:8082")
    logger.info(f"WebSocket 端点: ws://localhost:8082/browser")
    logger.info(f"前端页面: http://localhost:8082/index.html")
    
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