# 防洪四预 MCP 服务

基于 FastMCP 的防洪四预（预报、预警、预演、预案）智能服务，集成水库联合调度、参数模板管理、流量约束控制等功能。

## 项目结构

```
mcp-servers/
├── src/
│   ├── server.py                   # 服务入口（HTTP 模式，端口 8082）
│   ├── config/
│   │   ├── config.yaml             # 水库静态配置
│   │   ├── config.py               # 配置加载器
│   │   └── settings.py             # 环境变量配置（统一管理所有服务配置）
│   ├── services/
│   │   ├── communication/          # 通信服务
│   │   │   ├── command_sender.py
│   │   │   ├── message_queue.py
│   │   │   ├── session_context.py
│   │   │   ├── session_middleware.py
│   │   │   └── websocket_manager.py
│   │   ├── external_api/           # 外部 API 服务
│   │   │   ├── data_api_auth_service.py  # 数据 API 认证服务
│   │   │   ├── enhanced_search_service.py
│   │   │   ├── hydrology_forecast_service.py  # 水文局预报服务
│   │   │   ├── water_forecast_service.py
│   │   │   └── xinanjiang_service.py
│   │   └── storage/                # 存储服务
│   │       ├── scheme_storage.py
│   │       └── database/
│   │           ├── connection.py
│   │           ├── config_loader.py
│   │           ├── data_access.py
│   │           ├── init_database.py
│   │           └── xinanjiang_config_access.py
│   ├── tools/                      # MCP 工具定义（仅保留工具关键部分）
│   │   ├── forecast_models.py      # 预报模型工具（核心，11 个工具）
│   │   ├── warning_tools.py        # 预警工具
│   │   ├── simulation_tools.py     # 预演工具
│   │   ├── plan_tools.py           # 预案工具
│   │   ├── data_api_tools.py       # 数据 API 工具
│   │   ├── reservoir_dispatch.py   # 水库调度工具
│   │   └── ui_tools.py             # UI 工具
│   └── utils/                      # 工具函数（按业务分类，便于复用）
│       ├── logger.py               # 日志工具
│       ├── response_helper.py      # 响应辅助
│       ├── station_codes.py        # 站点编码映射
│       ├── date_utils.py           # 时间格式化工具
│       ├── data_api_utils.py       # 数据 API 请求辅助
│       ├── reservoir_utils.py      # 水库水位判断和告警
│       ├── mdb_utils.py            # MDB 数据库操作工具
│       ├── dispatch_utils.py       # 调度方案生成核心逻辑
│       ├── flood_utils.py          # 淹没分析和风险评估
│       ├── stats_utils.py          # 统计计算
│       ├── xinanjiang_utils.py     # 新安江模型辅助函数
│       ├── warning_utils.py        # 预警等级判断
│       └── template_utils.py       # 参数模板扫描和自然语言总结
├── 6/
│   └── data.mdb                    # Access 数据库（调度参数、计算结果）
├── Parameter_template/             # 参数模板文件（只读，不可修改）
│   ├── 上大洪水控制/
│   │   ├── 方案一：（小浪底不保滩，控花园口10000）.xlsx
│   │   ├── 方案二：（小浪底254以下保滩，254以上控花园口10000）.xlsx
│   │   └── 方案三：（小浪底全程4500保滩）.xlsx
│   └── 下大洪水控制/
│       ├── 方案一：演练洪水-常规调度....xlsx
│       └── 方案二：演练洪水-优化调度....xlsx
├── data/                           # Excel 入库流量数据
│   ├── Q_Inputsd.xlsx              # 上游入库流量
│   ├── Q_Inputxd.xlsx              # 下游入库流量
│   └── 水文站.txt                  # 水文站数据
├── RegualDispacth.exe              # 调度计算程序
├── skills/                         # Skill 文件（供智能体框架使用）
│   └── custom/
│       ├── flood-control-mcp/SKILL.md    # 防洪 MCP 使用指南
│       ├── flood-four-pre/SKILL.md       # 防洪四预工作流
│       └── schedule-dispatch/SKILL.md    # 调度方案生成指南
├── test/                           # 测试文件
│   ├── mcp_full_system_test.py     # 全功能系统测试
│   ├── test_new_flow_feature.py    # 流量约束 + 水库统计测试
│   └── test_parameter_templates.py # 参数模板测试
├── sql/                            # SQLite 初始化脚本
├── frontend/                       # 前端页面
├── .env                            # 环境变量配置文件
├── pyproject.toml
├── mcp-config.json                 # MCP 客户端配置
└── uv.lock
```

## 快速启动

### 环境要求

- Python >= 3.12
- uv 包管理器
- Windows 系统（依赖 Access 数据库驱动和 RegualDispacth.exe）

### 本地开发

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置 API 密钥等参数

# 启动 MCP 服务（HTTP 模式，端口 8082）
uv run python -c "from src.server import run_server; run_server()"

# 或直接执行
uv run mcp-server
```

启动后服务地址：
- MCP 端点: `http://localhost:8082/mcp`
- WebSocket 端点: `ws://localhost:8082/browser`
- 前端页面: `http://localhost:8082/index.html`

### Docker 部署

```bash
docker-compose up --build
docker-compose up -d     # 后台运行
docker-compose logs -f   # 查看日志
```

## 核心功能

### 1. 调度方案单生成 (`generate_dispatch_scheme`)

一键生成五库联调调度方案，完整流程：

1. **导入 Excel** — 从 `data/Q_Inputsd.xlsx` 和 `data/Q_Inputxd.xlsx` 读取入库流量
2. **运行计算** — 调用 `RegualDispacth.exe` 进行调度计算
3. **统计处理** — 读取 `Q_Output` 和 `Z_Output` 计算结果，提取水库统计指标
4. **存储入库** — 保存到 SQLite 数据库，返回前台展示数据

返回数据包含：
- 各站点流量统计（最大/最小/平均流量）
- 水库特征值（最大入库、最大出库、滞蓄洪量、最高水位、相应蓄量）

### 2. 参数模板管理

支持从 `Parameter_template/` 目录读取预定义参数模板（只读），可应用到 Access 数据库（`6/data.mdb` 的 `Dispatch_Par` 表）。

| 工具 | 说明 |
|------|------|
| `list_parameter_templates` | 列出所有可用模板（类别、参数条数、计算结果 sheet） |
| `show_parameter_template` | 查看模板完整参数（stcd/stnm/Control_Par/Instruction） |
| `apply_parameter_template` | 将模板参数写入 Dispatch_Par 表，可选自动生成调度方案 |
| `verify_dispatch_result` | 将实际计算结果与模板预期结果对比验证 |

模板匹配规则：
- 精确匹配唯一键（如 `上大洪水控制/方案一`）
- 模糊匹配关键词（如 `常规调度`、`上大`）

### 3. 流量约束控制 (`set_flow_constraint`)

控制指定站点流量不超过设定值，自动调整 `Dispatch_Par` 表中 6 个相关参数：

- **target 类型**：直接设为目标流量（如花园口控制流量）
- **buffer 类型**：设为目标流量 - 1000（如小浪底保滩流量）

当前支持站点：花园口

### 4. 数据库参数修改 (`modify_dispatch_param`)

支持查看和修改 `data.mdb` 中 `Dispatch_Par` 表的调度参数：

- `action="list"` — 查看所有 46 条参数
- `action="update"` — 按站点名和关键词匹配修改参数

### 5. 新安江水文模型 (`run_xinanjiang_model`)

运行新安江模型计算目标站点区间来水，支持：
- 从本地数据库查询降雨数据并计算加权面雨量
- 支持自定义模型参数
- 返回逐时段流量、降雨、蒸散发数据

### 6. 其他工具

- `run_rainfall_forecast_model` — 降雨预报模型
- `run_water_forecast_model` — 来水预报模型（对接设计院 API）
- `rainfall_similarity_analysis` — 降雨图斑相似性分析（三步流程）
- `generate_dispatch_scheme` — 调度方案生成辅助入口

## 工具列表

工具总计：**74 个**

| 类别 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 预报模型 | forecast_models.py | 11 | 水文预报、新安江模型、调度方案、参数模板、流量约束 |
| 预警工具 | warning_tools.py | 6 | 水位/流量预警、预警简报 |
| 预演工具 | simulation_tools.py | 9 | 相机飞行、闸门控制、水位标签 |
| 预案工具 | plan_tools.py | 4 | 模板管理、知识库、文档导出 |
| 数据 API | data_api_tools.py | 22 | 雨量/水文/水库数据获取 |
| UI 工具 | ui_tools.py | 9 | 页面跳转、调度方案、预演指令 |
| 水库调度 | reservoir_dispatch.py | 13 | 水库调度方案对比、模拟 |

### 预报模型工具 (forecast_models.py) — 11 个

- `run_rainfall_forecast_model` — 执行降雨预报模型
- `run_water_forecast_model` — 执行来水预报模型
- `generate_dispatch_scheme` — 一键生成调度方案单
- `run_xinanjiang_model` — 运行新安江水文模型
- `rainfall_similarity_analysis` — 降雨图斑相似性分析
- `modify_dispatch_param` — 查看/修改调度参数
- `set_flow_constraint` — 设置站点流量约束
- `list_parameter_templates` — 列出参数模板
- `show_parameter_template` — 查看模板参数详情
- `apply_parameter_template` — 应用参数模板
- `verify_dispatch_result` — 验证调度结果

## 工具函数分类

`src/utils/` 目录下按业务功能分类的工具函数，便于代码复用和维护：

| 模块 | 功能 | 关键函数 |
|------|------|---------|
| `date_utils.py` | 时间格式化 | `format_timestamp`, `format_date_fields` |
| `data_api_utils.py` | 数据 API 请求 | `api_get`, `api_post`, `get_session` |
| `reservoir_utils.py` | 水库水位判断 | `judge_water_level_warning`, `add_water_level_description` |
| `mdb_utils.py` | MDB 数据库操作 | `mdb_execute`, `mdb_update_field`, `mdb_insert_rows` |
| `dispatch_utils.py` | 调度方案生成 | `generate_xiaolangdi_scheme_core`, `generate_sanmenxia_scheme_core` |
| `flood_utils.py` | 淹没分析 | `calculate_flood_submergence`, `check_dongpinghu_diversion` |
| `stats_utils.py` | 统计计算 | `calculate_reservoir_stats`, `calculate_hydrologic_stats` |
| `xinanjiang_utils.py` | 新安江模型辅助 | `build_control_params`, `build_rainfall_array` |
| `warning_utils.py` | 预警等级判断 | `get_xiaolangdi_warning_core`, `get_yellow_river_emergency_response_core` |
| `template_utils.py` | 模板处理 | `scan_templates`, `generate_natural_language_summary` |
| `station_codes.py` | 站点编码映射 | `get_reservoir_code`, `get_hydrology_code` |

## 数据库

### Access 数据库 (`6/data.mdb`)

核心数据库，存储调度参数和计算结果：

| 表名 | 说明 |
|------|------|
| `Dispatch_Par` | 调度参数（46 条，stcd 1-46） |
| `Q_Inputsd` | 上游入库流量（Excel 导入） |
| `Q_Inputxd` | 下游入库流量（Excel 导入） |
| `Q_Output` | 出库流量计算结果（exe 运行后生成） |
| `Z_Output` | 水库水位/蓄量计算结果（exe 运行后生成） |

### SQLite 数据库 (`storage/flood_control.db`)

存储系统配置、方案数据、历史记录等。


## Skill 文件

提供给 DeerFlow 等智能体框架使用：

| Skill | 路径 | 说明 |
|-------|------|------|
| FloodControlMCP | `skills/custom/flood-control-mcp/SKILL.md` | 完整 MCP 工具使用指南（74 个工具） |
| FloodFourPre | `skills/custom/flood-four-pre/SKILL.md` | 防洪四预工作流（预报→预警→预演→预案） |
| ScheduleDispatch | `skills/custom/schedule-dispatch/SKILL.md` | 调度方案生成工作流 |

## 架构

```
Agent ←→ MCP (FastMCP, HTTP/8082)
           ├── Access 数据库 (data.mdb)
           ├── RegualDispacth.exe (调度计算)
           ├── SQLite 数据库 (flood_control.db)
           ├── 外部 API (数据/新安江/图斑分析/水文预报/来水预报)
           └── WebSocket → UE 场景
```

## 测试

```bash
# 全功能系统测试
uv run python test/mcp_full_system_test.py

# 流量约束 + 水库统计测试
uv run python test/test_new_flow_feature.py

# 参数模板测试
uv run python test/test_parameter_templates.py

# 清空数据库表后测试
uv run python test/clear_and_test.py
```

## 认证配置

MCP 服务支持两种认证模式：API Key 和 OAuth 2.1，通过 `.env` 文件配置。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MCP_AUTH_ENABLED` | 是否启用认证 | `false` |
| `MCP_AUTH_MODE` | 认证模式：`api_key` 或 `oauth` | `api_key` |
| `MCP_AUTH_API_KEY` | API Key 模式的单个密钥 | 空 |
| `MCP_SERVER_BASE_URL` | 服务基础 URL（OAuth 元数据中公布的端点地址） | `http://localhost:8082` |
| `MCP_ALLOWED_ORIGINS` | 允许的跨域源（逗号分隔） | `http://localhost:8082,http://localhost:3000` |
| `MCP_OAUTH_USERS` | OAuth 授权页面的登录用户（格式：`user:pass,user2:pass2`） | 空 |

### API Key 模式

简单直接，适合内部服务或开发环境。

```env
MCP_AUTH_ENABLED=true
MCP_AUTH_MODE=api_key
MCP_AUTH_API_KEY=your-secret-api-key
```

客户端调用时在请求头中携带 `Authorization: Bearer <api-key>`：

```bash
curl -H "Authorization: Bearer your-secret-api-key" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
     http://localhost:8082/mcp
```

### OAuth 2.1 模式

适合生产环境，支持完整的授权码流程（PKCE）、令牌刷新和撤销。

#### 配置步骤

**1. 配置用户和客户端**

```env
MCP_AUTH_ENABLED=true
MCP_AUTH_MODE=oauth
MCP_OAUTH_USERS=admin:123456,user:123456
```

`MCP_OAUTH_USERS` 定义的是**授权页面的登录用户**（人的身份），用于在 `/authorize` 页面登录授权。

**2. 注册 OAuth 客户端**

OAuth 客户端代表**调用 MCP 接口的应用程序**（应用的身份）。需要在 `data/oauth/clients.json` 中预注册：

```bash
mkdir -p data/oauth
python3 -c "
import json
clients = {
    'my-mcp-app': {
        'client_id': 'my-mcp-app',
        'client_secret': 'my-secret',
        'redirect_uris': ['http://localhost:3000/callback'],
        'grant_types': ['authorization_code', 'refresh_token'],
        'response_types': ['code'],
        'token_endpoint_auth_method': 'client_secret_post',
        'scope': 'mcp_access'
    }
}
with open('data/oauth/clients.json', 'w') as f:
    json.dump(clients, f, indent=2)
print('客户端注册成功')
"
```

> **注意**：`redirect_uris` 必须包含 MCP 客户端实际的回调地址，否则授权时会报错 `Redirect URI not registered for client`。例如 MCP 客户端回调地址为 `http://127.0.0.1:8088/api/mcp/oauth/callback`，则需要将其添加到 `redirect_uris` 中。

**3. 启动服务**

```bash
uv run python -c "from src.server import run_server; run_server()"
```

#### 完整 OAuth 流程

```
MCP 客户端                     MCP 服务 (端口 8082)
    │                               │
    │  1. 获取 OAuth 元数据          │
    │──── GET /.well-known/oauth-authorization-server ────→│
    │←─── {authorization_endpoint, token_endpoint, ...} ──│
    │                               │
    │  2. 请求授权码                 │
    │──── GET /authorize?response_type=code&client_id=... ─→│
    │←─── 302 → redirect_uri?code=xxx ───────────────────│
    │                               │
    │  3. 交换令牌                   │
    │──── POST /token (grant_type=authorization_code) ────→│
    │←─── {access_token, refresh_token, expires_in} ─────│
    │                               │
    │  4. 调用 MCP 接口              │
    │──── POST /mcp (Authorization: Bearer <access_token>) ─→│
    │←─── {jsonrpc, result} ──────────────────────────────│
    │                               │
    │  5. 刷新令牌（令牌过期后）      │
    │──── POST /token (grant_type=refresh_token) ─────────→│
    │←─── {access_token, refresh_token} ─────────────────│
```

#### MCP 客户端配置

以 `claude_desktop_config.json` 为例：

```json
{
  "mcpServers": {
    "FloodControlMCP": {
      "transport": "streamable-http",
      "url": "http://localhost:8082/mcp",
      "auth": {
        "type": "oauth",
        "authorization_url": "http://localhost:8082/authorize",
        "token_url": "http://localhost:8082/token",
        "scope": "mcp_access",
        "redirect_uri": "http://localhost:3000/callback"
      }
    }
  }
}
```

如果客户端在不同的网络环境（如 Docker 容器），需要将 `MCP_SERVER_BASE_URL` 改为客户端可访问的地址（如 `http://172.20.35.230:8082`）。

> **注意**：OAuth 2.1 规范要求非 `localhost` 的 issuer URL 必须使用 HTTPS。如果通过 IP 地址访问，需要配置 HTTPS 反向代理。

#### OAuth 端点

| 端点 | 用途 |
|------|------|
| `/.well-known/oauth-authorization-server` | OAuth 服务器元数据（自动发现） |
| `/.well-known/oauth-protected-resource/mcp` | 受保护资源元数据 |
| `/authorize` | 授权码端点 |
| `/token` | 令牌端点（颁发/刷新令牌） |
| `/mcp` | MCP 协议端点 |

#### 数据存储

OAuth 数据存储在 `data/oauth/` 目录下的 JSON 文件中：

| 文件 | 内容 | 生命周期 |
|------|------|---------|
| `clients.json` | 已注册的客户端（需手动预配） | 永久 |
| `users.json` | 用户账号（启动时从 `MCP_OAUTH_USERS` 自动创建） | 永久 |
| `auth_codes.json` | 临时授权码 | 5 分钟 |
| `access_tokens.json` | 访问令牌 | 1 小时 |
| `refresh_tokens.json` | 刷新令牌 | 7 天 |

> **注意**：生产环境建议改用数据库存储，并由专业的 OAuth 身份提供商（如 Auth0、Keycloak）管理认证。

## 注意事项

1. **参数模板不可修改**：`Parameter_template/` 目录下的模板文件为只读参考，用户可复制参数到 Access 数据库或通过自然语言对话修改数据库，但不能修改模板文件
2. **需要 Access 数据库驱动**：Windows 系统需安装 Microsoft Access Database Engine
3. **RegualDispacth.exe**：需放置在项目根目录下
4. **编码问题**：Windows 系统建议设置 `PYTHONUTF8=1` 环境变量避免编码错误
5. **配置管理**：所有服务配置统一通过 `.env` 文件管理，由 `settings.py` 提供访问接口
6. **工具函数抽取**：tools 文件仅保留工具定义和业务流程编排，通用逻辑抽取到 `src/utils/` 目录
