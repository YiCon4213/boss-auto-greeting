# 当前项目状态审计

更新时间：2026-07-22。本文描述 Phase 2 实现及真实浏览器退出门禁全部通过后的代码事实，不替代产品需求或设计规格。

## 1. 仓库与分支边界

`D:\Web\boss\boss-auto-greeting` 是独立 Git 仓库，位于另一个 Git 仓库 `D:\Web\boss` 内。Phase 1 已通过 PR #1 合入 `main`；Phase 2 已在 `codex/phase-2-browser-bridge-collection` 完成，等待按仓库流程集成。Phase 3 尚未开始。

## 2. 已实现能力

### 2.1 Phase 1 基础

- `agent_app.main.create_app()` 提供 FastAPI 应用工厂，默认监听 `127.0.0.1:8765`。
- 应用令牌和浏览器令牌分离，模型密钥只进入 `SecretStore`。
- 画像、模型非敏感配置、批次基础状态机和 11 张业务表继续复用。

### 2.2 浏览器任务协议

- Alembic head 为 `0002`；只给既有 `browser_tasks` 增加 `leased_by`、`attempt_count`、`progress_sequence`、`acked_at` 和 `resolved_at`。
- 浏览器任务只允许 `collect_batch`、`execute_delivery` 和 `pause`，采用 30 秒租约、worker 所有权、单调进度序号和“首个终态获胜”的幂等规则。
- 浏览器桥接接口位于 `/api/v1/browser/*` 并只接受浏览器令牌；应用令牌不能调用。
- `python -m agent_app.cli show-browser-token` 是唯一显式读取浏览器令牌的本机入口，HTTP API 不回显任何令牌。

### 2.3 油猴 AgentBridge 与采集

- `agentModeEnabled` 默认 `false`；Agent 不在线或开关关闭时仍走原 `StandaloneAutomation`。
- Agent 地址只允许 `http://127.0.0.1:8765` 或同端口 `localhost`，不执行后端返回的任意代码、选择器或 URL。
- `BatchCollector` 使用独立的 `__zhipin_agent_task_state__`，只选择岗位卡片、等待稳定详情并提交快照。
- 采集代码不调用聊天按钮点击或 `GreetingService.sendCurrent`；`ApprovedQueueRunner` 仍是明确报错的未实现占位。
- 验证码、登录失效和安全校验产生 `paused_security` 并停止继续领取智能任务。

### 2.4 不可变职位快照与批次闭环

- 服务端只从 `encryptJobId`、`securityId`、`lid` 计算强身份键，并对规范化 JD 计算 SHA-256 指纹；客户端不能提供受信身份键或指纹。
- 同一批次同一强身份重复提交返回原快照，不改 payload 或指纹，并写 `job_snapshot_duplicate` 审计事件。
- `POST /api/v1/batches/{id}/collect` 幂等创建一个 `collect_batch` 任务。
- 成功结果必须与 SQLite 实际快照数一致；任务终结、审计、计数和 `collecting -> collected` 在同一事务提交。
- 普通失败进入 `failed`，安全错误进入 `paused_security`，已有快照不会删除。

## 3. 当前测试与验证证据

- 48 项 pytest 全部通过，`agent_app` 总覆盖率 93.12%。
- Python `compileall`、`node --check zhipin-auto-greeting.user.js` 和 `git diff --check` 通过。
- Alembic 在新 SQLite 上从空库升级到 `0002 (head)`。
- 仍有一条既有 FastAPI/Starlette `TestClient` 第三方弃用警告，不影响通过结果。
- 2026-07-22 在用户本人 Chrome 完成 `limit=2` 的真实批次：任务终态为 `resolved`，批次为 `collected`，SQLite 中为两个不同强身份键和 JD 指纹的快照；分析、问候语、审批版本和发送项均为 0。
- 对已完成批次重复上报同一载荷返回 `duplicate=true`；快照计数保持 2，原 ID、payload、JD 指纹及时间戳均未改变，只新增一条重复审计事件。
- 用户确认采集期间没有进入聊天、点击沟通或发送消息，也没有出现验证码或安全校验。Agent 关闭且本地服务端口释放后，独立模式正常进入原列表循环，并在实际沟通前人工停止。

## 4. 尚未实现

- 模型分析、个性化话术、审批工作台、不可变批准队列执行和自然语言命令尚未实现。
- `execute_delivery` 仍只返回“发送队列尚未实现”，不能用于 Agent 投递。
- 后续真实浏览器验证仍必须由用户本人登录并授权；遇验证码或安全校验只暂停，不处理或绕过。

## 5. 主要风险

1. 油猴主脚本仍是大型单文件；后续只能按职责扩展，不能借机整体重写。
2. BOSS 的 SPA、DOM 和内部接口可能变化，自动契约不能替代本人登录环境的小批量验证。
3. 当前只支持一个活动浏览器和一个执行批次；不得扩展为云端、多用户或绕过平台限制的服务。
4. 后续分析、审批和发送必须继续消费同一应用服务，不能复制业务规则或绕过人工审批。
