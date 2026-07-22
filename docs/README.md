# 简历投递 Agent 文档索引

本目录记录如何在保留 BOSS 直聘油猴独立模式的前提下，建设一个仅在本机运行、必须人工审批、可供其它本地项目调用的简历投递 Agent。

## 当前实施状态

- Phase 1“本地服务与数据基础”已经完成：FastAPI 应用、SQLite/Alembic、应用与浏览器双令牌、画像与模型设置、批次基础状态机及 `/api/v1` 骨架已经落地。
- Phase 1 自动化门禁为 16 项测试通过、`agent_app` 覆盖率 93%；原油猴脚本语法检查通过，Phase 1 没有修改油猴脚本。
- 下一阶段是 Phase 2“油猴桥接与批次采集”。不得在 Phase 1 分支未合并或本地 `main` 未同步时直接开始新的阶段分支。
- 真实 BOSS 浏览器采集、审批和发送尚未实现；当前代码不能用于 Agent 模式投递。

## 权威阅读顺序

1. [current-state-analysis.md](current-state-analysis.md)：代码与测试的当前事实。
2. [product-requirements.md](product-requirements.md)：产品行为与验收标准。
3. [设计规格](superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md)：架构、安全边界和数据流。
4. [roadmap.md](roadmap.md)：阶段状态、产物和退出条件。
5. [实施计划索引](superpowers/plans/README.md)：各阶段详细计划与当前入口。
6. [new-session-handoff.md](new-session-handoff.md)：新会话恢复上下文和下一步操作。

## 文档职责

- `product-requirements.md` 和已批准设计规格保存稳定决策，除非产品行为或安全边界改变，否则不要随实现细节重写。
- `current-state-analysis.md`、`roadmap.md`、计划复选框和 `new-session-handoff.md` 必须随每个阶段同步更新。
- 完成计划保留为实施与验证证据；重复交接、临时提示词和已经被权威文档完整替代的过程文件应按 `AGENTS.md` 的规则清理。

## 强制边界

- 只修改 `D:\Web\boss\boss-auto-greeting`，不得修改父项目。
- `zhipin-auto-greeting.user.js` 必须继续独立运行；本地服务不能成为独立模式依赖。
- 未经人工批准不得发送；不得绕过验证码、登录、安全校验、频率限制或访问控制。
- API Key、Cookie、密码、浏览器凭据、运行时数据库和日志不得提交到 Git。
