# 简历投递 Agent 文档索引

本目录记录如何在保留 BOSS 直聘油猴独立模式的前提下，建设一个仅在本机运行、必须人工审批、可供其它本地项目调用的简历投递 Agent。

## 当前实施状态

- Phase 1“本地服务与数据基础”已通过 PR #1 合入 `main`；Phase 2“油猴桥接与批次采集”已通过 PR #2 合入 `main`。
- Phase 3“分析、话术与审批工作台”的五个实现任务已在 `codex/phase-3-analysis-approval-workbench` 完成：Alembic `0003`、隐私安全模型适配、可关闭双评分、事实可追溯问候语、不可变人工批准队列和原生双栏工作台均已落地。
- 当前自动化门禁为 81 项 pytest 通过、`agent_app` 覆盖率 92.42%；Python 编译、工作台与原油猴 JavaScript 语法、独立入口契约和差异检查通过。
- Phase 2 真实浏览器退出门禁继续有效：用户本人 Chrome 两岗位只读采集、终态幂等、全程无聊天/无发送，停止服务后独立模式正常。
- Phase 3 本机工作台退出门禁已通过：桌面双栏正常，390×844 窄屏无横向溢出且批准按钮完整可见；验证未访问 BOSS、未调用真实模型、未创建发送任务。
- 安全发送、自然语言命令和外部子 Agent 契约尚未实现；当前代码不能用于 Agent 模式投递。

## 权威阅读顺序

1. [current-state-analysis.md](current-state-analysis.md)：代码与测试的当前事实。
2. [product-requirements.md](product-requirements.md)：产品行为与验收标准。
3. [设计规格](superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md)：架构、安全边界和数据流。
4. [roadmap.md](roadmap.md)：阶段状态、产物和退出条件。
5. [实施计划索引](superpowers/plans/README.md)：各阶段详细计划与当前入口。
6. [Phase 2 人工验证清单](manual-testing/phase-2-collection.md)：已通过的真实浏览器退出门禁记录。
7. [Phase 3 工作台验证记录](manual-testing/phase-3-workbench.md)：自动化、桌面与窄屏退出门禁证据。
8. [new-session-handoff.md](new-session-handoff.md)：新会话恢复上下文和下一步操作。

## 文档职责

- `product-requirements.md` 和已批准设计规格保存稳定决策，除非产品行为或安全边界改变，否则不要随实现细节重写。
- `current-state-analysis.md`、`roadmap.md`、计划复选框和 `new-session-handoff.md` 必须随每个阶段同步更新。
- 完成计划保留为实施与验证证据；重复交接、临时提示词和已经被权威文档完整替代的过程文件应按 `AGENTS.md` 的规则清理。

## 强制边界

- 只修改 `D:\Web\boss\boss-auto-greeting`，不得修改父项目。
- `zhipin-auto-greeting.user.js` 必须继续独立运行；本地服务不能成为独立模式依赖。
- 未经人工批准不得发送；不得绕过验证码、登录、安全校验、频率限制或访问控制。
- API Key、Cookie、密码、浏览器凭据、运行时数据库和日志不得提交到 Git。
