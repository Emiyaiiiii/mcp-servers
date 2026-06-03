import os
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
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
    """处理根路径和 wkld.html 请求"""
    return FileResponse(os.path.join(get_frontend_path(), "wkld.html"))


def create_app() -> FastMCP:
    """创建 FastMCP 应用实例"""
    # 配置传输安全设置，允许MCP Inspector连接
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,  # 禁用DNS重绑定保护以便MCP Inspector连接
        allowed_hosts=["localhost:*", "127.0.0.1:*", "0.0.0.0:*"],
        allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
    )
    
    mcp = FastMCP(
        settings.MCP_SERVER_NAME,
        transport_security=transport_security,
        stateless_http=True  # 启用无状态HTTP模式，不需要session ID
    )

    register_warning_tools(mcp)
    register_simulation_tools(mcp)
    register_plan_tools(mcp)
    register_data_api_tools(mcp)
    register_forecast_models(mcp)
    register_reservoir_dispatch(mcp)
    register_ui_tools(mcp)

    return mcp


def run_server(transport="streamable-http"):
    """运行 MCP 服务（集成 WebSocket 和前端页面）"""
    mcp_app = create_app()
    
    # 获取 FastMCP 的 Starlette 应用
    starlette_app = mcp_app.streamable_http_app()
    
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
    
    print(f"🚀 MCP 服务已启动: http://localhost:8082")
    print(f"📡 WebSocket 端点: ws://localhost:8082/browser")
    print(f"🌐 前端页面: http://localhost:8082/wkld.html")
    
    # 使用 uvicorn 启动应用
    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=8082,
        log_level="info"
    )

if __name__ == "__main__":
    run_server()