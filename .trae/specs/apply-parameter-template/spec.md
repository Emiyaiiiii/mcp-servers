# 参数模板应用与调度方案验证 Spec

## Why
当前 `forecast_models.py` 中 `modify_dispatch_param` 工具需要逐条手动修改参数，效率低。业务上需要支持"按模板一键切换参数 → 生成调度方案"的完整工作流。`Parameter_template/` 目录下已有 5 套预定义参数模板（含预期计算结果），需要将其集成到 MCP 工具中，并支持计算结果验证。

## What Changes
- 新增 `list_parameter_templates` 工具：列出所有可用的参数模板及其元信息
- 新增 `show_parameter_template` 工具：展示指定模板的完整参数设置
- 新增 `apply_parameter_template` 工具：将模板参数写入 Dispatch_Par 表，并自动生成调度方案单
- 新增 `verify_dispatch_result` 工具：将实际计算结果与模板中的预期结果对比验证
- 修改 [forecast_models.py](file:///D:/code/mcp-servers/src/tools/forecast_models.py)：新增上述 4 个工具
- 更新 [SKILL.md](file:///D:/code/mcp-servers/skills/custom/flood-control-mcp/SKILL.md)：新增模板相关工具文档

## Impact
- Affected specs: 无
- Affected code: `src/tools/forecast_models.py`
- Updated files: `skills/custom/flood-control-mcp/SKILL.md`

## ADDED Requirements

### Requirement: list_parameter_templates 工具
系统 SHALL 提供一个 MCP 工具，扫描 `Parameter_template/` 目录，列出所有可用的参数模板。

#### Scenario: 列出所有模板
- **WHEN** 用户调用 `list_parameter_templates`
- **THEN** 系统扫描 `Parameter_template/` 下所有子目录中的 `.xlsx` 文件
- **AND** 返回每个模板的：类别（上大洪水控制/下大洪水控制）、名称、文件路径、参数条数、包含的计算结果 sheet 列表

#### Scenario: 目录为空
- **WHEN** `Parameter_template/` 目录不存在或为空
- **THEN** 返回明确提示"无可用模板"

### Requirement: show_parameter_template 工具
系统 SHALL 提供一个 MCP 工具，展示指定模板的完整参数设置。

#### Scenario: 展示模板参数
- **WHEN** 用户指定模板名称（如"方案一"）调用 `show_parameter_template`
- **THEN** 系统读取对应 `.xlsx` 文件的"参数" sheet
- **AND** 返回 46 条参数的完整列表（stcd、stnm、Control_Par、Instruction）
- **AND** 同时返回该模板包含的计算结果 sheet 列表（供用户了解模板除了参数还有什么）

#### Scenario: 模板不存在
- **WHEN** 用户指定的模板名称无法匹配到任何文件
- **THEN** 返回可用模板列表，提示用户重新选择

#### Scenario: 模板无参数 sheet
- **WHEN** 模板文件存在但没有"参数" sheet
- **THEN** 返回错误信息"该模板不包含参数设置"

### Requirement: apply_parameter_template 工具
系统 SHALL 提供一个 MCP 工具，将指定模板的参数写入 Dispatch_Par 表，然后自动生成调度方案单。

#### Scenario: 成功应用模板并生成方案
- **WHEN** 用户指定模板名称调用 `apply_parameter_template`
- **THEN** 系统依次执行：
  1. 读取模板的"参数" sheet，获取 46 条参数
  2. 将参数逐条 UPDATE 到 `data.mdb` 的 `Dispatch_Par` 表（按 stcd 匹配）
  3. 调用 `generate_dispatch_scheme()` 生成调度方案单
- **AND** 返回：模板名称、更新的参数数量、方案单 scheme_id、summary 摘要

#### Scenario: 仅应用参数不生成方案
- **WHEN** 用户调用 `apply_parameter_template` 并设置 `generate_scheme=False`
- **THEN** 系统仅执行参数更新，不生成方案单
- **AND** 返回更新的参数列表（修改前后对比）

#### Scenario: 模板不存在
- **WHEN** 指定的模板名称无法匹配
- **THEN** 返回错误信息，列出可用模板

#### Scenario: MDB 数据库不可用
- **WHEN** `data.mdb` 不存在或被占用
- **THEN** 返回明确的数据库错误信息

### Requirement: verify_dispatch_result 工具
系统 SHALL 提供一个 MCP 工具，将实际计算结果与模板中的预期结果进行对比验证。

#### Scenario: 验证计算结果
- **WHEN** 用户调用 `verify_dispatch_result` 指定模板名称
- **THEN** 系统执行：
  1. 调用 `apply_parameter_template` 应用参数并生成方案
  2. 读取 `data.mdb` 中 `Q_Output` 表的实际计算结果
  3. 读取模板中计算结果 sheet（如"三门峡"、"小浪底"、"下游"等）
  4. 按站点/时间对比实际 vs 预期流量
  5. 计算吻合度指标：最大误差、平均误差、各站点偏差百分比
- **AND** 返回验证报告：通过/失败状态、各站点误差统计、整体吻合度

#### Scenario: 模板无计算结果
- **WHEN** 模板只有参数 sheet 没有结果 sheet
- **THEN** 返回提示"该模板仅包含参数，无预期计算结果可验证"

#### Scenario: 关键站点偏差过大
- **WHEN** 某站点最大流量偏差超过 5%
- **THEN** 验证状态标记为"需关注"，列出偏差最大的站点和时段

## 技术约束

1. **模板匹配规则**：通过文件名关键词匹配（如"方案一"匹配包含"方案一"的文件名），忽略括号和后续描述
2. **参数更新策略**：按 `stcd` 字段精确匹配 UPDATE，确保不产生新记录
3. **验证对比方案**：按 `stnm`（站点名）和 `tm`（时间）匹配实际 vs 预期数据
4. **Excel 读取**：使用 `pandas.read_excel` 读取各 sheet
5. **路径约定**：`Parameter_template/` 目录位于项目根目录，与 `src/` 并列