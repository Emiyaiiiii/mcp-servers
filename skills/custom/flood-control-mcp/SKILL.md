---
name: flood-control-mcp
description: 防洪四预 MCP 服务完整技能指南。覆盖调度参数修改、方案单生成、防洪四预流程、数据查询、预报模型、预警评估、水库调度、前端交互等全部工具。当智能体框架需要使用防洪四预 MCP 服务时激活此技能。
---

# 防洪四预 MCP 服务技能指南

本技能为智能体框架（如 DeerFlow、Hermes 等）提供防洪四预 MCP 服务的完整调用指引。

## 服务信息

| 项目 | 值 |
|------|-----|
| 服务名 | FloodControlMCP |
| 版本 | 3.2.3 |
| 协议 | MCP 2025-11-25 |
| 传输方式 | streamable-http |
| 地址 | `http://localhost:8082/mcp` |
| 工具总数 | 74 个 |

---

## 一、工具总览（按业务分类）

### 1. 调度参数与方案单生成（6 个）

| 工具 | 用途 |
|------|------|
| `modify_dispatch_param` | 查看/修改 `Dispatch_Par` 表调度参数 |
| `set_flow_constraint` | 设置站点流量约束，自动调整相关 Dispatch_Par 参数 |
| `generate_dispatch_sheet` | 一键生成调度方案单（导入Excel→运行exe→导出结果） |
| `generate_dispatch_scheme` | 生成五库联调调度方案（基于2021年秋汛） |
| `generate_xiaolangdi_scheme` | 生成小浪底调度方案 |
| `generate_sanmenxia_scheme` | 生成三门峡调度方案 |

### 2. 数据查询（15+ 个）

| 工具 | 用途 |
|------|------|
| `get_reservoir_latest_realtime` | 水库最新实时水情 |
| `get_reservoir_realtime` | 水库指定时段历史水情 |
| `get_reservoir_features` | 水库特性信息 |
| `get_reservoir_warning` | 水库预警信息 |
| `get_reservoir_period_comparison` | 水库同期对比 |
| `get_river_latest_realtime` | 河道水文站最新实时水情 |
| `get_river_station_info` | 水文站基本信息 |
| `list_hydrological_stations` | 水文站列表 |
| `list_realtime_hydrology` | 水文站时段水情 |
| `list_daily_hydrology` | 水文站日水情 |
| `list_design_flood_results` | 设计洪水成果 |
| `get_hydrological_features` | 水文站水文特征 |
| `list_water_level_sections` | 水位断面列表 |
| `get_rainfall_station_info` | 雨量站基本信息 |
| `get_rainfall_statistics` | 雨量统计 |
| `get_river_period_comparison` | 水文站同期对比 |

### 3. 预报模型（3 个）

| 工具 | 用途 |
|------|------|
| `run_rainfall_forecast_model` | 降雨预报模型 |
| `run_water_forecast_model` | 设计院分布式来水预报模型 |
| `run_xinanjiang_model` | 新安江水文模型（计算区间来水） |

### 4. 预警评估（6 个）

| 工具 | 用途 |
|------|------|
| `check_water_level_warning` | 水位预警判断 |
| `check_flow_warning` | 流量预警判断 |
| `generate_warning_bulletin` | 生成预警通报 |
| `get_xiaolangdi_warning_level` | 小浪底预警等级 |
| `get_sanmenxia_warning_level` | 三门峡预警等级 |
| `get_yellow_river_emergency_response` | 黄河应急响应等级 |

### 5. 水库调度（2 个）

| 工具 | 用途 |
|------|------|
| `run_xiaolangdi_compensation_dispatch` | 小浪底补偿调度 |
| `run_xiaolangdi_water_level_control` | 小浪底水位控制 |

### 6. 防洪四预流程（4 个）

| 工具 | 用途 |
|------|------|
| `send_simulation_command` | 向前端发送预演指令 |
| `trigger_simulation_execution` | 触发预演执行 |
| `load_plan_template` | 加载预案模板并生成预案 |
| `send_plan_document_url` | 发送预案文档URL给前端 |

### 7. 预案与知识库（4 个）

| 工具 | 用途 |
|------|------|
| `list_plan_templates` | 列出预案模板 |
| `query_knowledge_base` | 知识库检索 |
| `get_risk_by_huayuankou_flow` | 花园口流量风险评估 |
| `get_flood_submerge` | 滩区淹没分析 |

### 8. 前端交互（12 个）

| 工具 | 用途 |
|------|------|
| `navigate_to_reservoir_overview` | 跳转水库总览 |
| `navigate_to_reservoir_detail` | 跳转水库详情 |
| `navigate_to_station_overview` | 跳转水文站总览 |
| `navigate_to_station_detail` | 跳转水文站详情 |
| `navigate_to_rainfall_overview` | 跳转降雨总览 |
| `navigate_to_rainfall_basin` | 跳转流域降雨 |
| `navigate_to_similar_rainfall_page` | 跳转相似降雨 |
| `navigate_to_reservoir_forecast_page` | 跳转水库预报 |
| `navigate_to_station_forecast_page` | 跳转水文站预报 |
| `navigate_to_control_guidance_overview` | 跳转控导总览 |
| `navigate_to_control_guidance_section` | 跳转控导断面 |
| `show_evacuation_routes` | 显示撤离路线 |
| `clear_evacuation_routes` | 清除撤离路线 |

### 9. 参数模板（4 个）

| 工具 | 用途 |
|------|------|
| `list_parameter_templates` | 列出所有可用的参数模板（类别、名称、参数条数、结果 sheet） |
| `show_parameter_template` | 展示指定模板的完整 46 条参数设置 |
| `apply_parameter_template` | 将模板参数写入 Dispatch_Par 表，可选自动生成调度方案单 |
| `verify_dispatch_result` | 对比实际计算结果与模板预期结果，输出验证报告 |

---

## 二、核心工具详细说明

### 2.1 modify_dispatch_param — 调度参数修改

**用途**：查看和修改 `data.mdb` 中 `Dispatch_Par` 表的调度参数。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `action` | string | 是 | `"list"` 查看所有参数，`"update"` 修改参数 |
| `station_name` | string | update时必填 | 站点名称（如"小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"、"花园口"、"东平湖"、"北金堤"） |
| `param_desc` | string | update时必填 | 参数关键词（如"敞泄"、"初始水位"、"防洪高水位"、"预泄流量"、"发电流量"、"分洪"等） |
| `new_value` | number | update时必填 | 新的参数值 |

**调用示例**：

```
# 查看全部参数
modify_dispatch_param(action="list")

# 修改小浪底为敞泄模式
modify_dispatch_param(action="update", station_name="小浪底", param_desc="敞泄", new_value=0)

# 修改小浪底初始水位
modify_dispatch_param(action="update", station_name="小浪底", param_desc="初始水位", new_value=250.0)

# 修改陆浑预泄流量
modify_dispatch_param(action="update", station_name="陆浑", param_desc="预泄流量", new_value=500.0)

# 设置分洪
modify_dispatch_param(action="update", station_name="东平湖", param_desc="分洪", new_value=1)

# 切换洪水类型
modify_dispatch_param(action="update", station_name="洪水类型", param_desc="洪水类型", new_value=0)
```

**匹配规则**：
- `station_name` 精确匹配 `stnm` 字段
- `param_desc` 部分匹配 `Instruction` 字段（关键词包含即可）
- 匹配到多条时会返回列表要求用户确认
- 匹配到 0 条时会返回全部可用参数列表

### 2.2 set_flow_constraint — 流量约束设置

**用途**：设置指定站点的流量约束，自动调整 `Dispatch_Par` 表中所有相关参数。一条命令完成多个参数调整，无需手动逐一修改。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `station_name` | string | 是 | 站点名称，目前支持 `"花园口"` |
| `max_flow` | number | 是 | 最大允许流量（m³/s），如 `13000` |

**自动调整的参数**（以花园口为例）：

| stcd | 站点 | 参数含义 | 调整方式 |
|------|------|---------|----------|
| 23 | 小浪底 | 预泄控制花园口流量 | 设为目标流量 - 1000 |
| 30 | 小浪底 | 保滩流量 | 设为目标流量 - 1000 |
| 38 | 花园口 | 判别库群退水时刻设置的花园口流量阈值 | 设为目标流量 |
| 39 | 花园口 | 下大洪水，退水过程控制的花园口流量 | 设为目标流量 |
| 43 | 花园口 | 判别支流水库关门时刻的花园口流量 | 设为目标流量 |
| 44 | 小浪底 | 小浪底保滩库容用完后，转控花园口的流量 | 设为目标流量 - 1000 |

**调用示例**：

```
# 控制花园口流量不超过 13000
set_flow_constraint(station_name="花园口", max_flow=13000)
```

**返回格式**：

```json
{
  "success": true,
  "command": "FUNC_SET_FLOW_CONSTRAINT",
  "station_name": "花园口",
  "max_flow": 13000,
  "updated_count": 6,
  "updated_params": [
    {"stcd": 23, "stnm": "小浪底", "instruction": "预泄控制花园口流量", "old_value": 4500, "new_value": 12000, "adjust_type": "buffer"},
    ...
  ],
  "hint": "参数已更新，请调用 generate_dispatch_sheet() 重新生成方案单验证效果"
}
```

### 2.3 generate_dispatch_sheet — 调度方案单生成

**用途**：一键生成调度方案单。自动完成：导入 Excel → 运行 RegualDispacth.exe → 导出结果到 output/ 文件夹。

**参数**：无。

**调用示例**：

```
generate_dispatch_sheet()
```

**执行流程**：
1. 从 `data/Q_Inputsd.xlsx` 和 `data/Q_Inputxd.xlsx` 读取数据
2. 导入到 `6/data.mdb` 的 `Q_Inputsd` 和 `Q_Inputxd` 表
3. 运行 `RegualDispacth.exe` 进行计算（超时 300 秒）
4. 将 `Q_Output` 表结果导出到 `output/Q_Output_<时间戳>.xlsx`

**返回格式**：

```json
{
  "success": true,
  "message": "调度方案单生成完成",
  "steps": {
    "import": {"Q_Inputsd_rows": 1780, "Q_Inputxd_rows": 8346, "elapsed_seconds": 2.5},
    "calculation": {"elapsed_seconds": 3.5, "exit_code": 0},
    "export": {"output_rows": 9630, "output_file": "output/Q_Output_xxx.xlsx", "elapsed_seconds": 0.6}
  },
  "total_elapsed_seconds": 7.0,
  "output_file": "output/Q_Output_xxx.xlsx"
}
```

### 2.4 generate_dispatch_scheme — 五库联调调度方案

**用途**：基于 2021 年秋汛真实调度数据生成五库联调方案。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start_time` | string | 否 | 调度开始时间，格式 `YYYY-MM-DD`，仅支持 2021-10-02 至 2021-10-07 |

**调用示例**：

```
generate_dispatch_scheme(start_time="2021-10-02")
```

### 2.5 参数模板工具

#### 2.5.1 list_parameter_templates — 列出所有模板

**用途**：扫描 `Parameter_template/` 目录，列出所有可用的参数模板。

**参数**：无。

**调用示例**：

```
# 查看所有模板
list_parameter_templates()
```

**返回格式**：

```json
{
  "success": true,
  "templates": [
    {
      "name": "方案一",
      "category": "上大洪水控制",
      "file_name": "方案一：（小浪底不保滩，控花园口10000）.xlsx",
      "param_count": 46,
      "result_sheets": ["三门峡", "小浪底", "下游", "特征值"]
    }
  ],
  "count": 5
}
```

#### 2.5.2 show_parameter_template — 展示模板参数

**用途**：展示指定模板的完整 46 条参数设置。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_name` | string | 是 | 模板名称关键词，支持模糊匹配（如"方案一"、"常规调度"、"上大"、"下大"） |

**调用示例**：

```
# 展示方案一参数
show_parameter_template(template_name="方案一")

# 模糊匹配（按"常规"关键词匹配下大洪水常规调度方案）
show_parameter_template(template_name="常规调度")
```

#### 2.5.3 apply_parameter_template — 应用模板并生成方案

**用途**：将模板参数写入 Dispatch_Par 表，可选自动生成调度方案单。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_name` | string | 是 | 模板名称关键词 |
| `generate_scheme` | bool | 否 | 是否自动生成方案单（默认 true） |

**调用示例**：

```
# 应用上大洪水方案一并生成方案单
apply_parameter_template(template_name="方案一")

# 按"常规方案"生成五库联调方案
apply_parameter_template(template_name="常规调度")

# 仅更新参数不生成方案
apply_parameter_template(template_name="方案二", generate_scheme=false)
```

#### 2.5.4 verify_dispatch_result — 验证计算结果

**用途**：应用参数模板生成方案后，将实际计算结果与模板预期结果进行对比验证。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_name` | string | 是 | 模板名称关键词 |

**调用示例**：

```
# 验证常规方案的调度计算结果
verify_dispatch_result(template_name="常规调度")
```

**返回格式**：

```json
{
  "success": true,
  "template_name": "方案一：演练洪水-常规调度-...",
  "scheme_id": "DS-0037",
  "verification": {
    "status": "通过",
    "message": "所有站点偏差在5%以内（最大3.2%），计算结果与预期一致",
    "total_matched_points": 3852,
    "stations_compared": ["三门峡", "小浪底", "下游"],
    "station_details": {
      "三门峡": {"matched_points": 642, "max_deviation_pct": 2.1, "avg_deviation_pct": 0.8},
      "小浪底": {"matched_points": 642, "max_deviation_pct": 3.2, "avg_deviation_pct": 1.1}
    }
  }
}
```

---

## 三、典型工作流

### 场景 A：修改调度参数后生成方案单

这是最常用的调度参数调整场景。

```
步骤 1：查看当前参数
  → modify_dispatch_param(action="list")

步骤 2：修改参数（可多次调用）
  → modify_dispatch_param(action="update", station_name="小浪底", param_desc="初始水位", new_value=251.0)
  → modify_dispatch_param(action="update", station_name="小浪底", param_desc="敞泄", new_value=1)

步骤 3：生成调度方案单
  → generate_dispatch_sheet()
```

### 场景 B：完整防洪四预流程

```
步骤 1：查询水情
  → get_reservoir_latest_realtime()
  → get_river_latest_realtime()

步骤 2：生成调度方案
  → generate_dispatch_scheme(start_time="2021-10-02")

步骤 3：执行预演（用户确认后）
  → send_simulation_command(scheme_id="DS-0001")
  → trigger_simulation_execution(task_id="...")

步骤 4：生成预案（用户确认后）
  → load_plan_template(generation_time="2021-10-02", scheme_id="DS-0001")
  → send_plan_document_url(document_url="...", document_name="...")
```

### 场景 C：预报分析

```
步骤 1：运行来水预报
  → run_water_forecast_model(station_type="reservoir", station_name="小浪底")

步骤 2：运行新安江模型
  → run_xinanjiang_model(station_name="陆浑水库", start_time="2021-10-02 00:00:00", end_time="2021-10-07 00:00:00")

步骤 3：预警评估
  → check_water_level_warning(reservoir="小浪底", forecast_water_level=270.0, warning_level=275.0)
  → check_flow_warning(section="花园口", forecast_flow=5000.0, warning_flow=4500.0)
```

### 场景 D：数据查询与前端导航

```
步骤 1：查询数据
  → get_reservoir_realtime(reservoir="小浪底", start_date="2021-10-02", end_date="2021-10-07")
  → list_realtime_hydrology(station="花园口", start_date="2021-10-02", end_date="2021-10-07")

步骤 2：前端导航（引导用户查看）
  → navigate_to_reservoir_detail(reservoir_name="小浪底", start_time="2021-10-02", end_time="2021-10-07")
```

### 场景 E：风险评估

```
步骤 1：花园口流量风险评估
  → get_risk_by_huayuankou_flow(flow=8000)

步骤 2：滩区淹没分析
  → get_flood_submerge(huayuankou_flow=8000)

步骤 3：应急响应判定
  → get_yellow_river_emergency_response(xiaolangdi_level=270.0)
```

### 场景 F：应用参数模板生成方案

这是最常用的参数模板应用场景。

```
步骤 1：查看所有模板
  → list_parameter_templates()

步骤 2：查看具体模板的参数
  → show_parameter_template(template_name="常规调度")

步骤 3：应用模板参数并生成方案单
  → apply_parameter_template(template_name="常规调度")

步骤 4（可选）：验证计算结果是否与预期一致
  → verify_dispatch_result(template_name="常规调度")
```

### 场景 G：设置流量约束控制花园口峰值

当用户需要控制某个站点（如花园口）的最大流量不超过指定值时，使用此流程自动调整参数。

```
步骤 1：设置流量约束
  → set_flow_constraint(station_name="花园口", max_flow=13000)
  → 自动调整 6 个 Dispatch_Par 参数（小浪底预泄流量、保滩流量、花园口控制阈值等）

步骤 2：重新生成调度方案单（验证效果）
  → generate_dispatch_sheet()

步骤 3（可选）：如果结果仍超标，进一步降低参数
  → set_flow_constraint(station_name="花园口", max_flow=12000)
  → generate_dispatch_sheet()
```

**调整说明**：
- "target" 类型参数（花园口控制阈值）直接设为目标流量
- "buffer" 类型参数（小浪底控制参数）设为目标流量 - 1000，留出安全余量
- 如果调整后仍超标，检查小花间（小浪底至花园口区间）天然来水是否已超过目标流量
- 如果区间来水超标，需要启用东平湖、北金堤等分洪工程

---

## 四、Dispatch_Par 参数完整目录（46 条）

| 序号 | stcd | 站点名称 | 含义 (Instruction) | 典型值 |
|------|------|----------|-------------------|--------|
| 1 | 1 | 东平湖 | 0表示不分洪，1表示分洪 | 0 / 1 |
| 2 | 2 | 北金堤 | 0表示不分洪，1表示分洪 | 0 / 1 |
| 3 | 3 | 三门峡 | 初始水位 | 295.0 |
| 4 | 4 | 小浪底 | 初始水位 | 250.86 |
| 5 | 5 | 陆浑 | 初始水位 | 316.21 |
| 6 | 6 | 故县 | 初始水位 | 524.19 |
| 7 | 7 | 河口村 | 初始水位 | 234.34 |
| 8 | 8 | 三门峡 | 0表示敞泄，1表示控泄 | 0 / 1 |
| 9 | 9 | 小浪底 | 0表示敞泄，1表示控泄 | 0 / 1 |
| 10 | 10 | 陆浑 | 0表示敞泄，1表示控泄 | 0 / 1 |
| 11 | 11 | 故县 | 0表示敞泄，1表示控泄 | 0 / 1 |
| 12 | 12 | 河口村 | 0表示敞泄，1表示控泄 | 0 / 1 |
| 13 | 13 | 三门峡 | 防洪高水位 | 335.0 |
| 14 | 14 | 小浪底 | 防洪高水位 | 275.0 |
| 15 | 15 | 陆浑 | 蓄洪限制水位 | 323.0 |
| 16 | 16 | 故县 | 蓄洪限制水位 | 546.84 |
| 17 | 17 | 河口村 | 蓄洪限制水位 | 285.43 |
| 18 | 18 | 三门峡 | 0表示完全自由敞泄关闭，1表示打开 | 0 / 1 |
| 19 | 19 | 小浪底 | 0表示预泄关闭，1表示打开 | 0 / 1 |
| 20 | 20 | 陆浑 | 0表示预泄关闭，1表示打开 | 0 / 1 |
| 21 | 21 | 故县 | 0表示预泄关闭，1表示打开 | 0 / 1 |
| 22 | 22 | 河口村 | 0表示预泄关闭，1表示打开 | 0 / 1 |
| 23 | 23 | 小浪底 | 预泄控制花园口流量 | 4500.0 |
| 24 | 24 | 陆浑 | 预泄流量 | 300.0 |
| 25 | 25 | 故县 | 预泄流量 | 300.0 |
| 26 | 26 | 河口村 | 预泄流量 | 100.0 |
| 27 | 27 | 河口村 | 花园口12000关门的最高水位 | 275.0 |
| 28 | 28 | 三门峡 | 下大洪水，三门峡给小浪底帮忙要求的小浪底蓄洪量 | 26.0 |
| 29 | 29 | 小浪底 | 4500转控10000的判别水位 | 254.0 |
| 30 | 30 | 小浪底 | 保滩流量 | 4500.0 |
| 31 | 31 | 小浪底 | 发电流量 | 300.0 |
| 32 | 32 | 陆浑 | 20年一遇以下洪水控制流量 | 1000.0 |
| 33 | 33 | 陆浑 | 发电流量 | 0.0 |
| 34 | 34 | 故县 | 20年一遇以下洪水控制流量 | 1000.0 |
| 35 | 35 | 故县 | 发电流量 | 0.0 |
| 36 | 36 | 河口村 | 254.5m以下控制武陟流量 | 2000.0 |
| 37 | 37 | 河口村 | 发电流量 | 0.0 |
| 38 | 38 | 花园口 | 判别库群退水时刻设置的花园口流量阈值 | 4500.0 |
| 39 | 39 | 花园口 | 下大洪水，退水过程控制的花园口流量 | 4500.0 |
| 40 | 40 | 小浪底 | 上大洪水，小浪底开门敞泄的滞蓄洪量阈值 | 200.0 |
| 41 | 41 | 陆浑 | 保本流域20年一遇的水位 | 321.5 |
| 42 | 42 | 故县 | 保本流域21年一遇的水位 | 542.04 |
| 43 | 43 | 花园口 | 判别支流水库关门时刻的花园口流量 | 12000.0 |
| 44 | 44 | 小浪底 | 小浪底保滩库容用完后，转控花园口的流量 | 4500.0 |
| 45 | 45 | 花园口 | 上大洪水，小浪底敞泄结束，花园口流量达到的超万洪量 | 200.0 |
| 46 | 46 | 洪水类型 | 0为上大洪水，1为下大洪水 | 0 / 1 |

---

## 五、站点编码对照

### 水库

| 名称 | 编码 |
|------|------|
| 陆浑水库 | BDA80200721 |
| 故县水库 | BDA80000661 |
| 三门峡水库 | BDA00000111 |
| 小浪底水库 | BDA00000121 |
| 河口村水库 | BDA00000761 |

### 水文站（常用）

| 名称 | 用途 |
|------|------|
| 龙门镇 | 伊洛河上游 |
| 白马寺 | 伊洛河中游 |
| 黑石关 | 伊洛河下游 |
| 花园口 | 黄河干流关键断面 |
| 泺口 | 黄河下游 |
| 艾山 | 黄河下游 |
| 孙口 | 黄河下游 |
| 高村 | 黄河下游 |
| 夹河滩 | 黄河下游 |
| 利津 | 黄河入海口 |
| 武陟 | 沁河 |
| 山路平 | 沁河 |

---

## 六、交互规则

1. **参数修改后建议先生成方案单**：修改 Dispatch_Par 参数后，调用 `generate_dispatch_sheet()` 生成新的调度方案单，以验证参数修改效果。

2. **四预流程每步确认**：防洪四预流程（方案→预演→预案）每步完成后必须等待用户确认再进入下一步。

3. **方案单唯一性**：`generate_dispatch_scheme` 仅支持 2021 年秋汛（10月2日至10月7日），基于唯一一套真实调度数据。

4. **前端工具需配合使用**：导航类工具（`navigate_to_*`）和预演类工具（`send_simulation_command`）需要前端界面配合才能看到效果。

5. **错误处理**：所有工具返回 `{"success": false, "error": "..."}` 格式，智能体应解析 error 字段并向用户展示具体错误原因。

6. **参数匹配提示**：当 `modify_dispatch_param` 匹配到多条记录时，不要自动选择，应将匹配列表展示给用户确认。