# 同步上游框架并重新应用修改 Spec

## Why
上游框架（`https://github.com/Emiyaiiiii/mcp-servers` master 分支）可能有新的更新，需要将我们的业务修改（`feat/flow-constraint-and-reservoir-stats` 分支）基于最新上游代码重新应用，确保代码干净且可追溯。

## What Changes
- 从远程仓库拉取最新 master 代码
- 基于 `origin/master` 创建新分支 `feat/sync-upstream-with-changes`
- 将当前分支的业务修改合并到新分支上
- 提交并推送新分支

## Impact
- Affected specs: 合并 `add-dispatch-sheet-generation`、`apply-parameter-template` 以及后续所有修改
- Affected code: 51 个文件变更（相对于 origin/master），核心文件为 `src/tools/forecast_models.py`、`skills/custom/flood-control-mcp/SKILL.md`

## Requirements
### Requirement: 同步上游并创建新分支
系统 SHALL 从 origin/master 拉取最新代码，创建新分支，并将当前分支的所有业务修改合并到新分支上。

#### Scenario: 成功同步并合并
- **WHEN** 执行 git fetch origin 并基于 origin/master 创建新分支
- **THEN** 新分支包含所有上游最新代码 + 我们的业务修改
- **AND** 代码可以正常启动 MCP 服务