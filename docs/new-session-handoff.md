# 新会话交接说明

更新时间：2026-07-22。本文是唯一的新会话交接文件；不要再创建按日期复制的交接文档。

## 当前状态

Phase 1 已合入 `main`。Phase 2“油猴桥接与批次采集”的五个实现任务已经在 `codex/phase-2-browser-bridge-collection` 上完成并独立提交；45 项 pytest、93% 覆盖率、Alembic `0002 (head)`、Python 编译、Userscript 语法和差异检查均通过。

Phase 2 仍未完成：当前环境没有可控制的 Chrome/Tampermonkey 窗口，尚未执行本人登录环境的两岗位采集和独立模式回归。不得把自动化契约当成人工证据，也不得开始 Phase 3。

## 已实现边界

- 浏览器任务只允许 `collect_batch`、`execute_delivery` 和 `pause`，采用短租约、worker 所有权和幂等结果。
- 浏览器令牌只通过 `python -m agent_app.cli show-browser-token` 在本机终端显式读取，HTTP API 不回显。
- Agent 模式默认关闭；关闭时继续调用原 `StandaloneAutomation`。
- `BatchCollector` 只选择岗位卡片和读取详情，不进入聊天、不发送消息。
- 快照身份键与 JD 指纹由服务端计算；重复任务不覆盖不可变快照。
- 计数不一致不能完成批次；验证码、登录失效和安全校验进入 `paused_security` 并保留已有快照。
- `ApprovedQueueRunner` 仍为未实现占位，当前代码不能用于 Agent 模式投递。

## 下一步：只完成 Phase 2 人工退出门禁

1. 阅读 `AGENTS.md`、`docs/README.md`、`docs/current-state-analysis.md` 和 Phase 2 计划。
2. 检查 Git 状态和 `codex/phase-2-browser-bridge-collection` 的五个功能提交，保留任何已有未提交改动。
3. 按 `docs/manual-testing/phase-2-collection.md` 在用户本人已登录、可正常手动浏览的 BOSS 环境执行两岗位采集。
4. 记录无聊天导航、无消息发送、两个不可变快照、`collected` 批次状态、重复/刷新幂等和服务停止后的独立模式证据。
5. 遇到验证码、登录失效或安全校验只确认整批暂停，不处理、不绕过。
6. 证据全部通过后，勾选 Task 2 Step 7、Phase 2 与总计划复选框，更新本文件、索引和路线图，再做 Phase 2 完成提交。

## 安全边界

- 只处理用户本人登录后有权查看的岗位。
- 不自动登录，不读取、导出或上传 Cookie、密码和浏览器凭据。
- 不绕过验证码、登录、安全校验、频率限制或访问控制。
- 未经后续人工审批不得发送；Phase 2 只允许采集。

## 新会话执行指令

```text
请在 D:\Web\boss\boss-auto-greeting 中继续“本地简历投递 Agent”的 Phase 2 退出门禁。只修改该子项目，保留已有改动。先核对 Phase 2 分支的五个功能提交与 45 项测试证据；不要开始 Phase 3。按 docs/manual-testing/phase-2-collection.md 在本人登录的 BOSS 浏览器中完成两岗位只采集验证和 Agent 关闭后的独立模式回归。不得进入聊天或发送，不得绕过验证码、登录或安全校验。只有全部人工证据通过后才勾选 Phase 2、同步文档并提交完成记录。
```
