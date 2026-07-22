# 简历投递 Agent 文档索引

本目录记录如何在保留 BOSS 直聘油猴独立模式的前提下，建设一个仅在本机运行、必须人工审批、可供其它本地项目调用的简历投递 Agent。

## 当前实施状态

- Phase 1“本地服务与数据基础”已经完成并合入 `main`。
- Phase 2“油猴桥接与批次采集”的五个实现任务已经提交：Alembic `0002`、浏览器租约协议、显式令牌 CLI、默认关闭的 `AgentBridge`、不可变快照、只采集不发送的 `BatchCollector` 和采集闭环均已落地。
- 当前自动化门禁为 48 项 pytest 通过、`agent_app` 覆盖率 93%；原油猴独立入口契约与 JavaScript 语法检查通过。
- Phase 2 真实浏览器退出门禁已于 2026-07-22 在用户本人 Chrome 通过：只读采集两个岗位并形成两个不可变快照，终态重复回放保持幂等，全程无聊天导航和发送；停止本地服务后独立模式正常。Phase 3 尚未开始。
- 模型分析、审批工作台和安全发送尚未实现；当前代码不能用于 Agent 模式投递。

## 权威阅读顺序

1. [current-state-analysis.md](current-state-analysis.md)：代码与测试的当前事实。
2. [product-requirements.md](product-requirements.md)：产品行为与验收标准。
3. [设计规格](superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md)：架构、安全边界和数据流。
4. [roadmap.md](roadmap.md)：阶段状态、产物和退出条件。
5. [实施计划索引](superpowers/plans/README.md)：各阶段详细计划与当前入口。
6. [Phase 2 人工验证清单](manual-testing/phase-2-collection.md)：已通过的真实浏览器退出门禁记录。
7. [new-session-handoff.md](new-session-handoff.md)：新会话恢复上下文和下一步操作。

## 文档职责

- `product-requirements.md` 和已批准设计规格保存稳定决策，除非产品行为或安全边界改变，否则不要随实现细节重写。
- `current-state-analysis.md`、`roadmap.md`、计划复选框和 `new-session-handoff.md` 必须随每个阶段同步更新。
- 完成计划保留为实施与验证证据；重复交接、临时提示词和已经被权威文档完整替代的过程文件应按 `AGENTS.md` 的规则清理。

## 强制边界

- 只修改 `D:\Web\boss\boss-auto-greeting`，不得修改父项目。
- `zhipin-auto-greeting.user.js` 必须继续独立运行；本地服务不能成为独立模式依赖。
- 未经人工批准不得发送；不得绕过验证码、登录、安全校验、频率限制或访问控制。
- API Key、Cookie、密码、浏览器凭据、运行时数据库和日志不得提交到 Git。
