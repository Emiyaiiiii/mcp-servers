# 防洪四预 MCP 服务

基于 FastMCP 的防洪四预（预报、预警、预演、预案）智能服务。

## 项目结构

```
mcp-servers/
├── src/
│   ├── server.py           # 服务入口
│   ├── config/
│   │   ├── config.yaml     # 水库配置
│   │   └── settings.py     # 环境变量配置
│   ├── services/
│   │   └── scene_connector.py  # WebSocket场景连接器
│   ├── tools/
│   │   ├── ui_tools.py         # UI页面跳转工具
│   │   ├── data_api_tools.py   # 数据API工具
│   │   ├── warning_tools.py    # 预警工具
│   │   ├── simulation_tools.py # 预演工具
│   │   ├── plan_tools.py       # 预案工具
│   │   └── forecast_models.py  # 预报模型工具
│   └── utils/
│       ├── exceptions.py
│       ├── logger.py
│       ├── retry.py
│       └── station_codes.py
├── templates/              # 预案模板
├── data/                   # 站点数据
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## 快速启动

### 本地开发

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置必要的参数

# 启动MCP服务（stdio 模式，用于 Claude Desktop 等客户端）
make start
# 或
uv run mcp-server

# 启动MCP服务（HTTP 模式，用于 Web 应用）
uv run python -c "from src.server import run_server; run_server(transport='streamable-http')"

# 测试mcp服务
npx @modelcontextprotocol/inspector
```

### Docker部署

```bash
# 构建并启动服务
docker-compose up --build

# 后台运行
docker-compose up -d
```

## 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
# MCP 服务配置
MCP_SERVER_NAME=FloodControlMCP

# 场景 WebSocket 配置（UE服务地址）
SCENE_WS_BASE_URL=ws://localhost:8889
SCENE_WS_TIMEOUT=30
SCENE_IDLE_TIMEOUT=60

# 数据 API 配置
DATA_API_BASE_URL=http://wt.hxyai.cn/fx
DATA_API_USERNAME=yhllm
DATA_API_PASSWORD=Yhllm#2026
DATA_API_MOCK_ENABLED=true

# 日志配置
LOG_LEVEL=INFO
```

## 工具列表

工具总计：**52个**

| 类别 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 预报模型 | forecast_models.py | 2 | 水文预报、洪水演进模型 |
| 预警工具 | warning_tools.py | 6 | 水位/流量预警、预警简报 |
| 预演工具 | simulation_tools.py | 9 | 相机飞行、闸门控制、水位标签 |
| 预案工具 | plan_tools.py | 4 | 模板管理、知识库、文档导出 |
| 数据API | data_api_tools.py | 22 | 雨量/水文/水库数据获取 |
| UI工具 | ui_tools.py | 9 | 页面跳转、调度方案、预演指令 |

### 预报工具 (forecast_models) - 2个
- `run_hydrological_model` - 执行水文预报模型
- `run_flood_routing_model` - 执行洪水演进模型

### 预警工具 (warning_tools) - 6个
- `generate_water_level_warning` - 获取水库预警信息
- `generate_flow_warning` - 获取河道水文站预警信息
- `get_rainfall_warning` - 获取雨量站预警信息
- `check_water_level_warning` - 判断预报水位是否超预警
- `check_flow_warning` - 判断预报流量是否超预警
- `generate_warning_bulletin` - 生成预警简报

### 预演工具 (simulation_tools) - 9个
- `fly_to_location` - 相机飞向位置
- `fly_to_sanmenxia_water_level_view` - 飞向三门峡水位视角
- `control_floodgate` - 控制闸门
- `set_reservoir_water_level` - 设置水库水位
- `create_water_level_placemark` - 创建水位标签
- `update_water_level_placemark` - 更新水位标签
- `destroy_placemarks` - 删除标签
- `query_scene_status` - 查询场景连接状态
- `get_available_locations` - 获取可用的位置列表
- `get_reservoir_info` - 获取水库详细信息

### 预案工具 (plan_tools) - 4个
- `load_plan_template` - 加载预案模板
- `list_plan_templates` - 列出可用模板
- `export_document` - 导出预案文档
- `query_knowledge_base` - 查询防洪知识库

### 数据API工具 (data_api_tools) - 22个
- `get_rainfall_station_info` - 获取雨量站信息
- `get_realtime_rainfall` - 获取实时雨量监测数据
- `get_daily_rainfall_stats` - 获取日降雨量统计
- `get_rainfall_statistics` - 获取雨量统计结果
- `get_river_station_info` - 获取水文站信息
- `list_hydrological_stations` - 获取水文站列表
- `list_design_flood_results` - 获取设计洪水成果
- `get_hydrological_features` - 获取水文特征统计
- `list_water_level_sections` - 获取水位断面列表
- `list_realtime_hydrology` - 获取实时水情列表
- `list_daily_hydrology` - 获取日均水情列表
- `list_reservoirs` - 获取水库列表
- `get_reservoir_features` - 获取水库特性
- `list_reservoir_level_capacity` - 获取水位库容曲线
- `list_reservoir_features` - 获取水库特征值列表
- `get_reservoir_realtime` - 获取水库实时水情
- `get_reservoir_daily` - 获取水库日均水情
- `get_river_latest_realtime` - 获取河道最新实时水情
- `get_reservoir_latest_realtime` - 获取水库最新实时水情
- `get_hydrological_extreme` - 获取水文站极值信息
- `get_hydrological_same_period` - 获取水文站同期数据
- `get_hydrological_yearly_extreme` - 获取各年份极值数据
- `get_rainfall_warning` - 获取雨量站预警信息
- `get_reservoir_warning` - 获取水库预警信息
- `get_hydrological_warning` - 获取水文站预警信息

### UI工具 (ui_tools) - 9个
- `navigate_to_reservoir_page` - 跳转到水库实时数据页面
- `navigate_to_station_page` - 跳转到水文站页面
- `navigate_to_rainfall_page` - 跳转到降雨信息页面
- `navigate_to_similar_rainfall_page` - 跳转到相似雨分析页面
- `navigate_to_reservoir_forecast_page` - 跳转到水库预报页面
- `navigate_to_control_guidance_page` - 跳转到控导信息页面
- `navigate_to_station_forecast_page` - 跳转到水文站预报页面
- `generate_dispatch_scheme` - 生成五库联调调度方案
- `send_simulation_command` - 发送预演指令

## 架构

```
Agent ←→ MCP ←WebSocket→ UE-server ←→ UE场景
           (长连接，同步等待返回)
```

MCP服务通过WebSocket与UE服务通信，所有场景操作同步执行并等待UE返回结果。

## 传输方式

支持两种传输方式：

1. **stdio** (默认): 用于 Claude Desktop 等本地客户端
   ```bash
   uv run mcp-server
   ```

2. **streamable-http**: 用于 Web 应用，支持 HTTP 请求
   ```bash
   uv run python -c "from src.server import run_server; run_server(transport='streamable-http')"
   ```

## 开发命令

```bash
# 安装依赖
make install

# 启动服务
make start

# 代码格式化
make format

# 代码检查
make lint

# 清理缓存
make clean
```

## 配置说明

### 水库配置 (config.yaml)

水库配置包含以下字段：
- `id`: 水库唯一标识
- `name`: 水库中文名称
- `warning_level`: 预警水位
- `flood_limit_level`: 汛限水位
- `normal_level`: 正常水位
- `camera_position`: 相机位置 [经度, 纬度, 高度]
- `camera_rotation`: 相机旋转 [俯仰角, 偏航角, 翻滚角]
- `gates`: 闸门配置（可选）

### 支持的传输方式

- `stdio`: 标准输入输出，适用于本地客户端
- `streamable-http`: HTTP 流式传输，适用于 Web 应用

## 依赖

- Python >= 3.12
- FastMCP >= 3.2.3
- websocket-client >= 1.5.0
- PyYAML >= 6.0.0
- requests >= 2.31.0
