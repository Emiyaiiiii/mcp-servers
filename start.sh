#!/bin/bash
set -e

echo "======================================"
echo "  防洪四预 MCP 服务启动脚本"
echo "======================================"

# 检查是否存在虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 安装依赖..."
    uv sync
fi

# 检查是否存在storage目录
if [ ! -d "storage" ]; then
    mkdir -p storage
fi

# 检查数据库是否存在
if [ ! -f "storage/flood_control.db" ]; then
    echo "🗄️ 初始化数据库..."
    uv run python -m src.services.database.init_database
    echo "✅ 数据库初始化完成"
fi

echo ""
echo "请选择启动模式："
echo "1. stdio 模式（用于 Claude Desktop 等本地客户端）"
echo "2. HTTP 模式（用于 Web 应用）"
echo ""
read -p "请输入选择 (1/2): " choice

case $choice in
    1)
        echo "🚀 启动 MCP 服务（stdio模式）..."
        uv run mcp-server
        ;;
    2)
        echo "🚀 启动 MCP 服务（HTTP模式）..."
        echo "服务将在 http://localhost:8082 运行"
        uv run python -c "from src.server import run_server; run_server(transport='streamable-http')"
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac
