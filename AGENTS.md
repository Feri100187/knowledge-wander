## Git 工作流

每次完成会修改文件的开发任务后，必须执行以下流程：

1. 使用 `git status` 检查修改。
2. 运行本任务相关的测试或构建检查。
3. 只提交本次任务相关的文件。
4. 使用 `git add` 暂存修改。
5. 使用清晰的 commit message 创建 Git commit。
6. 提交前确认当前分支。
7. 执行 `git pull --rebase`，处理远程更新。
8. 执行 `git push` 将当前分支推送到 GitHub。
9. 再次执行 `git status`。
10. 只有在确认本地提交已经成功推送到远程后，任务才算完成。

如果 `git pull --rebase`、`git push`、测试或构建失败：

* 不得假装任务已经完成。
* 不得强制覆盖远程历史。
* 明确报告失败原因并等待用户处理或继续修复。

禁止：

* `git push --force`
* `git reset --hard`，除非用户明确要求
* 未经允许删除其他开发者或其他 Agent 的修改

