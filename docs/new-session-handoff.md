# 新会话交接说明

更新时间：2026-07-22。本文是唯一的新会话交接文件；不要再创建按日期复制的交接文档。

## 当前状态

Phase 1 已合入 `main`。Phase 2“油猴桥接与批次采集”已在 `codex/phase-2-browser-bridge-collection` 完成：48 项 pytest 全部通过，`agent_app` 覆盖率 93.12%，Alembic `0002 (head)`、Python 编译、Userscript 语法和差异检查通过。

2026-07-22 已在用户本人 Chrome 通过 Phase 2 退出门禁：只读采集两个岗位，批次为 `collected` 且快照数为 2；终态重复回放没有新增或改写快照。用户确认未进入聊天、未点击沟通、未发送消息，成功重跑期间也没有验证码或安全校验。关闭 Agent、停止本地服务并确认 8765 端口释放后，油猴独立模式正常进入原列表循环，并在实际沟通前人工停止。

## 已实现边界

- 浏览器任务只允许 `collect_batch`、`execute_delivery` 和 `pause`，采用短租约、worker 所有权和幂等结果。
- 浏览器令牌只通过 `python -m agent_app.cli show-browser-token` 在本机终端显式读取，HTTP API 不回显。
- Agent 模式默认关闭；关闭时继续调用原 `StandaloneAutomation`。
- `BatchCollector` 只选择岗位卡片和读取详情，不进入聊天、不发送消息。
- 快照身份键与 JD 指纹由服务端计算；重复任务不覆盖不可变快照，包括批次已完成后的终态重放。
- 计数不一致不能完成批次；验证码、登录失效和安全校验进入 `paused_security` 并保留已有快照。
- `ApprovedQueueRunner` 仍为未实现占位，当前代码不能用于 Agent 模式投递。

## 下一步

1. 按仓库流程审阅并集成 `codex/phase-2-browser-bridge-collection`，保留用户已有改动和未跟踪 IDE 文件。
2. 集成后同步本地 `main`，再从 Phase 3 计划第一个未完成复选框开始新分支；不要在 Phase 2 分支直接开始 Phase 3。
3. Phase 3 继续使用测试驱动方式，实现分析、话术与人工审批工作台；任何发送能力仍必须等待不可变人工批准队列。

## 安全边界

- 只处理用户本人登录后有权查看的岗位。
- 不自动登录，不读取、导出或上传 Cookie、密码和浏览器凭据。
- 不绕过验证码、登录、安全校验、频率限制或访问控制。
- 未经后续人工审批不得发送；Phase 2 只提供采集能力。

## 新会话执行指令

```text
请在 D:\Web\boss\boss-auto-greeting 中继续“本地简历投递 Agent”。只修改该子项目并保留已有改动。先完整阅读 AGENTS.md、docs 索引、当前状态、产品需求、设计规格、路线图、总计划与 Phase 3 计划；确认 Phase 2 已通过退出门禁并集成到 main 后，再从 Phase 3 第一个未完成复选框开始。使用 superpowers:executing-plans 和测试驱动方式；不得绕过人工审批、验证码、登录或安全校验，也不得破坏油猴独立模式。
```
