---
name: flood-data-query
description: 查询防洪四预系统的实时数据，包括水库/水文站水情、降雨数据、场景位置、控导信息等。当用户询问水位、流量、降雨量、闸门情况或需要查看具体场景时调用此技能。注意：实时数据查询优先使用实时数据页面，预报查询仅在用户明确提到"预报"时使用。
---

# 防洪数据查询技能

本技能用于查询防洪四预系统的各类实时数据。遵循**先跳转页面，再查询数据**的流程。

## 重要原则

**实时数据优先原则**：

- 查询当前水位、流量、降雨量 → 跳转到**实时数据页面**
- 查询历史数据 → 跳转到**实时数据页面**并指定时间范围
- 只有用户明确提到"预报"、"预测"、"未来"时 → 才跳转到**预报页面**

## 核心工具

| 工具类别     | 工具名称                                  | 用途               |
| -------- | ------------------------------------- | ---------------- |
| **页面跳转** | `navigate_to_reservoir_overview`       | 跳转到水库总览页面      |
| **页面跳转** | `navigate_to_reservoir_detail`         | 跳转到水库详情页面      |
| **页面跳转** | `navigate_to_station_overview`        | 跳转到水文站总览页面     |
| **页面跳转** | `navigate_to_station_detail`          | 跳转到水文站详情页面     |
| **页面跳转** | `navigate_to_rainfall_overview`        | 跳转到降雨信息总览页面   |
| **页面跳转** | `navigate_to_rainfall_basin`          | 跳转到指定流域降雨页面   |
| **页面跳转** | `navigate_to_similar_rainfall_page`   | 跳转到相似雨分析页面    |
| **页面跳转** | `navigate_to_reservoir_forecast_page` | 跳转到水库预报页面     |
| **页面跳转** | `navigate_to_station_forecast_page`   | 跳转到水文站预报页面    |
| **页面跳转** | `navigate_to_control_guidance_overview` | 跳转到控导总览页面     |
| **页面跳转** | `navigate_to_control_guidance_section` | 跳转到指定河段控导页面   |
| **数据查询** | `get_reservoir_latest_realtime`       | 查询水库最新实时水情     |
| **数据查询** | `get_river_latest_realtime`           | 查询河道水文站最新实时水情 |
| **数据查询** | `get_rainfall_statistics`               | 查询实时雨量监测数据    |
| **数据查询** | `get_reservoir_realtime`              | 查询水库实时水情（指定水库）|
| **数据查询** | `list_realtime_hydrology`             | 查询水文站实时水情（指定水文站）|
| **场景控制** | `fly_to_location`                     | 飞向指定水库场景位置    |
| **模型计算** | `run_rainfall_forecast_model`         | 执行降雨预报模型       |
| **知识查询** | `query_knowledge_base`                | 查询防洪知识库         |

## 查询流程

### 一、实时数据查询（优先使用）

#### 1. 水库实时数据查询（最重要！）

**判断规则**：

- 用户问题中**提到具体水库名称**（如"三门峡"、"小浪底"、"陆浑"、"故县"、"河口村"）→ 调用 `navigate_to_reservoir_detail(reservoir_name="水库名称", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`
- 用户问题中**没有提到具体水库**（如"查看水库总览"、"查看五个水库情况"）→ 调用 `navigate_to_reservoir_overview()`

**示例**：

| 用户问法              | 使用的工具                                                                        |
| ----------------- | --------------------------------------------------------------------- |
| "**三门峡**现在水位多少"   | navigate\_to\_reservoir\_detail(reservoir\_name="三门峡", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") |
| "**小浪底**当前出库流量"   | navigate\_to\_reservoir\_detail(reservoir\_name="小浪底", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") |
| "**陆浑**水库水位"      | navigate\_to\_reservoir\_detail(reservoir\_name="陆浑", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00")  |
| "查看**五个水库**的实时情况" | navigate\_to\_reservoir\_overview() |
| "水库总览"            | navigate\_to\_reservoir\_overview() |

**五个水库名称（必须用中文）**：

- 陆浑
- 故县
- 三门峡
- 小浪底
- 河口村

**流程**:

1. 首先判断用户是否指定了水库名称
2. 如果指定了，调用 `navigate_to_reservoir_detail(reservoir_name="具体水库名", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`
3. 然后调用 `get_reservoir_realtime(reservoir="具体水库名", start_date="2026-04-15", end_date="2026-04-18")`

#### 2. 水文站实时数据查询

**判断规则**：

- 用户问题中**提到具体水文站名称**（如"花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"）→ 调用 `navigate_to_station_detail(station_name="水文站名称", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`
- 用户问题中**没有提到具体水文站** → 调用 `navigate_to_station_overview()`

**示例**：

| 用户问法          | 使用的工具                                                                      |
| ------------- | ----------------------------------------------------------------------- |
| "**花园口**流量多少" | navigate\_to\_station\_detail(station\_name="花园口", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") |
| "**高村**当前水位"  | navigate\_to\_station\_detail(station\_name="高村", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00")  |
| "查看水文站实时数据"   | navigate\_to\_station\_overview() |

**六个水文站名称（必须用中文）**：

- 花园口
- 高村
- 孙口
- 艾山
- 泺口
- 利津

**流程**:

1. 首先判断用户是否指定了水文站名称
2. 如果指定了，调用 `navigate_to_station_detail(station_name="具体水文站名", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`
3. 然后调用 `list_realtime_hydrology(station="具体水文站名", start_date="2026-04-15", end_date="2026-04-18")`

#### 3. 实时降雨数据查询

**用户问法示例**：

- "过去24小时降雨量"
- "最近的降雨情况"

**流程**: 调用 `navigate_to_rainfall_overview()` 跳转降雨总览页面 → 调用 `get_realtime_rainfall(start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")` 查询降雨数据

#### 4. 相似雨数据分析

**用户问法示例**：

- "做相似雨分析"

**流程**: 调用 `navigate_to_similar_rainfall_page(start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")` 跳转页面 → 直接回复跳转成功即可

#### 5. 查询控导信息

**用户问法示例**：

- "马庄控导情况"

**流程**: 调用 `navigate_to_control_guidance_section(section_name="马庄")` 跳转控导页面 → 简单回复跳转成功即可

***

### 二、预报数据查询（仅用户明确提到"预报"时使用）

#### 6. 水库降雨预报查询

**用户问法示例**：

- "三门峡水库未来水位预报"
- "预测小浪底的降雨预报"

**流程**:

1. 调用 `navigate_to_reservoir_forecast_page(reservoir_name="水库名称", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")` 跳转预报页面
2. 调用 `get_realtime_rainfall(start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")` 获取降雨数据
3. 调用 `run_rainfall_forecast_model(basin=..., start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00", rainfall_data=...)` 执行降雨预报模型

#### 7. 水文站降雨预报查询

**用户问法示例**：

- "花园口水文站未来流量预报"

**流程**: 调用 `navigate_to_station_forecast_page(station_name="水文站名称", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")` 跳转预报页面

***

### 三、场景控制

#### 8. 查看具体场景

**用户问法示例**：

- "看看小浪底的场景"
- "飞到三门峡"

**流程**: 调用 `fly_to_location(location_name="")` 飞向UE场景位置 → 回复跳转结果

**可用位置**: SanMenXia(三门峡), XiaoLangDi(小浪底), LuHun(陆浑), GuXian(故县), HeKouCun(河口村)

### 四、知识库检索（补充信息时使用）

#### 9. 查询防洪知识库

**用户问法示例**：

- "水库调度的原则是什么"
- "防洪预演的流程"
- "预警响应的等级有哪些"
- "应急处置措施有哪些"

**判断规则**：

- 用户询问防洪相关的知识、原理、流程、规范等非实时数据问题时使用
- 可在提供实时数据后，根据需要补充知识库信息

**流程**: 调用 `query_knowledge_base(query="查询关键词", mode="mix")` 获取知识库信息

**支持的查询模式**：

| 模式 | 说明 |
| ---- | ---- |
| `local` | 返回实体及其直接关系 + 相关文本片段 |
| `global` | 返回知识图谱中的关系模式 |
| `hybrid` | 结合本地和全局检索策略 |
| `naive` | 仅返回向量检索文本片段 |
| `mix` | 知识图谱数据与向量检索结合（默认） |

**返回数据结构**：

```json
{
    "success": true,
    "query": "水库调度",
    "mode": "mix",
    "entities": [...],
    "relationships": [...],
    "chunks": [...],
    "references": [...],
    "summary": "【内容片段】...\n【实体】...\n【关系】..."
}
```

## 响应格式

### 页面跳转响应

返回跳转命令发送结果，包含:

- `success`: 是否成功
- `command`: 发送的命令类型
- `reservoir_code`/`station_code`: 关联的编码
- `response`: UE场景响应

### 数据查询响应

返回查询的数据，包含:

- `code`: 状态码 (200=成功)
- `data`: 查询到的数据
- `msg`: 状态消息

## 常见查询场景（必须严格按照此表执行）

| 用户问法              | 工具调用（必须带参数）                                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------------------- |
| "**三门峡**现在水位多少"   | navigate\_to\_reservoir\_detail(reservoir\_name="三门峡", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") + get\_reservoir\_realtime(reservoir="三门峡", start\_date="2026-04-15", end\_date="2026-04-18") |
| "**小浪底**当前出库流量"   | navigate\_to\_reservoir\_detail(reservoir\_name="小浪底", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") + get\_reservoir\_realtime(reservoir="小浪底", start\_date="2026-04-15", end\_date="2026-04-18") |
| "**陆浑**水库水位"      | navigate\_to\_reservoir\_detail(reservoir\_name="陆浑", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") + get\_reservoir\_realtime(reservoir="陆浑", start\_date="2026-04-15", end\_date="2026-04-18")   |
| "查看**五个水库**的实时情况" | navigate\_to\_reservoir\_overview() + get\_reservoir\_latest\_realtime()                                  |
| "**花园口**流量多少"     | navigate\_to\_station\_detail(station\_name="花园口", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00") + list\_realtime\_hydrology(station="花园口", start\_date="2026-04-15", end\_date="2026-04-18")      |
| "过去24小时降雨"        | navigate\_to\_rainfall\_overview() + get\_realtime\_rainfall(start\_time="2026-05-05 00:00:00", end\_time="2026-05-06 00:00:00")              |
| "相似雨分析"           | navigate\_to\_similar\_rainfall\_page(start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00")                                 |
| "**三门峡**水库未来水位预报" | navigate\_to\_reservoir\_forecast\_page(reservoir\_name="三门峡", start\_time="2026-04-15 00:00:00", end\_time="2026-04-18 00:00:00")                                        |
| "**小浪底**泄流情况"（场景） | fly\_to\_location(location\_name="XiaoLangDi")                                                        |
| "**马庄**控导信息"      | navigate\_to\_control\_guidance\_section(section\_name="马庄")                                             |

**关键规则**：

- 用户问"XX水库水位/流量" → **必须传 reservoir\_name="XX"**
- 用户问"XX水文站流量/水位" → **必须传 station\_name="XX"**
- 只有问"水库总览"、"水文站总览"、"五个水库情况"时才调用 `*_overview` 工具

## 工具参数详细说明

### 页面跳转类工具

| 工具名                                   | 参数               | 参数说明                                           | 是否必填 |
| ------------------------------------- | ---------------- | ---------------------------------------------- | ---- |
| `navigate_to_reservoir_overview`       | 无参数              | 跳转到水库总览页面                                     | -    |
| `navigate_to_reservoir_detail`         | `reservoir_name` | 水库名称（必须是中文），例如："小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"     | 是    |
|                                        | `start_time`     | 开始时间（默认三天前）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间（默认现在）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_station_overview`         | 无参数              | 跳转到水文站总览页面                                     | -    |
| `navigate_to_station_detail`           | `station_name`   | 水文站名称（必须是中文），例如："花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津" | 是    |
|                                        | `start_time`     | 开始时间（默认三天前）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间（默认现在）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_rainfall_overview`        | 无参数              | 跳转到降雨信息总览页面                                   | -    |
| `navigate_to_rainfall_basin`           | `basin`          | 流域名称，例如："黄河"、"洛河"、"伊洛河"                              | 是    |
|                                        | `start_time`     | 开始时间（默认三天前）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间（默认现在）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_similar_rainfall_page`   | `start_time`     | 开始时间。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_reservoir_forecast_page`  | `reservoir_name` | 水库名称（必须是中文），例如："小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"     | 是    |
|                                        | `start_time`     | 开始时间（默认三天前）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间（默认现在）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_station_forecast_page`    | `station_name`   | 水文站名称（必须是中文）                                   | 是    |
|                                        | `start_time`     | 开始时间（默认三天前）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
|                                        | `end_time`       | 结束时间（默认现在）。格式：yyyy-MM-dd HH:mm:ss              | 是    |
| `navigate_to_control_guidance_overview` | 无参数              | 跳转到控导信息总览页面                                    | -    |
| `navigate_to_control_guidance_section` | `section_name`   | 河段/断面名称                                          | 是    |

### 数据查询类工具

| 工具名                             | 参数           | 参数说明                                           | 是否必填 |
| ------------------------------- | ------------ | ---------------------------------------------- | ---- |
| `get_reservoir_latest_realtime` | 无参数          | 查询所有水库最新数据                                     | -    |
| `get_river_latest_realtime`     | 无参数          | 查询所有水文站最新数据                                    | -    |
| `get_realtime_rainfall`         | `start_time` | 开始时间（必传，默认三天前）。格式：yyyy-MM-dd HH:mm:ss，例如："2026-04-15 00:00:00" | 是    |
|                                  | `end_time`   | 结束时间（必传，默认现在）。格式：yyyy-MM-dd HH:mm:ss，例如："2026-04-18 00:00:00" | 是    |
| `get_daily_rainfall_stats`      | `station`    | 雨量站名称（支持模糊匹配，必传）                                  | 是    |
|                                  | `start_date` | 开始日期（必传，默认三天前）。格式：yyyy-MM-dd，例如："2026-04-15" | 是    |
|                                  | `end_date`   | 结束日期（必传，默认现在）。格式：yyyy-MM-dd，例如："2026-04-18" | 是    |
| `get_reservoir_realtime`         | `reservoir`  | 水库名称（必须是中文），例如："小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"     | 是    |
|                                  | `start_date` | 开始日期（必传，默认三天前）。格式：yyyy-MM-dd，例如："2026-04-15" | 是    |
|                                  | `end_date`   | 结束日期（必传，默认现在）。格式：yyyy-MM-dd，例如："2026-04-18" | 是    |
| `list_realtime_hydrology`        | `station`    | 水文站名称（必须是中文），例如："花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津" | 是    |
|                                  | `start_date` | 开始日期（必传，默认三天前）。格式：yyyy-MM-dd，例如："2026-04-15" | 是    |
|                                  | `end_date`   | 结束日期（必传，默认现在）。格式：yyyy-MM-dd，例如："2026-04-18" | 是    |

### 场景控制类工具

| 工具名               | 参数              | 参数说明                                                 | 是否必填 |
| ----------------- | --------------- | ---------------------------------------------------- | ---- |
| `fly_to_location` | `location_name` | 位置名称（可选值：SanMenXia、XiaoLangDi、LuHun、GuXian、HeKouCun） | 是    |

### 模型计算类工具

| 工具名                       | 参数              | 参数说明            | 是否必填 |
| ------------------------- | --------------- | --------------- | ---- |
| `run_rainfall_forecast_model` | `basin`         | 流域名称（必传）            | 是    |
|                           | `start_time`    | 开始时间（必传，默认三天前）。格式：yyyy-MM-dd HH:mm:ss，例如："2026-04-15 00:00:00"            | 是    |
|                           | `end_time`      | 结束时间（必传，默认现在）。格式：yyyy-MM-dd HH:mm:ss，例如："2026-04-18 00:00:00"            | 是    |
|                           | `rainfall_data` | 降雨数据（JSON格式字符串，必传） | 是    |

### 知识查询类工具

| 工具名               | 参数              | 参数说明                                                 | 是否必填 |
| ----------------- | --------------- | ---------------------------------------------------- | ---- |
| `query_knowledge_base` | `query`         | 查询关键词（必传），例如："水库调度"、"防洪预演"、"预警响应"、"应急处置"          | 是    |
|                   | `mode`          | 查询模式（可选），支持：local、global、hybrid、naive、mix，默认mix           | 否    |

## 注意事项

### 最重要：水库/水文站名称必须传递

**常见错误**：用户问"三门峡水位"时，调用了 `navigate_to_reservoir_overview()` 而不是 `navigate_to_reservoir_detail(reservoir_name="三门峡", ...)`

**正确做法**：

- 用户提到"三门峡" → `navigate_to_reservoir_detail(reservoir_name="三门峡", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`
- 用户提到"花园口" → `navigate_to_station_detail(station_name="花园口", start_time="2026-04-15 00:00:00", end_time="2026-04-18 00:00:00")`

### 实时数据优先原则

**必须记住**：

- 查询当前水位、流量、降雨量 → **跳转实时数据页面** (navigate\_to\_reservoir\_detail 或 navigate\_to\_station\_detail)
- 查询历史数据 → **跳转实时数据页面** 并指定时间范围
- 只有用户明确提到"预报"、"预测"、"未来"时 → 才跳转预报页面

### 其他注意事项

1. **页面跳转时必须判断** - 用户是否提到了具体水库/水文站名称
2. **提到名称必须传递** - 如果用户提到了"三门峡"，就必须传 reservoir\_name="三门峡"
3. **时间格式** - 使用 `yyyy-MM-dd HH:mm:ss` 格式，例如 `2026-04-15 00:00:00`
4. **异步处理** - 工具调用是异步的，但返回结果后再回复用户
5. **场景控制** - 飞向场景后简单回复跳转结果即可
6. **位置名称** - 场景控制使用英文编码：SanMenXia(三门峡)、XiaoLangDi(小浪底)、LuHun(陆浑)、GuXian(故县)、HeKouCun(河口村)
