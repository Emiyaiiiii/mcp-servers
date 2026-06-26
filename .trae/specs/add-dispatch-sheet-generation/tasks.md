# Tasks

- [x] Task 1: 添加 pyodbc 依赖到 pyproject.toml
  - 在 [pyproject.toml](file:///D:/code/mcp-servers/pyproject.toml) 的 dependencies 中添加了 `"pyodbc>=5.0.0"`
  - 运行 `uv sync` 安装依赖

- [x] Task 2: 实现 modify_dispatch_param 工具
  - 在 [forecast_models.py](file:///D:/code/mcp-servers/src/tools/forecast_models.py) 的 `register_forecast_models` 函数中新增 `modify_dispatch_param` 工具
  - 连接 `6/data.mdb`，读取 Dispatch_Par 表
  - 基于用户输入的自然语言描述，匹配 stnm（站点名）和 Instruction（参数说明）
  - 支持查看所有参数、修改参数值、匹配失败时返回可用参数列表
  - 修改后返回修改前后的对比

- [x] Task 3: 实现 generate_dispatch_sheet 工具
  - 在 [forecast_models.py](file:///D:/code/mcp-servers/src/tools/forecast_models.py) 的 `register_forecast_models` 函数中新增 `generate_dispatch_sheet` 工具
  - 步骤1：读取 `data/Q_Inputsd.xlsx` 和 `data/Q_Inputxd.xlsx`
  - 步骤2：清空并导入到 `6/data.mdb` 的对应表
  - 步骤3：运行 `RegualDispacth.exe`（subprocess，设置超时300秒）
  - 步骤4：将 `Q_Output` 表导出为 Excel 到 `/output/` 文件夹
  - 返回执行摘要

- [x] Task 4: 创建 Skill 文件
  - 创建了 `skills/custom/schedule-dispatch/` 目录
  - 创建了 [SKILL.md](file:///D:/code/mcp-servers/skills/custom/schedule-dispatch/SKILL.md)，包含参数目录、调用示例、工作流说明

- [x] Task 5: MCP 功能测试
  - modify_dispatch_param list：返回全部46条参数 ✅
  - modify_dispatch_param update（精确关键词）：修改成功并返回前后对比 ✅
  - modify_dispatch_param update（模糊关键词）：返回多条匹配项 ✅
  - modify_dispatch_param update（无匹配）：返回错误和全部可用参数 ✅
  - generate_dispatch_sheet：导入1780+8346行，计算3.69s，导出9630行 ✅

# Task Dependencies
- Task 2 和 Task 3 依赖 Task 1（pyodbc 安装后才能编写代码）
- Task 4 可与 Task 2、Task 3 并行
- Task 5 依赖 Task 2、Task 3、Task 4