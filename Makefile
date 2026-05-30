.PHONY: all start start-http install test lint format clean db-init db-test db-shell db-clean

# 默认目标
all: install

# 安装依赖
install:
	uv sync

# 启动服务（stdio模式，用于本地客户端）
start:
	uv run mcp-server

# 启动服务（HTTP模式，用于Web应用）
start-http:
	uv run python -c "from src.server import run_server; run_server(transport='streamable-http')"

# 代码测试
test:
	python -m pytest tests/

# 代码检查
lint:
	flake8 src/

# 代码格式化
format:
	black src/

# 清理缓存和临时文件
clean:
	rm -rf __pycache__/ .venv/ logs/ *.pyc *.pyo .pytest_cache/

# 数据库初始化（重建并导入所有seed数据）
db-init:
	rm -f storage/flood_control.db*
	uv run python -m src.services.database.init_database
	@echo "✅ 数据库初始化完成"

# 数据库测试（测试连接和数据完整性）
db-test:
	uv run python test_database.py

# 数据库命令行
db-shell:
	sqlite3 storage/flood_control.db

# 清理数据库
db-clean:
	rm -f storage/flood_control.db*
	@echo "✅ 数据库已清理"

# 启动开发服务器（后台运行）
start-daemon:
	nohup uv run python -c "from src.server import run_server; run_server(transport='streamable-http')" > logs/mcp-server.log 2>&1 &
	@echo "MCP服务已启动，日志文件: logs/mcp-server.log"

# 停止后台服务
stop-daemon:
	@pkill -f "run_server" || true
	@echo "✅ MCP服务已停止"

# 查看日志
logs:
	tail -f logs/mcp-server.log

# 创建必要的目录
setup:
	mkdir -p storage logs
	@echo "✅ 目录结构已创建"

# 完整部署（安装依赖+初始化数据库+启动服务）
deploy: setup install db-init start-http
