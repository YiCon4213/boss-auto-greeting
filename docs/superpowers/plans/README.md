# 实施计划索引

已批准设计拆分为四个顺序阶段。完成计划保留为实现和验证证据，不因阶段结束删除。

| 阶段 | 状态 | 入口 |
| --- | --- | --- |
| 总计划 | 活动 | [2026-07-22-local-resume-delivery-agent.md](2026-07-22-local-resume-delivery-agent.md) |
| Phase 1：本地服务与数据基础 | 已完成，16 项测试、93% 覆盖率 | [2026-07-22-agent-foundation.md](2026-07-22-agent-foundation.md) |
| Phase 2：油猴桥接与批次采集 | 已完成，48 项测试、93.12% 覆盖率及真实浏览器门禁通过 | [2026-07-22-browser-bridge-collection.md](2026-07-22-browser-bridge-collection.md) |
| Phase 3：分析、话术与审批工作台 | 已完成，81 项测试、92.42% 覆盖率、Alembic `0003` 及桌面/窄屏工作台门禁通过 | [2026-07-22-analysis-approval-workbench.md](2026-07-22-analysis-approval-workbench.md) |
| Phase 4：安全发送、自然语言与外部调用 | 下一阶段，等待 Phase 3 合入 `main` | [2026-07-22-delivery-command-integration.md](2026-07-22-delivery-command-integration.md) |

执行规则：

- 新会话使用 `superpowers:executing-plans`，只从当前阶段第一个未完成复选框开始。
- 当前阶段退出门禁、实施日志、文档同步和独立提交均完成后，才能进入下一阶段。
- 阶段 PR 先合并到 GitHub `main`，本地 `main` 使用 `git pull --ff-only origin main` 同步，再创建新的 `codex/phase-*` 分支。
- 不跨阶段并行修改共享状态机，不重新生成已批准规格，不删除仍含决策或验证证据的计划。
