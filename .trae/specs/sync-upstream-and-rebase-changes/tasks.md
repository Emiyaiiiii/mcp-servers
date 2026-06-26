# Tasks

- [x] Task 1: 拉取上游最新代码并创建新分支
  - [x] SubTask 1.1: `git fetch origin` 拉取远程 master 最新代码（fedee4c → 030a741）
  - [x] SubTask 1.2: `git checkout -b feat/sync-upstream-with-changes origin/master` 基于上游最新 master 创建新分支

- [x] Task 2: 将当前分支的修改合并到新分支
  - [x] SubTask 2.1: `git merge feat/flow-constraint-and-reservoir-stats` 将当前分支的修改合并过来
  - [x] SubTask 2.2: 出现冲突（forecast_models.py），已解决：保留上游 rainfall_similarity_analysis + 合并所有业务修改

- [x] Task 3: 提交并推送新分支
  - [x] SubTask 3.1: 确认合并后的代码完整且无冲突（commit 5afc2bc）
  - [ ] SubTask 3.2: `git push -u origin feat/sync-upstream-with-changes` 推送到远程（网络不通，需手动推送）

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2