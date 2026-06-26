# 调度方案单生成与参数修改 Spec

## Why
当前 `forecast_models.py` 中的 `generate_dispatch_scheme` 工具仅从 SQLite 数据库读取历史调度方案数据，无法满足实际业务中需要基于 Access MDB 数据库进行实时调度计算、参数调整和调度方案单生成的需求。

## What Changes
- 在 [forecast_models.py](file:///D:/code/mcp-servers/src/tools/forecast_models.py) 中新增 `modify_dispatch_param` MCP 工具
- 在 [forecast_models.py](file:///D:/code/mcp-servers/src/tools/forecast_models.py) 中新增 `generate_dispatch_sheet` MCP 工具
- 新增 [schedule_dispatch_skill.md](file:///D:/code/mcp-servers/skills/custom/schedule-dispatch/SKILL.md) Skill 文件
- 在 [pyproject.toml](file:///D:/code/mcp-servers/pyproject.toml) 中新增 `pyodbc` 依赖

## Impact
- Affected specs: 无
- Affected code: `src/tools/forecast_models.py`, `pyproject.toml`
- New files: `skills/custom/schedule-dispatch/SKILL.md`

## ADDED Requirements

### Requirement: modify_dispatch_param 工具
系统 SHALL 提供一个 MCP 工具，允许用户通过自然语言描述修改 `data.mdb` 中 `Dispatch_Par` 表的调度参数。

#### Scenario: 修改敞泄/控泄模式
- **WHEN** 用户输入 "将小浪底改为敞泄模式"
- **THEN** 系统匹配到 stnm="小浪底"、Instruction="0表示敞泄，1表示控泄" 的记录
- **AND** 将 Control_Par 更新为 0
- **AND** 返回修改前后的参数对比

#### Scenario: 修改初始水位
- **WHEN** 用户输入 "三门峡初始水位改成 300"
- **THEN** 系统匹配到 stnm="三门峡"、Instruction="初始水位" 的记录
- **AND** 将 Control_Par 更新为 300.0
- **AND** 返回修改结果

#### Scenario: 查看所有参数
- **WHEN** 用户输入 "查看当前调度参数" 或不指定具体修改
- **THEN** 系统返回 Dispatch_Par 表中所有 46 条参数的完整列表

#### Scenario: 参数匹配失败
- **WHEN** 用户输入无法匹配到任何记录
- **THEN** 系统返回所有可用参数的列表，提示用户重新指定

### Requirement: generate_dispatch_sheet 工具
系统 SHALL 提供一个 MCP 工具，一键完成从 Excel 导入、调度计算到结果导出的完整流程。

#### Scenario: 生成调度方案单
- **WHEN** 用户调用 generate_dispatch_sheet
- **THEN** 系统依次执行：
  1. 读取 `data/Q_Inputsd.xlsx`，清空并导入到 `data.mdb` 的 `Q_Inputsd` 表
  2. 读取 `data/Q_Inputxd.xlsx`，清空并导入到 `data.mdb` 的 `Q_Inputxd` 表
  3. 运行 `RegualDispacth.exe` 进行调度计算
  4. 将 `Q_Output` 表导出为 Excel 到 `/output/` 文件夹
- **AND** 返回执行摘要（各步骤耗时、行数统计）

#### Scenario: Excel 文件不存在
- **WHEN** `data/Q_Inputsd.xlsx` 或 `data/Q_Inputxd.xlsx` 不存在
- **THEN** 返回明确的错误信息

#### Scenario: RegualDispacth.exe 执行失败
- **WHEN** exe 执行返回非零退出码或超时
- **THEN** 返回错误信息，包含退出码和 stderr 输出

### Requirement: Skill 文件
系统 SHALL 提供一个 Skill 说明文件，辅助 DeerFlow 等 LLM Agent 框架正确调用这两个 MCP 工具。

#### Scenario: Skill 内容完整性
- **WHEN** Agent 加载 Skill
- **THEN** Skill 包含：
  - 46 条 Dispatch_Par 参数的完整目录
  - 两个工具的调用示例
  - 典型工作流说明
  - 参数匹配规则