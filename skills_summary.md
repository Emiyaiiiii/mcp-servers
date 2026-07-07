# 防洪四预系统 - 数据工具与技能统计

## 一、数据工具（MCP Tools）

### 1.1 数据API工具 (`data_api_tools.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `get_rainfall_station_info` | 获取雨量站基本信息 | `station` |
| `get_realtime_rainfall` | 获取实时雨量监测数据 | `start_time`, `end_time` |
| `get_daily_rainfall_stats` | 获取时段日降雨量统计 | `station`, `start_date`, `end_date` |
| `get_rainfall_statistics` | 获取实时雨量统计结果 | `start_time`, `end_time` |
| `get_river_station_info` | 获取河道水文站基本信息 | `station` |
| `list_hydrological_stations` | 获取水文站基本信息列表 | 无 |
| `list_design_flood_results` | 获取设计洪水成果信息 | `station` |
| `get_hydrological_features` | 获取水文站水文特征统计 | `station` |
| `list_water_level_sections` | 获取监测水位断面列表 | `season_code`, `station` |
| `list_realtime_hydrology` | 获取水文站实时水情 | `station`, `start_date`, `end_date` |
| `list_daily_hydrology` | 获取水文站日均水情 | `station`, `start_date`, `end_date` |
| `get_reservoir_features` | 获取水库特性 | `reservoir` |
| `list_reservoir_level_capacity` | 获取水库水位库容曲线 | `reservoir` |
| `list_reservoir_features` | 获取水库特征值信息 | `reservoir` |
| `get_reservoir_realtime` | 获取水库实时水情 | `reservoir`, `start_date`, `end_date` |
| `get_river_latest_realtime` | 获取河道水文站最新实时水情 | 无 |
| `get_reservoir_latest_realtime` | 获取水库最新实时水情 | 无 |

### 1.2 预案工具 (`plan_tools.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `list_plan_templates` | 列出所有可用的预案模板 | 无 |
| `load_plan_template` | 自动查询数据并生成完整洪水调度预案 | `generation_time`, `scheme_id` |
| `query_knowledge_base` | 查询防洪知识库 | `query`, `mode`, `source`, `top_k` |
| `generate_xiaolangdi_scheme` | 生成小浪底水库机组孔洞调度方案 | `date`, `liu_liang`, `shui_wei`, `han_sha_liang` |

### 1.3 预报模型工具 (`forecast_models.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `run_rainfall_forecast_model` | 执行降雨预报模型 | `basin`, `start_time`, `end_time`, `rainfall_data` |
| `run_water_forecast_model` | 执行设计院分布式水文来水预报模型 | `station_type`, `station_name`, `start_time`, `end_time` |
| `generate_dispatch_scheme` | 生成调度方案单 | `start_time` |
| `run_xinanjiang_model` | 运行新安江水文模型 | `station_name`, `start_time`, `end_time`, `custom_params` |

### 1.4 UI导航工具 (`ui_tools.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `navigate_to_reservoir_overview` | 跳转到水库总览页面 | 无 |
| `navigate_to_reservoir_detail` | 跳转到指定水库实时数据详情 | `reservoir_name`, `start_time`, `end_time` |
| `navigate_to_station_overview` | 跳转到水文站总览页面 | 无 |
| `navigate_to_station_detail` | 跳转到指定水文站实时数据详情 | `station_name`, `start_time`, `end_time` |
| `navigate_to_rainfall_overview` | 跳转到降雨信息总览页面 | 无 |
| `navigate_to_rainfall_basin` | 跳转到指定流域降雨信息 | `basin`, `start_time`, `end_time` |
| `navigate_to_similar_rainfall_page` | 跳转到相似雨分析页面 | `start_time`, `end_time` |
| `navigate_to_reservoir_forecast_page` | 跳转到水库预报页面 | `reservoir_name`, `start_time`, `end_time` |
| `navigate_to_control_guidance_overview` | 跳转到控导信息总览 | 无 |
| `navigate_to_control_guidance_section` | 跳转到指定河段控导信息 | `section_name` |
| `navigate_to_station_forecast_page` | 跳转到水文站预报页面 | `station_name`, `start_time`, `end_time` |
| `send_simulation_command` | 向前端发送预演指令 | `scheme_id` |
| `trigger_simulation_execution` | 触发预演执行 | `task_id` |
| `send_plan_document_url` | 发送预案文档URL | `document_url`, `document_name` |
| `show_evacuation_routes` | 显示撤离转移路线标注 | `village_ids` |
| `clear_evacuation_routes` | 清除转移路线标注 | `route_ids` |

### 1.5 3D场景控制工具 (`simulation_tools.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `fly_to_location` | 控制相机飞向指定位置 | `location_name` |
| `control_floodgate` | 控制水库闸门开闭 | `reservoir_name`, `gate_type`, `gate_index`, `is_open` |
| `set_reservoir_water_level` | 设置水库水位 | `reservoir_name`, `water_level` |
| `create_water_level_placemark` | 创建水库水位标签 | `placemark_id`, `reservoir_name`, `water_level`, `altitude_offset` |
| `update_water_level_placemark` | 更新水位标签名称 | `placemark_id`, `water_level` |
| `destroy_placemarks` | 删除标签 | `placemark_ids` |
| `get_available_locations` | 获取可用位置列表 | 无 |

### 1.6 水库调度工具 (`reservoir_dispatch.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `run_xiaolangdi_compensation_dispatch` | 调用小浪底水库补偿调度模式 | `qy`, `sw`, `ck`, `qujian`, `num1`, `zmin`, `dq`, `dtt`, `ze`, `q0`, `z0`, `time`, `reservoir_id`, `zv`, `zqxl` |
| `run_xiaolangdi_water_level_control` | 调用小浪底水库水位控制模式 | `qy`, `sw`, `qujian`, `zmin`, `num1`, `dq`, `dtt`, `ze`, `q0`, `z0`, `time`, `reservoir_id`, `zv`, `zqxl` |

### 1.7 预警工具 (`warning_tools.py`)

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `check_water_level_warning` | 判断预报水位是否超预警 | `reservoir`, `forecast_water_level`, `warning_level`, `flood_limit_level` |
| `check_flow_warning` | 判断预报流量是否超预警 | `section`, `forecast_flow`, `warning_flow` |
| `generate_warning_bulletin` | 生成预警简报 | `reservoir`, `current_water_level`, `forecast_water_level`, `warning_level` |
| `get_xiaolangdi_warning_level` | 判断小浪底预警等级 | `tongguan_flow`, `reservoir_level`, `outflow_flow` |
| `get_sanmenxia_warning_level` | 判断三门峡预警等级 | `longmen_flow`, `tongguan_flow`, `huaxian_flow` |
| `get_yellow_river_emergency_response` | 判断黄河总体应急响应等级 | 多参数（各水库水位、各水文站流量） |

---

## 二、Skills技能

### 2.1 自定义技能（Custom）

#### 2.1.1 flood-four-pre - 五库联调防洪四预业务技能

**激活场景**：当用户提出防洪调度需求（如进行五库联调）时激活

**支持水库**：陆浑、故县、三门峡、小浪底、河口村

**四预流程**：
1. **第一步**：查询五库水情并获取调度方案
2. **第二步**：执行预演
3. **第三步**：等待用户触发预演或生成预案
4. **第四步**：生成预案

**重要限制**：目前仅支持针对2021年秋汛（10月2日至10月7日）的调度方案生成

---

#### 2.1.2 xinanjing-forecast - 新安江水文模型来水预报

**激活场景**：当用户要求运行新安江模型进行来水预报、对比真实入库数据、或进行偏差分析时激活

**适用站点**：小浪底水库（当前仅接入小浪底单库雨量站数据）

**可调参数**：
| 参数 | 含义 | 默认值 |
|------|------|--------|
| KC | 流域蒸散发折算系数 | 0.9 |
| B | 流域蓄水容量分布曲线指数 | 0.4 |
| UM | 上层张力水容量 | 30mm |
| LM | 下层张力水容量 | 80mm |
| SM | 自由水容量 | 25mm |
| KG | 地下水日出流系数 | 0.3 |
| KI | 壤中流日出流系数 | 0.3 |
| XE | 马斯京跟法演算参数 | 0.2 |

**处理流程**：确认信息 → 运行模型+跳转页面 → 展示结果 → 对比真实数据 → 偏差分析

---

### 2.2 公共技能（Public）

| 技能名称 | 功能描述 | 典型触发场景 |
|---------|---------|-------------|
| `deep-research` | 系统性深度网络研究方法论 | "what is X", "explain X", "research X", 内容生成前的调研 |
| `data-analysis` | 数据分析技能，支持Excel/CSV文件的SQL查询、统计汇总、结果导出 | 用户上传数据文件并请求分析 |
| `chart-visualization` | 图表可视化技能，支持26种图表类型 | 用户需要可视化数据 |
| `frontend-design` | 前端设计技能 | 网页/应用界面设计 |
| `github-deep-research` | GitHub深度研究 | 分析GitHub项目、代码仓库 |
| `image-generation` | 图片生成技能 | 生成图片内容 |
| `newsletter-generation` | 新闻通讯生成 | 生成新闻稿、简报 |
| `podcast-generation` | 播客生成 | 生成播客内容 |
| `ppt-generation` | PPT演示文稿生成 | 创建演示文稿 |
| `skill-creator` | 技能创建工具 | 创建新的AI技能 |
| `surprise-me` | 惊喜推荐技能 | 提供随机推荐 |
| `systematic-literature-review` | 系统性文献综述 | 学术文献分析 |
| `vercel-deploy-claimable` | Vercel部署 | 部署Web应用到Vercel |
| `video-generation` | 视频生成技能 | 生成视频内容 |
| `web-design-guidelines` | 网页设计指南 | 网页设计规范指导 |
| `academic-paper-review` | 学术论文评审 | 评审学术论文 |
| `code-documentation` | 代码文档生成 | 生成代码文档 |
| `consulting-analysis` | 咨询分析技能 | 提供咨询分析服务 |
| `claude-to-deerflow` | Claude到DeerFlow转换 | 相关服务转换 |
| `find-skills` | 技能查找工具 | 查找可用技能 |
| `bootstrap` | Bootstrap框架相关 | Bootstrap项目构建 |

---

## 三、工具分类汇总

### 3.1 按功能分类

| 类别 | 工具数量 | 主要用途 |
|------|---------|---------|
| 数据查询 | 17 | 雨量站、水文站、水库数据查询 |
| 预案管理 | 4 | 预案模板、调度方案、知识库 |
| 预报模型 | 4 | 降雨预报、来水预报、新安江模型 |
| UI导航 | 13 | 页面跳转、预演控制、路线显示 |
| 3D场景 | 7 | 相机控制、闸门控制、水位设置 |
| 水库调度 | 2 | 补偿调度、水位控制模式 |
| 预警判断 | 6 | 水位预警、流量预警、应急响应 |

### 3.2 技能分类

| 类别 | 数量 | 说明 |
|------|------|------|
| 自定义技能 | 2 | 防洪四预业务专用 |
| 公共技能 | 22 | 通用AI技能 |

---

## 四、核心业务流程

```
五库联调四预流程
    ↓
查询五库水情数据
    ↓
生成调度方案 (generate_dispatch_scheme)
    ↓
发送预演指令 (send_simulation_command)
    ↓
触发预演执行 (trigger_simulation_execution)
    ↓
生成预案文档 (load_plan_template)
    ↓
发送文档URL (send_plan_document_url)
```

---

*文档生成时间：2026年6月*
*数据来源：mcp-servers/src/tools/ 及 mcp-servers/skills/*