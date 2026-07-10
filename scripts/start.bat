@echo off
echo ======================================
echo   防洪四预 MCP 服务启动脚本
echo ======================================

REM 检查是否存在虚拟环境
if not exist ".venv" (
    echo 正在安装依赖...
    uv sync
)

REM 检查是否存在storage目录
if not exist "storage" (
    mkdir storage
)

REM 检查数据库是否存在
if not exist "storage\flood_control.db" (
    echo 正在初始化数据库...
    uv run python -m src.services.database.init_database
    echo 数据库初始化完成
)

echo.
echo 请选择启动模式：
echo 1. stdio 模式（用于 Claude Desktop 等本地客户端）
echo 2. HTTP 模式（用于 Web 应用）
echo.
set /p choice=请输入选择 (1/2): 

if "%choice%"=="1" (
    echo 启动 MCP 服务（stdio模式）...
    uv run mcp-server
) else if "%choice%"=="2" (
    echo 启动 MCP 服务（HTTP模式）...
    echo 服务将在 http://localhost:8082 运行
    uv run python -c "from src.server import run_server; run_server(transport='streamable-http')"
) else (
    echo 无效选择
    pause
    exit /b 1
)
