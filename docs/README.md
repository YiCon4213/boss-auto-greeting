# 简历投递 Agent 文档索引

本目录描述如何把当前的 BOSS 直聘油猴脚本改造成一个本机运行、人工审批后发送、可被其他项目调用的简历投递 Agent。

## 阅读顺序

1. [current-state-analysis.md](current-state-analysis.md)：现有代码、能力、缺口和可复用边界。
2. [product-requirements.md](product-requirements.md)：已经确认的产品需求与验收口径。
3. [superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md](superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md)：完整架构和数据流设计。
4. [roadmap.md](roadmap.md)：建议的阶段顺序、阶段产物和退出条件。
5. [new-session-handoff.md](new-session-handoff.md)：供新 Codex 会话快速恢复上下文的交接说明。

## 强制项目边界

- 只修改 `D:\Web\boss\boss-auto-greeting`。
- 不修改父目录原项目 `D:\Web\boss` 中已有的 Python 服务、Chrome 扩展、测试或文档。
- 保留 `zhipin-auto-greeting.user.js` 的独立运行能力。本地 Agent 未启动或智能辅助关闭时，原有固定话术自动沟通功能仍可使用。
- 不把 `zhipin-devtools-unlock.user.js` 作为正式产品依赖，不设计绕过验证码、登录校验、安全验证或平台访问控制的功能。
- 所有发送动作必须来源于已人工批准的批次，并在发送前确认岗位和会话身份。

## 当前文档状态

这些文档记录的是已与用户确认的设计。详细到具体文件、测试命令和提交粒度的实施计划，需要在书面设计规格审阅通过后单独生成。
