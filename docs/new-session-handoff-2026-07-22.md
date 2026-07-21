# 新会话实施交接（2026-07-22）

## 当前状态

书面规格已经通过，详细实施计划已经生成，产品代码尚未开始修改。工作目录是 `D:\Web\boss\boss-auto-greeting`；不得修改父目录 `D:\Web\boss` 原项目。

## 必读顺序

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/current-state-analysis.md`
4. `docs/product-requirements.md`
5. `docs/superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md`
6. `docs/roadmap.md`
7. `docs/superpowers/plans/2026-07-22-local-resume-delivery-agent.md`
8. `docs/superpowers/plans/2026-07-22-agent-foundation.md`
9. 后续三个阶段计划只在进入对应阶段前完整阅读

## 执行规则

- 使用 `superpowers:executing-plans`，严格按复选框和测试驱动步骤执行。
- 先只执行 Phase 1；通过退出门禁并汇报后，再进入 Phase 2。
- 保留油猴独立模式，Agent 默认关闭，本地服务不可用时不得影响原功能。
- 采集与发送分离；发送只能消费不可变的人工批准队列。
- 不自动登录、不处理验证码、不导出 Cookie、不绕过安全校验。
- 列表更新后必须按强 ID 重新定位；身份不匹配时跳过，安全类问题暂停整批。
- 模型不得虚构简历事实，空画像字段不参与分析，联系方式和敏感字段默认不发送给模型。
- 开始前检查 Git 状态并保留用户已有改动；每个任务按计划独立验证和提交。

## 可直接复制到新会话的指令

```text
请在 D:\Web\boss\boss-auto-greeting 中执行“本地简历投递 Agent”实施计划。只修改该子项目，不得修改父目录 D:\Web\boss 的原项目。先完整阅读 AGENTS.md、docs/README.md、docs/current-state-analysis.md、docs/product-requirements.md、docs/superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md、docs/roadmap.md、docs/superpowers/plans/2026-07-22-local-resume-delivery-agent.md 和 docs/superpowers/plans/2026-07-22-agent-foundation.md。检查 Git 状态并保留已有改动。使用 superpowers:executing-plans，严格按复选框和测试驱动方式从 Phase 1 的第一个未完成任务开始；本次先只执行 Phase 1，完成退出门禁并汇报后再进入下一阶段。保留油猴独立模式，不得绕过人工审批、验证码、登录或安全校验。
```

后续阶段入口：

- `docs/superpowers/plans/2026-07-22-browser-bridge-collection.md`
- `docs/superpowers/plans/2026-07-22-analysis-approval-workbench.md`
- `docs/superpowers/plans/2026-07-22-delivery-command-integration.md`
