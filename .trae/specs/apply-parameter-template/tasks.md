# Tasks: 参数模板应用与调度方案验证

- [x] Task 1: 实现 `_find_template_file` 辅助函数
  - 扫描 `Parameter_template/` 下所有子目录，建立模板名称→文件路径的映射
  - 支持通过关键词（如"方案一"、"方案二"、"常规调度"）模糊匹配文件名
  - 缓存扫描结果避免重复读取文件系统
  - **验证**: 单元测试确认正确匹配所有 5 个模板文件，以及模糊匹配、未找到场景

- [x] Task 2: 实现 `list_parameter_templates` MCP 工具
  - 调用 `_find_template_file` 扫描所有模板
  - 读取每个模板的 sheet 列表和参数行数
  - 返回结构化列表：类别、名称、参数行数、结果 sheet 列表
  - **验证**: 调用工具，确认返回 5 个模板，各有正确类别和 sheet 信息

- [x] Task 3: 实现 `show_parameter_template` MCP 工具
  - 接收 `template_name` 参数，模糊匹配模板文件
  - 读取"参数" sheet 的 46 条参数（stcd, stnm, Control_Par, Instruction）
  - 同时返回该模板包含的计算结果 sheet 列表
  - 处理模板不存在、无参数 sheet 等异常
  - **验证**: 调用工具展示"方案一"参数，确认返回 46 条参数 + sheet 列表

- [x] Task 4: 实现 `apply_parameter_template` MCP 工具
  - 接收 `template_name` 和 `generate_scheme`（默认 True）参数
  - 读取模板"参数" sheet，逐条 UPDATE 到 Dispatch_Par 表（按 stcd 匹配）
  - 若 `generate_scheme=True`，调用 `generate_dispatch_scheme()` 生成方案单
  - 返回：模板名称、更新参数数、修改前后对比、scheme_id（若生成）
  - 处理 MDB 不可用、模板不存在等异常
  - **验证**: 应用模板后检查 Dispatch_Par 表数据一致，再调用 generate_dispatch_scheme 确认成功

- [x] Task 5: 实现 `verify_dispatch_result` MCP 工具
  - 接收 `template_name` 参数
  - 调用 `apply_parameter_template` 应用参数并生成方案
  - 读取 Q_Output 的实际计算结果
  - 读取模板中结果 sheet（三门峡、小浪底、陆浑、故县、河口村、下游等）
  - 按站点名+时间匹配对比实际 vs 预期流量
  - 计算各站点误差：最大偏差、平均偏差、偏差百分比
  - 返回验证报告：通过/需关注/失败，各站点误差详情
  - **验证**: 对"常规方案"模板运行验证，确认报告格式正确

- [x] Task 6: 更新 SKILL.md 文档
  - 在 `skills/custom/flood-control-mcp/SKILL.md` 中新增"参数模板"章节
  - 补充 4 个新工具的调用说明和示例
  - 新增"应用模板生成方案"工作流示例
  - **验证**: 文档内容与工具实现一致

# Task Dependencies
- Task 2, 3, 4, 5 均依赖 Task 1（`_find_template_file` 辅助函数）
- Task 5 依赖 Task 4（`apply_parameter_template`）
- Task 6 依赖 Task 2～5 全部完成