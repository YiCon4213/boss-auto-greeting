# 新会话交接说明

更新时间：2026-07-22。本文是唯一的新会话交接文件；不要再创建按日期复制的交接文档。

## 当前状态

Phase 1 已通过 PR #1 合入 `main`，Phase 2 已通过 PR #2 合入 `main`。Phase 3“分析、话术与审批工作台”已在 `codex/phase-3-analysis-approval-workbench` 完成：81 项 pytest 全部通过，`agent_app` 覆盖率 92.42%，Alembic `0003 (head)`、Python 编译、工作台与 Userscript 语法、差异检查均通过。

Phase 3 本机工作台验证也已通过：桌面双栏正常；390×844 窄屏无横向溢出，审批按钮完整可见。该验证没有访问 BOSS、调用真实模型或触发发送。Phase 2 的用户本人 Chrome 两岗位只读采集、终态幂等、无聊天/无发送和独立模式真实浏览器证据继续有效。

## 已实现边界

- OpenAI-compatible 客户端使用独立分析/问候语 schema，最多一次安全重试，错误不包含 API Key、原始响应或画像内容。
- 模型画像复用 `ProfileService.model_context()`；空字段和默认私密字段不进入请求。
- 目标分阈值决定默认选择，个人分不淘汰；分析关闭时不调用模型并默认进入审批。
- 问候语使用可追溯事实白名单，关闭时使用基础模板；失败记录不能被批准。
- 工作台提供批次分析、冻结快照审阅、选择、终稿编辑和人工批准，动态内容安全渲染。
- 批准生成不可变 `ApprovalVersion` 与 `DeliveryItem`，强 ID、JD 指纹和人工终稿冻结；重复批准幂等。
- 批准不会创建浏览器发送任务；`ApprovedQueueRunner` 仍是未实现占位，当前代码不能用于 Agent 模式投递。
- 油猴 Agent 默认关闭，关闭时继续调用原 `StandaloneAutomation`。

## 下一步

1. 按仓库流程审阅并集成 `codex/phase-3-analysis-approval-workbench`，保留用户已有改动和未跟踪 IDE 文件。
2. 集成后同步本地 `main`，再从 `docs/superpowers/plans/2026-07-22-delivery-command-integration.md` 第一个未完成复选框开始新的 `codex/phase-4-*` 分支；不要在 Phase 3 分支直接开始发送。
3. Phase 4 必须继续测试驱动，实现已批准队列的显式安全执行、发送前身份/会话复核、单项失败继续和安全类整批暂停。
4. 任何真实浏览器发送验证都必须由用户本人登录并明确授权；批准和开始执行必须保持为两个独立人工动作。

## 安全边界

- 只处理用户本人登录后有权查看的岗位。
- 不自动登录，不读取、导出或上传 Cookie、密码和浏览器凭据。
- 不绕过验证码、登录、安全校验、频率限制或访问控制。
- 未经人工批准不得发送；批准后仍需下一阶段的用户显式“开始执行”。
- Phase 3 工作台不提供发送入口，当前 `execute_delivery` 占位不能投递。

## 新会话执行指令

```text
请在 D:\Web\boss\boss-auto-greeting 中继续“本地简历投递 Agent”。只修改该子项目并保留已有改动。先完整阅读 AGENTS.md、docs 索引、当前状态、产品需求、设计规格、路线图、总计划与 Phase 4 计划；确认 Phase 3 已通过退出门禁并集成到 main 后，再从 Phase 4 第一个未完成复选框开始。使用 superpowers:executing-plans 和测试驱动方式；批准与开始执行必须保持为两个独立人工动作；不得绕过人工审批、验证码、登录或安全校验，也不得破坏油猴独立模式。
```
